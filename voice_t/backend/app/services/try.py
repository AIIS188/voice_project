#!/usr/bin/env python
"""
Simplified test script for extract_from_ppt function
"""
import os
import sys
import json
import re
from pathlib import Path
from pprint import pprint

# Add the necessary paths
current_dir = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(ROOT_DIR)

# Import necessary model class
# If you don't have access to the original SlideContent class, create a simple version
class SlideContent:
    def __init__(self, slide_id, title, content, notes):
        self.slide_id = slide_id
        self.title = title
        self.content = content
        self.notes = notes

# Import the required modules for extract_from_ppt
try:
    # Try to import from app.core modules
    from app.core.extractor_main import run_pipeline
except ImportError:
    print("Warning: Could not import run_pipeline. Using mock version for testing.")
    # Mock version for testing
    def run_pipeline(pptx_file, output_dir, temp_format, lecture_mode, output_format, save_intermediate):
        """Mock function that returns a sample lecture path and slide count"""
        # Create a sample JSON file
        lecture_path = os.path.join(output_dir, "sample_lecture.json")
        with open(lecture_path, 'w', encoding='utf-8') as f:
            json.dump({
                "# 讲案标题": "示例讲案",
                "## 开场白": "欢迎大家参加本次演讲。",
                "## 幻灯片1": {
                    "讲解": "这是第一张幻灯片的内容。",
                    "重点总结": ["要点1", "要点2"]
                },
                "## 幻灯片2": {
                    "讲解": "这是第二张幻灯片的内容。",
                    "重点总结": ["要点A", "要点B"],
                    "互动环节": ["提问1", "讨论2"]
                }
            }, f, ensure_ascii=False, indent=2)
        return lecture_path, 2

