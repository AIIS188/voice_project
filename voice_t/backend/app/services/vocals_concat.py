import pysrt
import os
import librosa
import soundfile as sf
import numpy as np


def create_silent_audio(duration_ms, sr=44100):
    """
    创建指定时长的空白音频
    :param duration_ms: 空白音频的时长（毫秒）
    :param sr: 音频采样率
    :return: 指定时长的空白音频数组
    """
    duration_sec = duration_ms / 1000
    return np.zeros(int(duration_sec * sr))


def scale_audio(audio, sr, target_duration_ms):
    """
    使用 librosa 对音频进行不变调缩放以达到目标时长
    :param audio: 输入的音频数组
    :param sr: 音频采样率
    :param target_duration_ms: 目标时长（毫秒）
    :return: 缩放后的音频数组
    """
    current_duration_sec = len(audio) / sr
    current_duration_ms = current_duration_sec * 1000
    if current_duration_ms == 0:
        return audio
    rate = current_duration_ms/ target_duration_ms
    return librosa.effects.time_stretch(audio, rate=rate)


def vocals_concat(srt_file_path, audio_files, output_file_path=None, sr=44100):
    """
    根据 SRT 文件的时间戳拼接音频
    :param srt_file_path: SRT 文件的路径
    :param audio_files: 准备好的音频文件列表
    :param output_file_path: 输出音频文件的路径
    :param sr: 音频采样率
    """
    subs = pysrt.open(srt_file_path)
    final_audio = np.array([])
    prev_end_ms = 0

    for i, sub in enumerate(subs):
        start_ms = sub.start.milliseconds + sub.start.seconds * 1000 + sub.start.minutes * 60 * 1000 + sub.start.hours * 60 * 60 * 1000
        end_ms = sub.end.milliseconds + sub.end.seconds * 1000 + sub.end.minutes * 60 * 1000 + sub.end.hours * 60 * 60 * 1000

        # 用空白音频填充前一个字幕结束到当前字幕开始的时间段
        silent_duration = start_ms - prev_end_ms
        if silent_duration > 0:
            silent_audio = create_silent_audio(silent_duration, sr)
            final_audio = np.concatenate((final_audio, silent_audio))

        # 加载当前音频文件
        audio, _ = librosa.load(audio_files[i % len(audio_files)], sr=sr)

        # 调整音频时长
        target_duration_ms = end_ms - start_ms
        scaled_audio = scale_audio(audio, sr, target_duration_ms)

        # 拼接调整后的音频
        final_audio = np.concatenate((final_audio, scaled_audio))

        prev_end_ms = end_ms

    # 处理最后一个字幕结束到音频末尾的空白部分
    total_duration_ms = end_ms
    if len(final_audio) / sr * 1000 < total_duration_ms:
        remaining_silent_duration = total_duration_ms - len(final_audio) / sr * 1000
        remaining_silent_audio = create_silent_audio(remaining_silent_duration, sr)
        final_audio = np.concatenate((final_audio, remaining_silent_audio))
    out_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),'concated_vocals')
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

     # 保存最终音频
    if output_file_path != None:
        sf.write(os.path.join(out_dir,output_file_path), final_audio, sr)
        print(f"音频拼接完成，保存到 {os.path.join(out_dir,output_file_path)}")
    return os.path.join(out_dir,output_file_path)
    
def vocal_and_back_concat(audio1_path, audio2_path, output_path):
    """
    合成两段音频
    :param audio1_path: 第一段音频文件的路径
    :param audio2_path: 第二段音频文件的路径
    :param output_path: 输出音频文件的路径
    :return: 合成后的音频文件的路径
    """
    # 加载音频文件
    audio1, sr1 = librosa.load(audio1_path)
    audio2, sr2 = librosa.load(audio2_path)
    
    # 确保采样率一致
    if sr1 != sr2:
        # 可以选择将音频重采样到其中一个采样率，这里选择 sr1
        audio2 = librosa.resample(audio2, orig_sr=sr2, target_sr=sr1)
        sr = sr1
    else:
        sr = sr1

    # 确保两段音频长度一致
    max_length = max(len(audio1), len(audio2))
    audio1_padded = np.pad(audio1, (0, max_length - len(audio1)), mode='constant')
    audio2_padded = np.pad(audio2, (0, max_length - len(audio2)), mode='constant')
    
    # 合成音频
    synthesized_audio = audio1_padded + audio2_padded
    
    # 归一化音频
    synthesized_audio = librosa.util.normalize(synthesized_audio)
    out_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),'final_audio')
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    # 保存合成后的音频
    sf.write(os.path.join(out_dir,output_path), synthesized_audio, sr)
    
    return os.path.join(out_dir,output_path)

if __name__ == "__main__":
    srt_file_path = "subtitles/test.srt"
    audio_files = ["test_voice/1.wav", "test_voice/2.wav","test_voice/3.wav"]
    output_file_path = "output_audio.wav"




