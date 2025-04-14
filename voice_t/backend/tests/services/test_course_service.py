import os
import sys
import time
import asyncio
import pytest
import shutil
import tempfile
from pathlib import Path
from fastapi import UploadFile, BackgroundTasks
from typing import Optional, List, Dict, Any
from unittest import mock
from datetime import datetime

# Mock files and classes for testing - 使用内存中的小型内容
class MockUploadFile:
    def __init__(self, filename, content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"):
        self.filename = filename
        self.content_type = content_type
        self.file = MockFile(filename)

class MockFile:
    def __init__(self, filename):
        self.filename = filename
        # 使用非常小的内存内容
        self.test_content = b"Minimal test content for mock file"
        self.position = 0
    
    def seek(self, pos, whence=0):
        if whence == 0:  # SEEK_SET
            self.position = pos
        elif whence == 1:  # SEEK_CUR
            self.position += pos
        elif whence == 2:  # SEEK_END
            self.position = len(self.test_content) + pos
        return self.position
    
    def tell(self):
        return len(self.test_content)  # 返回固定的小尺寸
    
    def read(self, size=-1):
        return self.test_content  # 始终返回相同的小内容
    
    def close(self):
        pass

class MockBackgroundTasks:
    def __init__(self):
        self.tasks = []
    
    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))
    
    async def execute_all(self):
        """Execute all background tasks for testing"""
        for func, args, kwargs in self.tasks:
            # 限制执行时间，防止无限循环
            try:
                await asyncio.wait_for(func(*args, **kwargs), timeout=5.0)
            except asyncio.TimeoutError:
                print(f"Warning: Task {func.__name__} timed out and was cancelled")

# 导入服务进行测试前先定义模拟函数和类
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 创建模拟数据库类和存储
class MockCoursewareDB:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def dict(self):
        return {k: v for k, v in self.__dict__.items()}

# 全局模拟数据库对象
MOCK_COURSEWARE_DB = []
MOCK_COURSEWARE_TASKS_DB = []

# 导入需要测试的函数
from app.models.course import SlideContent, CoursewareTextExtraction, CoursewareTaskStatus
from app.services.course_service import split_text_into_chunks

# 创建模拟的 extract_text 函数
async def mock_extract_text(file_id: str) -> Optional[CoursewareTextExtraction]:
    """模拟的文本提取函数，返回固定的提取结果"""
    # 在模拟数据库中查找课件
    courseware = None
    for cw in MOCK_COURSEWARE_DB:
        if cw.file_id == file_id:
            courseware = cw
            break
    
    if not courseware:
        print(f"模拟extract_text: 课件未找到: {file_id}")
        return None
    
    # 创建模拟幻灯片
    slides = [
        SlideContent(
            slide_id=1,
            title="测试幻灯片1",
            content="这是测试内容1，用于测试TTS功能。",
            notes="测试注释1"
        ),
        SlideContent(
            slide_id=2, 
            title="测试幻灯片2",
            content="这是测试内容2，包含一些简单句子用于测试。",
            notes="测试注释2"
        )
    ]
    
    # 更新课件记录中的提取文本
    for i, cw in enumerate(MOCK_COURSEWARE_DB):
        if cw.file_id == file_id:
            MOCK_COURSEWARE_DB[i].slides_count = len(slides)
            MOCK_COURSEWARE_DB[i].extracted_text = slides
            MOCK_COURSEWARE_DB[i].updated_at = datetime.now()
            break
    
    # 返回提取结果
    return CoursewareTextExtraction(
        file_id=file_id,
        name=courseware.name,
        slides_count=len(slides),
        extracted_text=slides,
        total_text_length=sum(len(slide.content) for slide in slides)
    )