# Copy the extract_from_ppt function from course_service.py
def extract_from_ppt(file_path):
    """
    从ppt提取内容、获得讲案。这个函数使用main.py中的run_pipeline来处理PPT文件。
    
    Args:
        file_path: PPT文件路径
        
    Returns:
        slides_count: 幻灯片数量
        slides: SlideContent对象列表
    """
    print(f"开始从PPT文件提取内容: {file_path}")
    
    # 创建临时输出目录
    temp_dir = os.path.join(os.path.dirname(file_path), "temp_extraction")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 运行PPT处理流程，得到讲案文件路径和幻灯片数量
        lecture_path, slides_count = run_pipeline(
            pptx_file=file_path,
            output_dir=temp_dir,
            temp_format="json",
            lecture_mode="auto",
            output_format="json",
            save_intermediate=True
        )
        
        # 读取生成的讲案文件
        with open(lecture_path, 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)
        
        # 创建SlideContent对象列表
        slides = []
        
        # 处理讲案数据
        lecture_title = lecture_data.get("# 讲案标题", "")
        opening = lecture_data.get("## 开场白", "")
        
        # 获取所有幻灯片键
        slide_keys = [key for key in lecture_data.keys() if key.startswith("## 幻灯片")]
        slide_keys.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0)
        
        for key in slide_keys:
            try:
                # 提取幻灯片编号
                slide_id = int(re.search(r'(\d+)', key).group(1))
                slide_data = lecture_data[key]
                
                # 提取幻灯片内容
                if isinstance(slide_data, dict):
                    # 提取讲解内容
                    content = slide_data.get("讲解", "")
                    
                    # 提取重点总结并格式化为笔记
                    notes = ""
                    key_points = slide_data.get("重点总结", [])
                    if key_points:
                        notes = "重点总结：\n" + "\n".join([f"- {point}" for point in key_points])
                    
                    # 如果有互动环节，添加到笔记中
                    interactions = slide_data.get("互动环节", [])
                    if interactions:
                        if notes:
                            notes += "\n\n"
                        notes += "互动环节：\n" + "\n".join([f"- {item}" for item in interactions])
                    
                    # 如果是最后一张幻灯片，添加结束语
                    if "结束语" in slide_data:
                        if notes:
                            notes += "\n\n"
                        notes += f"结束语：\n{slide_data['结束语']}"
                    
                    # 尝试提取标题（使用内容的第一行或标题字段）
                    title = ""
                    if content:
                        lines = content.split('\n')
                        if lines:
                            title = lines[0].strip()
                            # 如果第一行很短，可能是标题
                            if len(title) < 50:
                                content = '\n'.join(lines[1:]).strip()
                    
                    # 创建SlideContent对象
                    slide_content = SlideContent(
                        slide_id=slide_id,
                        title=title,
                        content=content,
                        notes=notes
                    )
                    
                    slides.append(slide_content)
                else:
                    # 处理滑动数据是字符串的情况
                    print(f"警告: 幻灯片 {key} 数据格式不正确，跳过处理")
                
            except Exception as e:
                print(f"处理幻灯片 {key} 时出错: {e}")
                import traceback
                traceback.print_exc()
        
        # 按幻灯片编号排序
        slides.sort(key=lambda x: x.slide_id)
        
        # 如果是第一张幻灯片，添加开场白到内容中
        if slides and opening:
            first_slide = slides[0]
            first_slide.content = f"{opening}\n\n{first_slide.content}"
        
        # 如果没有幻灯片内容（可能是解析失败），创建一个默认的幻灯片
        if not slides:
            default_slide = SlideContent(
                slide_id=1,
                title=lecture_title if lecture_title else "课件内容",
                content="无法提取具体幻灯片内容，请查看原始PPT文件。",
                notes=""
            )
            slides.append(default_slide)
        
        return slides_count, slides
        
    except Exception as e:
        print(f"提取PPT内容时出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 创建一个默认幻灯片
        default_slide = SlideContent(
            slide_id=1,
            title="处理错误",
            content=f"处理PPT文件时出错: {str(e)}",
            notes=""
        )
        
        return 1, [default_slide]

def test_extract_from_ppt(ppt_file_path):
    """
    Test the extract_from_ppt function with a given PowerPoint file.
    
    Args:
        ppt_file_path: Path to the PowerPoint file
    """
    print(f"\n{'='*50}")
    print(f"Testing extract_from_ppt with file: {ppt_file_path}")
    print(f"{'='*50}\n")
    
    # Check if the file exists
    if not os.path.exists(ppt_file_path):
        print(f"Error: The file {ppt_file_path} does not exist.")
        return
    
    # Print file info
    file_size = os.path.getsize(ppt_file_path)
    print(f"File size: {file_size / 1024:.2f} KB")
    
    # Call the function
    print("\nExtracting content from PowerPoint file...")
    try:
        slides_count, extracted_slides = extract_from_ppt(ppt_file_path)
        
        # Print the results
        print(f"\nExtraction completed successfully!")
        print(f"Number of slides: {slides_count}")
        print(f"Number of extracted slide contents: {len(extracted_slides)}")
        
        # Print details of each slide
        print("\nExtracted content summary:")
        print(f"{'-'*50}")
        
        total_content_length = 0
        for i, slide in enumerate(extracted_slides, 1):
            content_length = len(slide.content)
            total_content_length += content_length
            has_notes = bool(slide.notes)
            
            print(f"Slide {i} (ID: {slide.slide_id}):")
            print(f"  Title: {slide.title[:50]}{'...' if len(slide.title) > 50 else ''}")
            print(f"  Content length: {content_length} characters")
            print(f"  Has notes: {has_notes}")
            print(f"{'-'*50}")
        
        print(f"\nTotal content length: {total_content_length} characters")
        
        # Save the extracted content to a JSON file for further analysis
        output_dir = os.path.dirname(ppt_file_path)
        output_file = os.path.join(output_dir, f"{Path(ppt_file_path).stem}_extracted.json")
        
        # Convert slide objects to dictionaries
        slides_data = [
            {
                "slide_id": slide.slide_id,
                "title": slide.title,
                "content": slide.content,
                "notes": slide.notes
            }
            for slide in extracted_slides
        ]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    "file_path": ppt_file_path,
                    "slides_count": slides_count,
                    "extracted_slides_count": len(extracted_slides),
                    "total_content_length": total_content_length,
                    "slides": slides_data
                }, 
                f, 
                ensure_ascii=False, 
                indent=2
            )
        
        print(f"\nExtracted content saved to: {output_file}")
        
        # Print the first slide content as a sample
        if extracted_slides:
            print("\nSample content from first slide:")
            print(f"{'-'*50}")
            print(f"Title: {extracted_slides[0].title}")
            print(f"Content: \n{extracted_slides[0].content[:500]}{'...' if len(extracted_slides[0].content) > 500 else ''}")
            if extracted_slides[0].notes:
                print(f"\nNotes: \n{extracted_slides[0].notes[:300]}{'...' if len(extracted_slides[0].notes) > 300 else ''}")
            print(f"{'-'*50}")
            
        return slides_count, extracted_slides
    
    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    # Use the provided PowerPoint file path
    ppt_file_path = r"d:\2025服务外包竞赛\text1.pptx"
    
    # Check if the path was provided as a command line argument
    if len(sys.argv) > 1:
        ppt_file_path = sys.argv[1]
    
    # Run the test
    test_extract_from_ppt(ppt_file_path)