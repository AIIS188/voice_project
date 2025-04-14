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

def insert_audio_with_com(ppt_file: str, audio_files_by_slide: Dict[int, List[str]]) -> bool:
    """使用COM接口插入音频"""
    try:
        import win32com.client

        # 使用PowerPoint COM接口打开演示文稿
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
        # 不设置 Visible 属性，避免出现 "Application.Visible : Invalid request" 错误
        # ppt_app.Visible = False

        # 打开演示文稿
        abs_ppt_file = os.path.abspath(ppt_file)
        presentation = ppt_app.Presentations.Open(abs_ppt_file)

        # 遍历每个幻灯片，添加音频
        for slide_index, audio_files in audio_files_by_slide.items():
            # 确保幻灯片索引在有效范围内
            if slide_index < len(presentation.Slides):
                slide = presentation.Slides[slide_index + 1]  # PowerPoint中幻灯片索引从1开始

                # 遍历该幻灯片的所有音频文件
                for i, audio_file in enumerate(audio_files):
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

                    # 添加可视化的播放按钮
                    try:
                        # 添加圆角矩形按钮
                        button = slide.Shapes.AddShape(13, 0, 0, 72, 36)  # 13是圆角矩形

                        # 设置按钮外观
                        button.Fill.ForeColor.RGB = 0x0078D7  # 蓝色
                        button.Line.ForeColor.RGB = 0x005AAA  # 深蓝色
                        button.Line.Weight = 1

                        # 添加文本
                        button.TextFrame.TextRange.Text = f"播放音频 {i+1}"
                        button.TextFrame.TextRange.Font.Color.RGB = 0xFFFFFF  # 白色
                        button.TextFrame.TextRange.Font.Bold = True

                        # 将按钮放在幻灯片右下角
                        slide_width = presentation.PageSetup.SlideWidth
                        slide_height = presentation.PageSetup.SlideHeight
                        button.Left = slide_width - 108  # 右边距离108点
                        button.Top = slide_height - 108  # 下边距离108点

                        # 添加点击操作
                        button.ActionSettings(1).Action = 7  # ppActionRunProgram
                        button.ActionSettings(1).Run = abs_audio_file
                    except Exception as e:
                        print(f"Failed to add play button with COM: {e}")

        # 保存演示文稿
        presentation.Save()
        presentation.Close()
        ppt_app.Quit()

        print(f"Successfully inserted audio using COM interface: {ppt_file}")
        return True
    except ImportError:
        print("Failed to import win32com. Please install it with: pip install pywin32")
        return False
    except Exception as e:
        print(f"Failed to insert audio using COM interface: {e}")
        return False

def insert_audio_with_python_pptx(ppt_file: str, audio_files_by_slide: Dict[int, List[str]]) -> bool:
    """使用python-pptx插入音频"""
    try:
        from pptx import Presentation
        from pptx.util import Inches

        # 加载演示文稿
        prs = Presentation(ppt_file)

        print(f"Total slides in PPT: {len(prs.slides)}")
        print(f"Audio files by slide: {audio_files_by_slide}")

        # 遍历每个幻灯片，添加音频
        for slide_index, audio_files in audio_files_by_slide.items():
            # 确保幻灯片索引在有效范围内
            if slide_index < len(prs.slides):
                slide = prs.slides[slide_index]
                print(f"Processing slide {slide_index+1} with {len(audio_files)} audio files")

                # 遍历该幻灯片的所有音频文件
                for i, audio_file in enumerate(audio_files):
                    # 使用绝对路径
                    abs_audio_file = os.path.abspath(audio_file)
                    print(f"Adding audio file {i+1}: {abs_audio_file}")

                    # 计算每个音频文件的位置，从右上角开始排列
                    # 每行最多放3个按钮
                    button_width = 1.2  # 按钮宽度（英寸）
                    button_height = 0.5  # 按钮高度（英寸）
                    buttons_per_row = 3  # 每行按钮数

                    # 计算行和列
                    row = i // buttons_per_row
                    col = i % buttons_per_row

                    # 计算位置
                    left = Inches(prs.slide_width.inches - (col + 1) * button_width - 0.2)
                    top = Inches(row * button_height + 0.2)

                    # 添加音频到幻灯片
                    try:
                        # 直接使用简化的API，不设置poster_frame和其他参数
                        movie = slide.shapes.add_movie(
                            abs_audio_file,
                            left=left,
                            top=top,
                            width=Inches(button_width),
                            height=Inches(button_height)
                        )
                        print(f"Successfully added audio to slide {slide_index+1}")
                    except Exception as e:
                        print(f"Failed to add audio to slide {slide_index+1}: {e}")
                        import traceback
                        traceback.print_exc()

        # 保存修改后的演示文稿
        prs.save(ppt_file)

        print(f"Successfully inserted audio using python-pptx: {ppt_file}")
        return True
    except ImportError:
        print("Failed to import python-pptx. Please install it with: pip install python-pptx")
        return False
    except Exception as e:
        print(f"Failed to insert audio using python-pptx: {e}")
        return False

