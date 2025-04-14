
import os
from spleeter.separator import Separator






def get_background_sound(a, b=os.path.join(os.path.dirname(os.path.abspath(__file__)),'vocal_and_back'),c:str =''):
    # 初始化 Spleeter 并指定分离模式（例如 2stems 表示人声和伴奏）
    
    
    separator = Separator('spleeter:2stems')
    

    # 输入文件路径
    audio_file = a

    # 输出文件夹路径
    output_path = b
    if not os.path.exists(output_path):
        os.mkdir(output_path)

    # 执行音频分离
    separator.separate_to_file(audio_file, output_path)

    print("人声分离完成！")
    # 返回背景声文件路径
    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    return os.path.join(output_path, base_name, c)



# 测试函数
if __name__ == "__main__":

    background_sound = get_background_sound(os.path.join(os.path.dirname(os.path.abspath(__file__)),'try.mp3'))
    print(f"背景声文件路径: {background_sound}")