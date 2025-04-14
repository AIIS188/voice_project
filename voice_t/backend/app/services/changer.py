import os
import ffmpeg
import whisper
import warnings
from typing import Iterator, TextIO
import opencc  # 新增：导入 opencc 进行繁体转简体
import sys
os.environ["IMAGEMAGICK_BINARY"] = r"C:\Program Files\ImageMagick-7.1.1-Q16\magick.exe"
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip





# 获取当前目录并添加CosyVoice路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.append(ROOT_DIR)

from app.services.make_audios import make_audios
import pysrt
from app.services.vocals_concat import vocals_concat, vocal_and_back_concat  # 输入srt文件和音频文件，输出拼接后的音频文件（以变量形式返回）
from app.services.sparator import get_background_sound  # 输入视频地址，输出背景音（返回地址）


# 初始化 opencc 转换器（繁体转简体）
converter = opencc.OpenCC('t2s')


# 将字符串转换为布尔值的函数
def str2bool(string):
    # 将输入字符串转换为小写，便于统一处理
    string = string.lower()
    # 定义字符串到布尔值的映射字典
    str2val = {"true": True, "false": False}

    # 检查输入字符串是否在映射字典中
    if string in str2val:
        # 如果存在，返回对应的布尔值
        return str2val[string]
    else:
        # 如果不存在，抛出值错误异常，提示用户输入错误
        raise ValueError(
            f"Expected one of {set(str2val.keys())}, got {string}")


# 将秒数转换为 SRT 格式时间戳的函数
def format_timestamp(seconds: float, always_include_hours: bool = False):
    # 确保输入的秒数为非负数
    assert seconds >= 0, "non-negative timestamp expected"
    # 将秒数转换为毫秒数
    milliseconds = round(seconds * 1000.0)

    # 计算小时数
    hours = milliseconds // 3_600_000
    # 减去已经计算的小时对应的毫秒数
    milliseconds -= hours * 3_600_000

    # 计算分钟数
    minutes = milliseconds // 60_000
    # 减去已经计算的分钟对应的毫秒数
    milliseconds -= minutes * 60_000

    # 计算秒数
    seconds = milliseconds // 1_000
    # 减去已经计算的秒对应的毫秒数
    milliseconds -= seconds * 1_000

    # 根据条件决定是否显示小时部分
    hours_marker = f"{hours:02d}:" if always_include_hours or hours > 0 else ""
    # 返回格式化后的时间戳字符串
    return f"{hours_marker}{minutes:02d}:{seconds:02d},{milliseconds:03d}"


# 将转录结果写入 SRT 文件的函数
def write_srt(transcript: Iterator[dict], file: TextIO):
    for i, segment in enumerate(transcript, start=1):
        # 转换字幕文本为简体中文
        simplified_text = converter.convert(segment['text'].strip().replace('-->', '->'))

        print(
            f"{i}\n"
            f"{format_timestamp(segment['start'], always_include_hours=True)} --> "
            f"{format_timestamp(segment['end'], always_include_hours=True)}\n"
            f"{simplified_text}\n",  # 使用转换后的简体字幕
            file=file,
            flush=True,
        )


# 从文件路径中提取文件名（不包含扩展名）的函数
def filename(path):
    # 先获取文件名（包含扩展名），再分离扩展名，返回文件名部分
    return os.path.splitext(os.path.basename(path))[0]


# 封装处理视频的主逻辑函数
def process_video(input_video_path,model_name="small", output_dir="output_video",
                  output_srt=False, srt_only=False, verbose=False,
                  task="transcribe", language="zh"):
    output_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),output_dir)
    

    try:
        # 创建输出目录，如果目录已存在则不会报错
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        # 若创建目录时出错，打印错误信息并返回
        print(f"Error creating output directory: {e}")
        return None

    # 检查模型名称是否以 .en 结尾，若是则强制语言检测为英语
    if model_name.endswith(".en"):
        warnings.warn(
            f"{model_name} is an English-only model, forcing English detection.")
        language = "en"

    try:
        # 加载指定的 Whisper 模型
        model = whisper.load_model(model_name)
    except Exception as e:
        # 若加载模型时出错，打印错误信息并返回
        print(f"Error loading Whisper model: {e}")
        return None

    # 从视频文件中提取音频
    audio = get_audio(input_video_path)
    audio_back = get_background_sound(audio,c='accompaniment.wav')

    # 根据音频生成字幕文件
    
    subtitles = get_subtitles(
        audio,
        lambda audio_path: model.transcribe(audio_path, task=task, language=language)
    )

    return audio_back,subtitles
    
    

    

    


