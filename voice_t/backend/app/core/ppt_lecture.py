import os
import json
import argparse
from openai import OpenAI
from app.core.app_prompts import TEACHING_SCRIPT_PROMPTS


class LectureGenerator:
    def __init__(self, api_key=None, base_url=None, model="qwen-omni-turbo"):
        """
        初始化教学讲案生成器

        Args:
            api_key: API密钥
            base_url: API基础URL (例如DashScope的URL)
            model: 使用的模型名称
        """
        # 从环境变量或参数中获取API密钥
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "sk-9806a9e11e6a4a4daf6e588bbed24fcf")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL",
                                                   "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = model

        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # 获取提示词配置
        self.system_prompt = TEACHING_SCRIPT_PROMPTS["system_prompt"]
        self.content_analysis_prompt = TEACHING_SCRIPT_PROMPTS["content_analysis_prompt"]
        self.lecture_generation_prompt = TEACHING_SCRIPT_PROMPTS["lecture_generation_prompt"]
        self.single_slide_prompt = TEACHING_SCRIPT_PROMPTS["single_slide_prompt"]
        self.json_lecture_prompt = TEACHING_SCRIPT_PROMPTS["json_lecture_prompt"]

    def load_ppt_content(self, input_path):
        """加载PPT提取的内容，支持TXT和JSON格式"""
        content = None
        is_json = input_path.lower().endswith('.json')

        with open(input_path, 'r', encoding='utf-8') as f:
            if is_json:
                content = json.load(f)
            else:
                content = f.read()

        return content, is_json

    def analyze_content_structure(self, ppt_content):
        """分析PPT内容结构，确定如何组织讲案"""
        print("正在分析PPT内容结构...")

        # 准备分析提示词
        prompt = self.content_analysis_prompt.format(ppt_content=ppt_content)

        # 调用API进行内容分析，使用流式模式
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            stream=True  # 添加这个参数
        )

        # 从流式响应中获取完整内容
        analysis_result = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                analysis_result += chunk.choices[0].delta.content

        print("内容分析完成")
        return analysis_result

    def generate_lecture_script(self, ppt_content, mode="auto", analysis_result=None, output_format="md"):
        """
        生成教学讲案

        Args:
            ppt_content: PPT内容（字符串或JSON）
            mode: 生成模式：'auto'（自动决定）, 'combined'（合并讲解）, 'separate'（分开讲解）
            analysis_result: 内容分析结果（可选）
            output_format: 输出格式 ('md' 或 'json')

        Returns:
            生成的讲案内容
        """
        print(f"正在生成讲案，模式：{mode}，格式：{output_format}...")

        # 如果是JSON格式，需要转换为文本
        if isinstance(ppt_content, dict):
            text_content = ""
            for slide in ppt_content.get("slides", []):
                text_content += f"\n--- 幻灯片 {slide['slide_number']} ---\n"
                text_content += slide.get("text_content", "") + "\n"

                # 添加图片描述
                for image in slide.get("images", []):
                    text_content += f"【图片内容】: {image.get('description', '')}\n"

            ppt_content = text_content

        # 准备提示词
        if output_format == "json":
            # 使用含有特殊格式标记的json_lecture_prompt
            try:
                prompt = self.json_lecture_prompt.format(ppt_content=ppt_content)
            except KeyError as e:
                print(f"警告: 格式化JSON提示词时出错: {e}")
                # 使用更简单的提示词作为备选
                prompt = f"""请将以下PPT内容转换为JSON格式的教学讲案：

    {ppt_content}

    JSON格式要求:
    - 包含"讲案标题"、"开场白"和每张幻灯片的讲解
    - 每张幻灯片包含"讲解"、"互动环节"和"重点总结"字段
    - 最后一张幻灯片需要额外包含"结束语"字段
    - 所有字符串需要使用双引号
    - 文本换行使用\\n而不是实际换行
    """
        elif mode == "auto":
            # 如果没有提供分析结果，先进行分析
            if not analysis_result:
                analysis_result = self.analyze_content_structure(ppt_content)

            # 调用API生成完整讲案
            prompt = self.lecture_generation_prompt.format(ppt_content=ppt_content)

            # 在提示词中包含分析结果
            prompt += f"\n\n请根据以下内容结构分析生成讲案：\n\n{analysis_result}"

        elif mode == "combined":
            # 直接生成合并讲案
            prompt = self.lecture_generation_prompt.format(ppt_content=ppt_content)

        elif mode == "separate":
            # 分开生成每张幻灯片的讲解
            slides = ppt_content.split("--- 幻灯片")
            combined_script = ""

            for i, slide_content in enumerate(slides[1:], 1):  # 跳过第一个空元素
                slide_prompt = self.single_slide_prompt.format(
                    slide_content=f"--- 幻灯片{slide_content}"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": slide_prompt}
                    ],
                    temperature=0.7,
                    stream=True  # 添加这个参数
                )

                # 处理流式响应
                slide_script = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        slide_script += chunk.choices[0].delta.content

            return combined_script

        # 对于auto、combined和json模式，调用API生成讲案
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,  # 增加token限制以确保完整输出
            stream=True  # 添加这个参数
        )

        # 处理流式响应
        lecture_script = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                lecture_script += chunk.choices[0].delta.content
        print("讲案生成完成")
        return lecture_script

    def save_lecture_script(self, script, output_path, output_format="md"):
        """保存生成的讲案到文件"""
        if output_format == "json":
            try:
                # 尝试直接解析AI生成的JSON字符串
                import json
                import re

                # 首先移除可能的Markdown代码块标记
                if "```json" in script:
                    script = re.sub(r'```json\s*', '', script)
                if script.endswith("```"):
                    script = script.rsplit("```", 1)[0]

                # 移除可能的非JSON内容（如说明性文字）
                try:
                    # 尝试找到第一个有效的JSON对象
                    start_brace = script.find('{')
                    end_brace = script.rfind('}')
                    if start_brace >= 0 and end_brace >= 0:
                        script = script[start_brace:end_brace + 1]
                except:
                    # 如果上述处理失败，保持原样
                    pass

                script = script.strip()

                # 尝试解析JSON
                try:
                    lecture_data = json.loads(script)

                    # 添加元数据字段
                    lecture_data["metadata"] = {
                        "generation_time": None,  # 由调用方添加
                        "mode": None,  # 由调用方添加
                    }

                    # 验证JSON结构是否符合要求
                    required_keys = ["# 讲案标题", "## 开场白"]
                    slide_keys = [k for k in lecture_data.keys() if k.startswith("## 幻灯片")]

                    # 确保存在必要的字段
                    if not all(key in lecture_data for key in required_keys) or not slide_keys:
                        # 警告：生成的JSON缺少必要字段，将尝试修复

                        if "# 讲案标题" not in lecture_data:
                            lecture_data["# 讲案标题"] = "PPT教学讲案"

                        if "## 开场白" not in lecture_data:
                            lecture_data["## 开场白"] = "同学们好，今天我们开始学习新的内容。"

                        # 如果没有幻灯片数据，尝试从原始数据中提取
                        if not slide_keys:
                            # 创建至少一个幻灯片
                            lecture_data["## 幻灯片 1"] = {
                                "讲解": "幻灯片内容",
                                "互动环节": [],
                                "重点总结": [],
                                "结束语": "今天的课程到此结束，谢谢大家。"
                            }

                    # 检查每个幻灯片的结构
                    for key in slide_keys:
                        slide_data = lecture_data[key]

                        # 确保每个幻灯片都有必要的字段
                        if not isinstance(slide_data, dict):
                            lecture_data[key] = {
                                "讲解": str(slide_data),
                                "互动环节": [],
                                "重点总结": []
                            }
                            continue

                        if "讲解" not in slide_data:
                            slide_data["讲解"] = "幻灯片内容"

                        if "互动环节" not in slide_data:
                            slide_data["互动环节"] = []
                        elif not isinstance(slide_data["互动环节"], list):
                            slide_data["互动环节"] = [str(slide_data["互动环节"])]

                        if "重点总结" not in slide_data:
                            slide_data["重点总结"] = []
                        elif not isinstance(slide_data["重点总结"], list):
                            slide_data["重点总结"] = [str(slide_data["重点总结"])]

                    # 检查最后一张幻灯片是否有结束语
                    if slide_keys:
                        last_slide_key = sorted(slide_keys, key=lambda x: int(re.findall(r'\d+', x)[0]))[-1]
                        if "结束语" not in lecture_data[last_slide_key]:
                            lecture_data[last_slide_key]["结束语"] = "今天的课程到此结束，谢谢大家。"

                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}，将使用原始文本生成JSON结构")
                    # 如果无法解析JSON，则创建一个基本的JSON结构
                    lecture_data = {
                        "metadata": {
                            "generation_time": None,
                            "mode": None,
                        },
                        "# 讲案标题": "PPT教学讲案",
                        "## 开场白": "同学们好，今天我们开始学习新的内容。",
                        "## 幻灯片 1": {
                            "讲解": "AI生成的内容无法解析为标准JSON格式，这里提供了原始输出。",
                            "互动环节": [],
                            "重点总结": [],
                            "结束语": "今天的课程到此结束，谢谢大家。"
                        },
                        "content": script  # 保存原始内容以备参考
                    }

                # 保存为JSON
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(lecture_data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                # 保存JSON时出错
                # 发生异常时，将原始内容保存为文本文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(script)
        else:
            # 保存为纯文本或Markdown
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(script)

        # 讲案已保存

    def run(self, input_path, output_path=None, mode="auto", output_format="md"):
        """运行讲案生成流程"""
        import json
        import re

        # 如果未提供输出路径，则生成默认路径
        if not output_path:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = f"{base_name}_lecture_script.{output_format}"

        # 加载PPT内容
        ppt_content, is_json = self.load_ppt_content(input_path)

        # 如果内容太长，并且是JSON格式，则考虑分批处理
        if is_json and output_format == "json":
            try:
                # 提取幻灯片信息
                slides = ppt_content.get("slides", [])
                total_slides = len(slides)

                if total_slides > 10:  # 假设超过10张幻灯片就分批处理
                    # 内容较长，将分批处理

                    # 1. 先生成讲案标题和开场白
                    intro_content = {
                        "metadata": ppt_content.get("metadata", {}),
                        "slides": slides[:2]  # 只取前两张幻灯片用于生成简介
                    }

                    # 分析内容结构
                    if mode == "auto":
                        analysis_result = self.analyze_content_structure(
                            json.dumps(intro_content, ensure_ascii=False, indent=2)
                        )
                    else:
                        analysis_result = None

                    # 生成标题和开场白
                    print("1. 正在生成讲案标题和开场白...")
                    intro_script = self.generate_lecture_script(
                        intro_content,
                        mode=mode,
                        analysis_result=analysis_result,
                        output_format=output_format
                    )

                    # 解析生成的JSON
                    intro_json = None
                    try:
                        # 提取JSON部分
                        if "```json" in intro_script:
                            intro_script = re.sub(r'```json\s*', '', intro_script)
                        if intro_script.endswith("```"):
                            intro_script = intro_script.rsplit("```", 1)[0]

                        # 尝试找到第一个有效的JSON对象
                        start_brace = intro_script.find('{')
                        end_brace = intro_script.rfind('}')
                        if start_brace >= 0 and end_brace >= 0:
                            intro_script = intro_script[start_brace:end_brace + 1]

                        intro_json = json.loads(intro_script.strip())
                    except Exception as e:
                        print(f"解析开场白JSON失败: {e}")
                        intro_json = {
                            "# 讲案标题": "PPT教学讲案",
                            "## 开场白": "同学们好，今天我们开始学习新的内容。"
                        }

                    # 2. 分批处理每个幻灯片
                    batch_size = 5  # 每批处理的幻灯片数量
                    all_slides_data = {}

                    for i in range(0, total_slides, batch_size):
                        batch_end = min(i + batch_size, total_slides)
                        print(f"2. 正在处理第{i + 1}到第{batch_end}张幻灯片...")

                        # 准备这一批的内容
                        batch_content = {
                            "metadata": ppt_content.get("metadata", {}),
                            "slides": slides[i:batch_end]
                        }

                        # 生成这一批的讲稿
                        batch_script = self.generate_lecture_script(
                            batch_content,
                            mode="combined",  # 使用combined模式处理批次
                            output_format=output_format
                        )

                        # 解析JSON
                        try:
                            if "```json" in batch_script:
                                batch_script = re.sub(r'```json\s*', '', batch_script)
                            if batch_script.endswith("```"):
                                batch_script = batch_script.rsplit("```", 1)[0]

                            start_brace = batch_script.find('{')
                            end_brace = batch_script.rfind('}')
                            if start_brace >= 0 and end_brace >= 0:
                                batch_script = batch_script[start_brace:end_brace + 1]

                            batch_json = json.loads(batch_script.strip())

                            # 只提取幻灯片信息
                            for key, value in batch_json.items():
                                if key.startswith("## 幻灯片"):
                                    all_slides_data[key] = value
                        except Exception as e:
                            print(f"解析第{i + 1}-{batch_end}批幻灯片JSON失败: {e}")
                            # 为这批幻灯片创建默认数据
                            for j in range(i + 1, batch_end + 1):
                                all_slides_data[f"## 幻灯片 {j}"] = {
                                    "讲解": f"第{j}张幻灯片内容",
                                    "互动环节": [],
                                    "重点总结": []
                                }

                    # 3. 合并所有结果
                    merged_data = {**intro_json}

                    # 添加幻灯片数据
                    for key in sorted(all_slides_data.keys(), key=lambda x: int(re.findall(r'\d+', x)[0])):
                        merged_data[key] = all_slides_data[key]

                    # 确保最后一张幻灯片有结束语
                    last_slide_key = sorted(all_slides_data.keys(), key=lambda x: int(re.findall(r'\d+', x)[0]))[-1]
                    if "结束语" not in merged_data[last_slide_key]:
                        merged_data[last_slide_key]["结束语"] = "今天的课程到此结束，谢谢大家。"

                    # 添加元数据
                    merged_data["metadata"] = {
                        "generation_time": None,  # 由调用方添加
                        "mode": mode,
                    }

                    # 保存为JSON
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(merged_data, f, ensure_ascii=False, indent=2)

                    print("分批处理完成，已合并所有讲案内容")
                    return json.dumps(merged_data, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"分批处理失败，将尝试标准处理方式: {e}")
                # 如果分批处理失败，回退到标准处理

        # 标准处理流程
        # 如果是自动模式，先进行内容分析
        analysis_result = None
        if mode == "auto":
            analysis_result = self.analyze_content_structure(
                ppt_content if not is_json else json.dumps(ppt_content, ensure_ascii=False, indent=2)
            )

        # 生成讲案，传递output_format参数
        lecture_script = self.generate_lecture_script(
            ppt_content,
            mode=mode,
            analysis_result=analysis_result,
            output_format=output_format
        )

        # 保存讲案
        self.save_lecture_script(lecture_script, output_path, output_format=output_format)

        return lecture_script

# 当作为主程序运行时
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根据PPT内容生成教学讲案")
    parser.add_argument("input_file", help="PPT内容文件路径（TXT或JSON格式）")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--mode", "-m", choices=["auto", "combined", "separate"], default="auto",
                        help="生成模式：auto（自动决定）, combined（合并讲解）, separate（分开讲解）")
    parser.add_argument("--format", "-f", choices=["md", "json"], default="md",
                        help="输出格式：md（Markdown）或json（JSON结构化数据）")
    parser.add_argument("--api-key", help="API密钥")
    parser.add_argument("--api-url", help="API基础URL")
    parser.add_argument("--model", default="qwen-omni-turbo", help="使用的模型名称")

    args = parser.parse_args()

    generator = LectureGenerator(
        api_key=args.api_key,
        base_url=args.api_url,
        model=args.model
    )

    generator.run(
        args.input_file,
        output_path=args.output,
        mode=args.mode,
        output_format=args.format
    )