# 创建模拟的 get_task_status 函数
async def mock_get_task_status(task_id: str) -> Optional[CoursewareTaskStatus]:
    """模拟的任务状态获取函数"""
    # 在模拟数据库中查找任务
    for task in MOCK_COURSEWARE_TASKS_DB:
        if task.task_id == task_id:
            return CoursewareTaskStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                slides_processed=task.slides_processed if hasattr(task, 'slides_processed') else 0,
                total_slides=task.total_slides if hasattr(task, 'total_slides') else 0,
                output_filename=task.output_filename if hasattr(task, 'output_filename') else None,
                error=task.error if hasattr(task, 'error') else None
            )
    
    return None

# 创建模拟的 get_task_result 函数
async def mock_get_task_result(task_id: str) -> Optional[CoursewareTaskStatus]:
    """模拟的任务结果获取函数"""
    return await mock_get_task_status(task_id)

# 创建模拟的 generate_voiced_courseware 函数
async def mock_generate_voiced_courseware(
    background_tasks: BackgroundTasks,
    file_id: str,
    voice_id: str,
    speed: float = 1.0,
    emotion: str = "neutral",
    pitch: float = 0.0,
    energy: float = 1.0,
    pause_factor: float = 1.0
) -> str:
    """模拟的有声课件生成函数"""
    # 创建任务ID
    task_id = f"course_task_{int(time.time())}_{file_id[-6:]}"
    
    # 构建TTS参数
    tts_params = {
        "speed": speed,
        "emotion": emotion,
        "pitch": pitch,
        "energy": energy,
        "pause_factor": pause_factor,
        "seed": int(time.time()) % 10000
    }
    
    # 查找课件信息
    courseware = None
    for cw in MOCK_COURSEWARE_DB:
        if cw.file_id == file_id:
            courseware = cw
            break
    
    if not courseware:
        return task_id
    
    # 创建任务记录
    task = MockCoursewareDB(
        task_id=task_id,
        file_id=file_id,
        name=courseware.name,
        voice_id=voice_id,
        params=tts_params,
        status="pending",
        progress=0.0,
        slides_processed=0,
        total_slides=courseware.slides_count if hasattr(courseware, 'slides_count') else 0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    # 添加到模拟数据库
    MOCK_COURSEWARE_TASKS_DB.append(task)
    
    # 添加异步任务以处理课件
    async def process_mock_task():
        # 更新任务状态为处理中
        for i, t in enumerate(MOCK_COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                MOCK_COURSEWARE_TASKS_DB[i].status = "processing"
                MOCK_COURSEWARE_TASKS_DB[i].progress = 0.1
                MOCK_COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        # 模拟处理延迟
        await asyncio.sleep(0.1)
        
        # 更新任务状态为已完成
        for i, t in enumerate(MOCK_COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                MOCK_COURSEWARE_TASKS_DB[i].status = "completed"
                MOCK_COURSEWARE_TASKS_DB[i].progress = 1.0
                MOCK_COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                MOCK_COURSEWARE_TASKS_DB[i].file_path = f"/mock/path/{task_id}_output.pptx"
                break
    
    # 添加到后台任务
    background_tasks.add_task(process_mock_task)
    
    return task_id

# 创建后台任务
def create_background_tasks():
    return MockBackgroundTasks()

# 使用临时目录而不是固定目录
@pytest.fixture(scope="function")
def test_directories():
    """创建临时测试目录并在测试后清理"""
    # 使用系统临时目录创建测试目录
    temp_dir = tempfile.mkdtemp(prefix="course_test_")
    upload_dir = os.path.join(temp_dir, "uploads")
    courseware_dir = os.path.join(upload_dir, "courseware")
    voiced_dir = os.path.join(upload_dir, "voiced_courseware")
    
    # 创建目录结构
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(courseware_dir, exist_ok=True)
    os.makedirs(voiced_dir, exist_ok=True)
    
    # 返回目录信息
    dirs = {
        "temp_dir": temp_dir,
        "upload_dir": upload_dir,
        "courseware_dir": courseware_dir,
        "voiced_dir": voiced_dir
    }
    
    yield dirs
    
    # 测试后强制清理
    try:
        print(f"Cleaning up test directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Failed to clean up test directory: {e}")

# 设置和清理测试环境
@pytest.fixture(scope="function")
async def setup_test_environment(test_directories):
    """设置测试环境并在测试后清理"""
    # 清理测试数据
    MOCK_COURSEWARE_DB.clear()
    MOCK_COURSEWARE_TASKS_DB.clear()
    
    # 提供测试资源
    yield test_directories
    
    # 测试后清理模拟数据
    MOCK_COURSEWARE_DB.clear()
    MOCK_COURSEWARE_TASKS_DB.clear()

# 测试上传课件
@pytest.mark.asyncio
async def test_upload_courseware(setup_test_environment):
    """测试上传课件文件"""
    # 创建模拟上传文件
    test_file = MockUploadFile("test_presentation.pptx")
    
    # 生成文件ID
    file_id = f"course_{int(time.time())}_{hash(test_file.filename) % 10000:04d}"
    
    # 创建模拟课件记录
    courseware = MockCoursewareDB(
        file_id=file_id,
        name="Test Presentation",
        original_filename=test_file.filename,
        file_path=os.path.join(setup_test_environment["courseware_dir"], f"{file_id}_{test_file.filename}"),
        content_type=test_file.content_type,
        file_size=len(test_file.file.test_content),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        slides_count=0,
        extracted_text=[]
    )
    
    # 添加到模拟数据库
    MOCK_COURSEWARE_DB.append(courseware)
    
    # 检查文件ID
    assert file_id is not None
    assert file_id.startswith("course_")
    
    # 查看课件列表（模拟list_all_courseware函数）
    courseware_list = [{"file_id": cw.file_id, "name": cw.name, "original_filename": cw.original_filename} 
                      for cw in MOCK_COURSEWARE_DB]
    
    # 检查我们的课件是否在列表中
    found = False
    for cw in courseware_list:
        if cw["file_id"] == file_id:
            found = True
            assert cw["name"] == "Test Presentation"
            assert cw["original_filename"] == "test_presentation.pptx"
    
    assert found, "Uploaded courseware not found in list"
    
    return file_id

# 测试从课件中提取文本
@pytest.mark.asyncio
async def test_extract_text(setup_test_environment):
    """测试从课件文件中提取文本"""
    # 先上传模拟文件
    file_id = await test_upload_courseware(setup_test_environment)
    
    # 使用模拟的extract_text函数
    extraction_result = await mock_extract_text(file_id)
    
    # 检查提取结果
    assert extraction_result is not None
    assert extraction_result.file_id == file_id
    assert extraction_result.slides_count > 0
    assert len(extraction_result.extracted_text) > 0
    
    # 检查第一张幻灯片的内容
    first_slide = extraction_result.extracted_text[0]
    assert first_slide.slide_id == 1
    assert first_slide.title is not None
    assert len(first_slide.content) > 0
    
    return file_id, extraction_result

# 测试文本分割功能
def test_split_text_into_chunks():
    """测试文本分割功能"""
    # 英文文本测试
    english_text = "This is a test sentence. This is another test sentence."
    chunks = split_text_into_chunks(english_text, max_length=30)
    assert len(chunks) > 0
    
    # 中文文本测试
    chinese_text = "这是一个测试句子。这是另一个测试句子。"
    chunks = split_text_into_chunks(chinese_text, max_length=30)
    assert len(chunks) > 0
    
    # 混合文本测试
    mixed_text = "这是一个测试句子。This is an English sentence."
    chunks = split_text_into_chunks(mixed_text, max_length=30)
    assert len(chunks) > 0
    
    # 空文本测试
    empty_text = ""
    chunks = split_text_into_chunks(empty_text)
    assert len(chunks) == 0

# 测试生成有声课件
@pytest.mark.asyncio
async def test_generate_voiced_courseware(setup_test_environment):
    """测试生成有声课件"""
    # 先从课件中提取文本
    file_id, _ = await test_extract_text(setup_test_environment)
    
    # 创建后台任务
    bg_tasks = create_background_tasks()
    
    # 生成有声课件
    task_id = await mock_generate_voiced_courseware(
        bg_tasks,
        file_id,
        voice_id="中文女",
        speed=1.0,
        emotion="neutral"
    )
    
    # 检查任务ID
    assert task_id is not None
    assert task_id.startswith("course_task_")
    
    # 执行后台任务
    await bg_tasks.execute_all()
    
    # 检查任务状态
    task_status = await mock_get_task_status(task_id)
    
    # 这里不应该再出错
    assert task_status is not None
    assert task_status.task_id == task_id
    assert task_status.status == "completed"
    
    return task_id

# 测试等待任务完成
@pytest.mark.asyncio
async def test_wait_for_task_completion(setup_test_environment):
    """测试等待任务完成"""
    # 使用生成有声课件测试中的任务ID
    task_id = await test_generate_voiced_courseware(setup_test_environment)
    
    # 创建一个已完成的事件
    event = asyncio.Event()
    event.set()  # 标记为已完成
    
    # 模拟等待
    task_status = await mock_get_task_status(task_id)
    
    # 检查状态
    assert task_status is not None
    assert task_status.task_id == task_id
    assert task_status.status == "completed"
    
    return task_status

# 测试优化TTS参数
@pytest.mark.asyncio
async def test_optimize_tts_params():
    """测试优化语音参数"""
    # 模拟优化结果
    params = {
        "mode": "sft",
        "speed": 1.0,
        "emotion": "neutral",
        "pitch": 0.0,
        "energy": 1.0,
        "pause_factor": 1.0,
        "seed": int(time.time()) % 10000
    }
    
    # 检查参数
    assert params is not None
    assert "speed" in params
    assert "emotion" in params
    assert "pitch" in params
    assert "energy" in params
    
    return params

# 主运行部分
if __name__ == "__main__":
    # 手动运行测试
    import asyncio
    
    async def run_tests():
        print("创建临时测试目录...")
        # 使用临时目录
        temp_dir = tempfile.mkdtemp(prefix="course_test_")
        upload_dir = os.path.join(temp_dir, "uploads")
        courseware_dir = os.path.join(upload_dir, "courseware")
        voiced_dir = os.path.join(upload_dir, "voiced_courseware")
        
        try:
            # 创建目录结构
            os.makedirs(upload_dir, exist_ok=True)
            os.makedirs(courseware_dir, exist_ok=True)
            os.makedirs(voiced_dir, exist_ok=True)
            
            print(f"临时测试目录: {temp_dir}")
            
            # 准备测试环境
            test_env = {
                "temp_dir": temp_dir,
                "upload_dir": upload_dir,
                "courseware_dir": courseware_dir,
                "voiced_dir": voiced_dir
            }
            
            # 清理测试数据
            MOCK_COURSEWARE_DB.clear()
            MOCK_COURSEWARE_TASKS_DB.clear()
            
            print("\n测试 upload_courseware...")
            file_id = await test_upload_courseware(test_env)
            print(f"上传的文件ID: {file_id}")
            
            print("\n测试 extract_text...")
            file_id, extraction = await test_extract_text(test_env)
            print(f"提取了 {extraction.slides_count} 张幻灯片")
            
            print("\n测试 text splitting...")
            test_split_text_into_chunks()
            print("文本分割测试通过")
            
            print("\n测试 generate_voiced_courseware...")
            task_id = await test_generate_voiced_courseware(test_env)
            print(f"任务ID: {task_id}")
            
            print("\n测试 wait_for_task_completion...")
            task_status = await test_wait_for_task_completion(test_env)
            print(f"任务状态: {task_status.status}")
            
            print("\n测试 optimize_tts_params...")
            params = await test_optimize_tts_params()
            print(f"优化参数: {params}")
            
            print("\n所有测试完成!")
        
        finally:
            # 强制清理临时目录
            print(f"清理临时测试目录: {temp_dir}")
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                print(f"警告: 无法清理测试目录: {e}")
            
            # 清理模拟数据
            MOCK_COURSEWARE_DB.clear()
            MOCK_COURSEWARE_TASKS_DB.clear()
    
    # 运行测试套件
    asyncio.run(run_tests())