def create_audio_zip(output_dir: str, task_id: str, audio_files: List[str]) -> Optional[str]:
    """创建包含所有音频文件的ZIP包"""
    try:
        import zipfile

        # 创建ZIP文件路径
        zip_path = os.path.join(output_dir, f"{task_id}_audio_files.zip")

        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # 使用字典跟踪已添加的文件名
            added_filenames = {}

            # 遍历所有音频文件
            for i, audio_file in enumerate(audio_files):
                # 检查音频文件是否存在
                if os.path.exists(audio_file):
                    # 获取基本文件名
                    base_filename = os.path.basename(audio_file)

                    # 如果文件名已存在，添加唯一的后缀
                    if base_filename in added_filenames:
                        # 获取文件名和扩展名
                        name, ext = os.path.splitext(base_filename)
                        # 创建新的唯一文件名
                        unique_filename = f"{name}_{i}{ext}"
                        print(f"Renaming duplicate file {base_filename} to {unique_filename}")
                    else:
                        unique_filename = base_filename
                        added_filenames[base_filename] = True

                    # 将音频文件添加到ZIP包中
                    zipf.write(audio_file, unique_filename)

        print(f"Successfully created audio ZIP file: {zip_path}")
        return zip_path
    except Exception as e:
        print(f"Failed to create audio ZIP file: {e}")
        return None

def handle_extra_audio_tasks(tts_tasks: List[Dict[str, Any]], total_slides: int) -> List[Dict[str, Any]]:
    """处理额外的音频任务"""
    if not tts_tasks or total_slides <= 0:
        return tts_tasks

    if len(tts_tasks) <= total_slides:
        return tts_tasks

    print(f"Warning: Audio tasks count ({len(tts_tasks)}) > slides count ({total_slides})")
    print("Will merge extra audio tasks to the last slide")

    # 将多余的音频任务合并到最后一张幻灯片
    last_slide_index = total_slides - 1

    # 确保有效的幻灯片数量
    valid_tasks = []
    for task in tts_tasks:
        if task["slide_id"] < total_slides:
            valid_tasks.append(task)
        else:
            # 如果幻灯片ID超出范围，将其分配给最后一张幻灯片
            if not valid_tasks or valid_tasks[-1]["slide_id"] != last_slide_index:
                # 创建一个新的任务给最后一张幻灯片
                last_task = {
                    "slide_id": last_slide_index,
                    "chunks": [],
                    "total_duration": 0
                }
                valid_tasks.append(last_task)

            # 将超出范围的幻灯片的音频块添加到最后一张幻灯片
            for chunk in task["chunks"]:
                valid_tasks[-1]["chunks"].append(chunk)

    # 确保最后一张幻灯片存在
    if valid_tasks and valid_tasks[-1]["slide_id"] == last_slide_index:
        # 更新最后一张幻灯片的总时长
        valid_tasks[-1]["total_duration"] = sum(chunk.get("duration", 0) for chunk in valid_tasks[-1]["chunks"])

    # 按幻灯片ID排序
    valid_tasks.sort(key=lambda x: x["slide_id"])

    return valid_tasks

def collect_audio_files_by_slide(tts_tasks: List[Dict[str, Any]], total_slides: int) -> Dict[int, List[str]]:
    """收集每个幻灯片的音频文件"""
    audio_files_by_slide = {}
    all_audio_files = []

    # 处理额外的音频任务
    tts_tasks = handle_extra_audio_tasks(tts_tasks, total_slides)

    print(f"After handling extra tasks: {len(tts_tasks)} tasks for {total_slides} slides")

    # 收集每个幻灯片的音频文件
    for slide_task in tts_tasks:
        slide_id = slide_task["slide_id"]

        # 计算实际的幻灯片索引
        # 如果slide_id超出范围，使用可用的最后一张幻灯片
        actual_slide_index = min(slide_id, total_slides - 1)

        print(f"Mapping slide_id {slide_id} to actual_slide_index {actual_slide_index}")

        # 初始化该幻灯片的音频文件列表
        if actual_slide_index not in audio_files_by_slide:
            audio_files_by_slide[actual_slide_index] = []

        # 收集该幻灯片的所有音频文件
        for chunk in slide_task["chunks"]:
            audio_file = chunk.get("audio_file")

            # 检查音频文件是否存在
            if audio_file and os.path.exists(audio_file):
                # 将音频文件添加到列表中
                audio_files_by_slide[actual_slide_index].append(audio_file)
                print(f"Added audio file {audio_file} to slide {actual_slide_index+1}")
                all_audio_files.append(audio_file)

    return audio_files_by_slide, all_audio_files

def insert_audio_to_ppt(ppt_file: str, tts_tasks: List[Dict[str, Any]], output_dir: str, task_id: str) -> Optional[str]:
    """将音频插入到PPT中"""
    try:
        # 检查文件是否存在
        if not os.path.exists(ppt_file):
            print(f"PPT file not found: {ppt_file}")
            return None

        # 获取幻灯片总数
        try:
            from pptx import Presentation
            prs = Presentation(ppt_file)
            total_slides = len(prs.slides)
            print(f"Total slides: {total_slides}")
        except Exception as e:
            print(f"Failed to get slides count: {e}")
            return None

        # 收集每个幻灯片的音频文件
        audio_files_by_slide, all_audio_files = collect_audio_files_by_slide(tts_tasks, total_slides)

        # 直接使用python-pptx插入音频
        try:
            if insert_audio_with_python_pptx(ppt_file, audio_files_by_slide):
                print(f"Successfully inserted audio using python-pptx: {ppt_file}")
                return ppt_file
        except Exception as e:
            print(f"Failed to insert audio using python-pptx: {e}")
            import traceback
            traceback.print_exc()

        # 如果失败，创建音频ZIP包
        zip_path = create_audio_zip(output_dir, task_id, all_audio_files)
        if zip_path:
            print(f"Successfully created audio ZIP file: {zip_path}")
            return zip_path

        return None
    except Exception as e:
        print(f"Failed to insert audio to PPT: {e}")
        return None
