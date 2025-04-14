
import os
import sys
import pysrt
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from app.services.cosyvoice_tts import get_cosyvoice_model


def make_audios(srt_path, voice_id=None):
    
    
    tts = get_cosyvoice_model()
    vocals_list = []

    # Use the provided voice_id or default to "中文女" if none is specified
    selected_voice = voice_id if voice_id else "中文女"
    
    try:
        # Read SRT file
        subs = pysrt.open(srt_path)
        i = 1
        for sub in subs:
            # Extract subtitle text
            text = sub.text
            # Use TTS to generate audio with the selected voice
            audio = tts.synthesize(
                text=text, 
                params={},
                output_path=f'{i}.wav', 
                voice_id=selected_voice  # Use the selected voice_id here
            )  
            # Add generated audio to the list
            vocals_list.append(audio)
            i = i + 1
        print(vocals_list)
    except Exception as e:
        print(f"Error processing subtitles: {e}")
    return vocals_list
if __name__ == "__main__":
    

    # 遍历每个视频文件及其对应的字幕文件
    
    make_audios(os.path.join(os.path.dirname(os.path.abspath(__file__)),'subtitles','test.srt'))

            # 读取SRT文件
        
    
    

