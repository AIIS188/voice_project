import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

def find_original_ppt(file_id: str, original_filename: str, upload_dir: str) -> Optional[str]:
    """查找原始PPT文件"""
    # 首先在voiced_courseware目录中查找
    voiced_courseware_dir = os.path.join(upload_dir, "voiced_courseware")
    voiced_file_path = os.path.join(voiced_courseware_dir, f"{file_id}_{original_filename}")

    if os.path.exists(voiced_file_path):
        print(f"Found original file in voiced_courseware: {voiced_file_path}")
        return voiced_file_path

    # 然后在courseware目录中查找
    courseware_dir = os.path.join(upload_dir, "courseware")
    original_file_path = os.path.join(courseware_dir, f"{file_id}_{original_filename}")

    if os.path.exists(original_file_path):
        print(f"Found original file in courseware: {original_file_path}")
        # 复制到voiced_courseware目录
        os.makedirs(voiced_courseware_dir, exist_ok=True)
        try:
            shutil.copy2(original_file_path, voiced_file_path)
            print(f"Copied original file to voiced_courseware: {voiced_file_path}")
            return voiced_file_path
        except Exception as e:
            print(f"Failed to copy file to voiced_courseware: {e}")
            return original_file_path

    print(f"Original file not found: {original_file_path}")
    return None

def find_task_file(task_id: str, file_id: str, upload_dir: str) -> Optional[str]:
    """查找任务相关的文件"""
    # 首先在voiced_courseware目录中查找
    voiced_courseware_dir = os.path.join(upload_dir, "voiced_courseware")
    if os.path.exists(voiced_courseware_dir):
        print(f"Searching in voiced_courseware directory: {voiced_courseware_dir}")
        for filename in os.listdir(voiced_courseware_dir):
            if task_id in filename or file_id in filename:
                found_file_path = os.path.join(voiced_courseware_dir, filename)
                print(f"Found file: {found_file_path}")
                return found_file_path

    # 然后在courseware目录中查找
    courseware_dir = os.path.join(upload_dir, "courseware")
    if os.path.exists(courseware_dir):
        print(f"Searching in courseware directory: {courseware_dir}")
        for filename in os.listdir(courseware_dir):
            if task_id in filename or file_id in filename:
                found_file_path = os.path.join(courseware_dir, filename)
                print(f"Found file: {found_file_path}")
                return found_file_path

    print(f"Task file not found for task_id={task_id}, file_id={file_id}")
    return None

def create_audio_zip(output_dir: str, task_id: str, audio_files: List[str]) -> Optional[str]:
    """创建包含所有音频文件的ZIP包"""
    try:
        import zipfile

        # 创建ZIP文件路径
        zip_path = os.path.join(output_dir, f"{task_id}_audio_files.zip")

        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # 遍历所有音频文件
            for audio_file in audio_files:
                # 检查音频文件是否存在
                if os.path.exists(audio_file):
                    # 将音频文件添加到ZIP包中
                    zipf.write(audio_file, os.path.basename(audio_file))

        print(f"Successfully created audio ZIP file: {zip_path}")
        return zip_path
    except Exception as e:
        print(f"Failed to create audio ZIP file: {e}")
        return None

def find_audio_files(task_id: str, upload_dir: str) -> List[str]:
    """查找与任务相关的音频文件"""
    audio_files = []

    # 查找音频文件夹
    audio_dir = os.path.join(upload_dir, f"course_task_{task_id}_audio")
    if not os.path.exists(audio_dir):
        # 尝试查找类似的文件夹
        for dirname in os.listdir(upload_dir):
            if dirname.startswith("course_task_") and task_id in dirname and "audio" in dirname:
                audio_dir = os.path.join(upload_dir, dirname)
                break

    if os.path.exists(audio_dir):
        print(f"Found audio directory: {audio_dir}")
        # 收集所有WAV文件
        for filename in os.listdir(audio_dir):
            if filename.endswith(".wav"):
                audio_files.append(os.path.join(audio_dir, filename))

    print(f"Found {len(audio_files)} audio files")
    return audio_files

def insert_audio_to_ppt(ppt_file: str, audio_files: List[str], output_dir: str, task_id: str) -> Optional[str]:
    """将音频插入到PPT中"""
    try:
        # 检查文件是否存在
        if not os.path.exists(ppt_file):
            print(f"PPT file not found: {ppt_file}")
            return None

        # 尝试使用COM接口插入音频（仅在Windows上有效）
        try:
            import win32com.client

            # 使用PowerPoint COM接口打开演示文稿
            ppt_app = win32com.client.Dispatch("PowerPoint.Application")
            ppt_app.Visible = False  # 不显示PowerPoint窗口

            # 打开演示文稿
            abs_ppt_file = os.path.abspath(ppt_file)
            presentation = ppt_app.Presentations.Open(abs_ppt_file)

            # 获取幻灯片总数
            total_slides = len(presentation.Slides)
            print(f"Total slides: {total_slides}")

            # 对音频文件进行排序
            sorted_audio_files = sorted(audio_files)

            # 确保音频文件数量不超过幻灯片数量
            if len(sorted_audio_files) > total_slides:
                print(f"Warning: Audio files count ({len(sorted_audio_files)}) > slides count ({total_slides})")
                print("Extra audio files will be added to the last slide")

            # 遍历每个幻灯片，添加音频
            for i, audio_file in enumerate(sorted_audio_files):
                # 计算实际的幻灯片索引
                slide_index = min(i, total_slides - 1)

                # 获取对应的幻灯片
                slide = presentation.Slides[slide_index + 1]  # PowerPoint中幻灯片索引从1开始

                # 使用绝对路径
                abs_audio_file = os.path.abspath(audio_file)

                # 添加音频到幻灯片
                shape = slide.Shapes.AddMediaObject2(abs_audio_file)
                shape.AnimationSettings.PlaySettings.PlayOnEntry = True
                shape.AnimationSettings.PlaySettings.HideWhileNotPlaying = True

                # 调整大小和位置（小尺寸，不影响视觉）
                shape.Width = 1
                shape.Height = 1
                shape.Left = 0
                shape.Top = 0

            # 保存演示文稿
            presentation.Save()
            presentation.Close()
            ppt_app.Quit()

            print(f"Successfully inserted audio using COM interface: {ppt_file}")
            return ppt_file
        except ImportError:
            print("Failed to import win32com. Please install it with: pip install pywin32")
            # 如果无法使用COM接口，创建一个包含所有音频文件的ZIP包
            return create_audio_zip(output_dir, task_id, audio_files)
        except Exception as e:
            print(f"Failed to insert audio using COM interface: {e}")
            # 如果插入失败，创建一个包含所有音频文件的ZIP包
            return create_audio_zip(output_dir, task_id, audio_files)
    except Exception as e:
        print(f"Failed to insert audio to PPT: {e}")
        return None
