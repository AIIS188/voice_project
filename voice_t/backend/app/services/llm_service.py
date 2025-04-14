"""Large Language Model Service

This module provides functions for generating lecture content using large language models.
"""
import os
import json
import asyncio
import traceback
from typing import Dict, Any, List, Optional

# 使用真实的大模型API生成讲解内容
async def generate_lecture_content(slide_content: str) -> str:
    """
    使用大模型API生成幻灯片的讲解内容

    Args:
        slide_content: 幻灯片内容

    Returns:
        生成的讲解内容
    """
    try:
        # 导入LectureGenerator类
        from app.core.ppt_lecture import LectureGenerator

        # 创建LectureGenerator实例
        generator = LectureGenerator()

        # 构建提示词
        prompt = f"""你是一位优秀的教育工作者，擅长将复杂的知识点转化为流畅、生动、有趣的讲解。

        请根据以下幻灯片内容，生成一段流畅、自然、有逻辑性的讲解文本。
        讲解应该包含对幻灯片内容的解释、扩展和必要的背景知识，使听众能够更好地理解幻灯片内容。

        幻灯片内容：
        {slide_content}

        要求：
        1. 请直接给出讲解内容，不要包含任何前缀或格式标记
        2. 讲解应该流畅自然，如同你在课堂上对学生进行讲解
        3. 如果有备注信息，请将其融入到讲解中，而不是直接引用
        4. 请确保讲解内容丰富、有深度，但不要过于冗长
        """

        # 调用API生成讲解内容
        lecture_content = generator.generate_lecture_script(
            prompt,
            mode="combined",  # 使用合并模式
            output_format="md"  # 输出为Markdown格式
        )

        # 清理生成的内容，去除可能的格式标记
        lecture_content = lecture_content.strip()

        # 如果生成的内容为空，使用备选方案
        if not lecture_content:
            # 提取标题、内容和备注
            title = ""
            content = ""
            notes = ""

            for line in slide_content.split("\n"):
                if line.startswith("标题："):
                    title = line[3:].strip()
                elif line.startswith("内容："):
                    content = line[3:].strip()
                elif line.startswith("备注："):
                    notes = line[3:].strip()

            # 生成备选讲解内容
            lecture_content = ""

            if title:
                lecture_content += f"今天我们要讲的是\"{title}\"。\n\n"

            if content:
                lecture_content += f"{content}\n\n"

            if notes:
                lecture_content += f"{notes}\n\n"

            if not lecture_content:
                lecture_content = "这张幻灯片展示了重要的内容，请大家仔细观察和思考。"

        return lecture_content

    except Exception as e:
        print(f"使用大模型API生成讲解内容失败: {e}")
        traceback.print_exc()

        # 如果API调用失败，使用备选方案
        # 提取标题、内容和备注
        title = ""
        content = ""
        notes = ""

        for line in slide_content.split("\n"):
            if line.startswith("标题："):
                title = line[3:].strip()
            elif line.startswith("内容："):
                content = line[3:].strip()
            elif line.startswith("备注："):
                notes = line[3:].strip()

        # 生成备选讲解内容
        lecture_content = ""

        if title:
            lecture_content += f"今天我们要讲的是\"{title}\"。\n\n"

        if content:
            # 添加一些解释性文本
            lecture_content += f"{content}\n\n"

            # 根据内容添加一些额外的上下文
            if "王维" in content or "相思" in content:
                lecture_content += "王维是唐代著名诗人，他的《相思》是一首脍炙人口的爱情诗，以红豆寄托相思之情，表达了对远方恋人的思念。\n\n"
            elif "诸葛亮" in content:
                lecture_content += "诸葛亮，字孔明，号卧龙，是三国时期蜀汉丞相，杰出的政治家、军事家、外交家、文学家、发明家。他辅佐刘备建立蜀汉，并在刘备死后辅佐刘禅治国。\n\n"

        if notes:
            # 将备注融入讲解
            lecture_content += f"{notes}\n\n"

        # 如果没有内容，添加一个结论
        if not lecture_content:
            lecture_content = "这张幻灯片展示了重要的内容，请大家仔细观察和思考。"

        # 模拟异步处理
        await asyncio.sleep(0.1)

        return lecture_content
# Add this function to app/services/llm_service.py

async def generate_coherent_lecture(slides_content: List[Dict[str, Any]], course_name: str) -> Dict[str, str]:
    """
    Generate a coherent lecture script that maintains narrative flow across all slides.
    This creates a more natural speech synthesis experience with better transitions and context.
    
    Args:
        slides_content: List of slide information including title, content and notes
        course_name: Name of the course
        
    Returns:
        Dictionary mapping slide_id to enhanced lecture content
    """
    try:
        from app.core.config import settings
        import json
        import aiohttp
        
        # Format slides for model context
        slides_context = json.dumps(slides_content, ensure_ascii=False)
        
        # Prepare prompt for the LLM
        prompt = f"""
        你是一位教育专家和优秀的讲师。请基于以下幻灯片内容，为每一张幻灯片生成清晰、连贯且自然的讲解内容。
        
        课程名称: {course_name}
        
        幻灯片信息:
        {slides_context}
        
        请为每张幻灯片生成讲解内容，要求：
        1. 内容要连贯自然，像真人授课一样
        2. 适合语音合成朗读，句子长度适中
        3. 解释幻灯片中的概念和要点，但不要照搬幻灯片文字
        4. 加入恰当的过渡语句，使各幻灯片内容前后连贯
        5. 在重要概念处可以适当放慢语速，增加停顿
        6. 考虑到听众感受，使用适合口语的表达方式
        7. 保持中文语言习惯自然，避免生硬翻译感
        
        请输出JSON格式，键为幻灯片ID（数字形式），值为该幻灯片的讲解内容字符串。
        """
        
        # Call your LLM API - adjust based on your actual implementation
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.LLM_API_URL,
                json={
                    "prompt": prompt,
                    "max_tokens": 3000,
                    "temperature": 0.7
                },
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"}
            ) as response:
                result = await response.json()
                
                # Extract the generated text from the API response
                # Adjust this based on your LLM API's response format
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Try to parse the JSON response
                try:
                    # Find JSON in the response if surrounded by other text
                    import re
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1)
                    
                    coherent_lecture = json.loads(content)
                    return coherent_lecture
                except json.JSONDecodeError:
                    print("Failed to parse JSON response from LLM")
                    # Create a simple structured response as fallback
                    return {str(slide["slide_id"]): f"讲解内容：{slide['title']}" for slide in slides_content}
        
    except Exception as e:
        print(f"Error generating coherent lecture: {e}")
        import traceback
        traceback.print_exc()
        return {}  # Return empty dictionary on error
# 其他可能的API调用函数
async def call_openai_api(prompt: str) -> str:
    """Call OpenAI API to generate text"""
    # This would be implemented with actual API calls
    return "OpenAI generated content"

async def call_local_llm(prompt: str) -> str:
    """Call a local LLM to generate text"""
    # This would be implemented with actual API calls
    return "Local LLM generated content"