# 从视频文件中提取音频的函数
def get_audio(path,out_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'vedio_audio')):
    # 检查输出目录是否存在，不存在则创建
    if not os.path.exists(out_path):
        os.makedirs(out_path)



    # 遍历每个视频文件路径

        # 检查视频文件是否存在
    if not os.path.isfile(path):
            # 若文件不存在，打印提示信息并跳过该文件
        print(f"Video file {path} not found. Skipping...")

    print(f"Extracting audio from {filename(path)}...")
        # 构建音频文件的完整路径
    output_path = os.path.join(out_path, f"{filename(path)}.wav")

    try:
            # 使用 ffmpeg 从视频中提取音频并保存为 WAV 格式
        ffmpeg.input(path).output(
            output_path,
            acodec="pcm_s16le", ac=1, ar="16k"
        ).run(quiet=True, overwrite_output=True)

    except ffmpeg.Error as e:
            # 若提取音频时出错，打印错误信息
        print(f"Error extracting audio from {filename(path)}: {e.stderr.decode()}")

    return output_path


# 根据音频文件生成字幕文件的函数
def get_subtitles(audio_path: str, transcribe: callable, output_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),'subtitle')):
    # 强制字幕文件存放在 output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir) 
    srt_path = os.path.join(output_dir, f"{filename(audio_path)}.srt")

    print(
        f"正在创建字幕文件，保存在{filename(audio_path)}... This might take a while."
    )

    try:
        # 临时忽略警告信息
        warnings.filterwarnings("ignore")
        # 调用转录函数进行语音识别和转录
        result = transcribe(audio_path)
        # 恢复警告信息的显示
        warnings.filterwarnings("default")

        # 打开字幕文件并写入转录结果
        with open(srt_path, "w", encoding="utf-8") as srt:
            write_srt(result["segments"], file=srt)

        print(f"字幕文件已成功保存到 {srt_path}")
        return srt_path
    except Exception as e:
        # 若生成字幕时出错，打印错误信息
        print(f"创建失败 {filename(audio_path)}: {e}")
        return None
# ... 现有代码 ...

from multiprocessing import Process, Queue

def process_video_wrapper(queue, input_video_path, model_name="small", output_dir="output_video",
                          output_srt=False, srt_only=False, verbose=False,
                          task="transcribe", language="zh"):
    result = process_video(input_video_path, model_name, output_dir, output_srt, srt_only, verbose, task, language)
    queue.put(result)

def vocals_concat_wrapper(queue, subtitles, vocals_list, output_file):
    vocals = vocals_concat(subtitles, vocals_list, output_file)
    queue.put(vocals)


def add_subtitles_to_video(video_path, audio_path, srt_path, output_path=None):
    if output_path==None:
        output_path=os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)),'output_video'), f"{filename(video_path)}_out.mp4")
    if not os.path.exists(os.path.dirname(output_path)):
        os.mkdir(os.path.dirname(output_path))
    
    # 加载视频和音频
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)

    # 替换视频的音频
    video = video.set_audio(audio)

    # 使用 pysrt 读取 SRT 文件，尝试不同编码
    
    subs = pysrt.open(srt_path, encoding='utf-8')
    

    subtitle_clips = []
    for sub in subs:
        text = sub.text
        print(f"处理字幕: {text}")

        start_time = sub.start.seconds + sub.start.milliseconds / 1000
        end_time = sub.end.seconds + sub.end.milliseconds / 1000

        # 打印调试信息，确保时间转换正确
        print(f"字幕时间 - 开始: {start_time}秒, 结束: {end_time}秒")

        # 创建字幕剪辑，指定支持中文的字体，并添加黑色描边
        subtitle = TextClip(text, fontsize=24, color='white', method='caption', size=(video.w * 0.8, None),
                            font='SimHei', stroke_color='black', stroke_width=0.5)
        subtitle = subtitle.set_start(start_time).set_end(end_time).set_position(('center', 'bottom'))
        subtitle_clips.append(subtitle)

    # 合成视频和字幕
    final_video = CompositeVideoClip([video] + subtitle_clips)

    # 保存最终视频
    final_video.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=video.fps)

    # 关闭剪辑对象
    video.close()
    audio.close()
    final_video.close()

    return output_path

# 主要功能函数
def video_changer(video_path, voice_id=None):
    result_queue = Queue()

    # Create a new process to execute process_video function
    p = Process(target=process_video_wrapper, args=(result_queue, video_path))
    # Start the process
    p.start()
    # Wait for the process to end
    p.join()

    # Get results from the queue
    audio_back, subtitle = result_queue.get()

    # Pass the voice_id to make_audios function
    vocals_list = make_audios(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'subtitle', f'{filename(video_path)}.srt'),
        voice_id=voice_id  # Pass the voice_id here
    )

    vocals_queue = Queue()

    # Create a new process to execute vocals_concat function
    p2 = Process(target=vocals_concat_wrapper, args=(vocals_queue, subtitle, vocals_list, 'concated_vocals.wav'))
    # Start the process
    p2.start()
    # Wait for the process to end
    p2.join()

    # Get results from the queue
    vocals = vocals_queue.get()
    audios = vocal_and_back_concat(vocals, audio_back, f'{filename(subtitle)}_final.wav')
    out_path = add_subtitles_to_video(video_path, audios, subtitle)
    
    return out_path
    
    return out_path
if __name__ == '__main__':
    # 创建一个队列用于进程间通信
    print(video_changer('test.mp4'))




    