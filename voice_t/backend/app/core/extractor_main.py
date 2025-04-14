import os
import sys
import argparse
import datetime
from app.core.outppt  import PPTExtractor
from app.core.ppt_lecture import LectureGenerator


def run_pipeline(pptx_file, output_dir=None, temp_format="json", lecture_mode="auto",
                 output_format="json", api_key=None, api_url=None, model="qwen-omni-turbo",
                 save_intermediate=True):
    """
    运行完整的PPT到教学讲案转换流程

    Args:
        pptx_file: PPT文件路径
        output_dir: 输出目录
        temp_format: 中间文件格式 (txt 或 json)
        lecture_mode: 讲案生成模式 (auto, combined, separate)
        output_format: 输出格式 (md 或 json)
        api_key: API密钥
        api_url: API基础URL
        model: 使用的模型名称
        save_intermediate: 是否保存中间文件

    Returns:
        讲案文件路径
    """
    # 准备输出目录
    if not output_dir:
        output_dir = os.path.dirname(pptx_file) or "."
    os.makedirs(output_dir, exist_ok=True)

    # 文件名处理
    base_name = os.path.splitext(os.path.basename(pptx_file))[0]
    extracted_path = os.path.join(output_dir, f"{base_name}_extracted.{temp_format}")
    lecture_path = os.path.join(output_dir, f"{base_name}_lecture_script.{output_format}")

    # 开始处理PPT文件
    # 1. 提取PPT内容
    extractor = PPTExtractor(api_key=api_key, base_url=api_url, model=model)
    content, slide_count = extractor.run(
        pptx_file,
        output_path=extracted_path if save_intermediate else None,
        output_format=temp_format,
        save_images=True
    )

    # 如果不保存中间文件，则content变量中已包含内容
    if not save_intermediate:
        extracted_path = None

    # 2. 生成教学讲案
    generator = LectureGenerator(api_key=api_key, base_url=api_url, model=model)

    # 如果有保存中间文件，则从文件加载
    if extracted_path:
        lecture_script = generator.run(
            extracted_path,
            output_path=lecture_path,
            mode=lecture_mode,
            output_format=output_format
        )
    else:
        # 否则，直接使用内存中的内容
        ppt_content = content

        # 分析内容结构
        if lecture_mode == "auto":
            analysis_result = generator.analyze_content_structure(ppt_content)
        else:
            analysis_result = None

        # 生成讲案
        lecture_script = generator.generate_lecture_script(
            ppt_content,
            mode=lecture_mode,
            analysis_result=analysis_result,
            output_format=output_format  # 传递输出格式参数
        )

        # 保存讲案
        generator.save_lecture_script(lecture_script, lecture_path, output_format=output_format)

    # 如果输出是JSON格式，处理完整的元数据
    if output_format == "json" and os.path.exists(lecture_path):
        import json
        with open(lecture_path, 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)

        # 确保metadata字段存在
        if "metadata" not in lecture_data:
            lecture_data["metadata"] = {}

        # 添加元数据
        lecture_data["metadata"].update({
            "generation_time": datetime.datetime.now().isoformat(),
            "mode": lecture_mode,
            "source_ppt": os.path.basename(pptx_file),
            "model": model
        })

        # 重新保存JSON
        with open(lecture_path, 'w', encoding='utf-8') as f:
            json.dump(lecture_data, f, ensure_ascii=False, indent=2)

    # 处理完成
    # 返回结果
    return lecture_path, slide_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从PPT生成教学讲案的完整流程")
    parser.add_argument("--pptx_file", help="PPT文件路径", default="D:/2025服务外包竞赛/text1.pptx")
    parser.add_argument("--output-dir", "-o", help="输出目录", default="./output")
    parser.add_argument("--temp-format", "-tf", choices=["txt", "json"], default="json",
                        help="中间文件格式 (txt 或 json)")
    parser.add_argument("--lecture-mode", "-m", choices=["auto", "combined", "separate"], default="auto",
                        help="讲案生成模式：auto（自动决定）, combined（合并讲解）, separate（分开讲解）")
    parser.add_argument("--output-format", "-f", choices=["md", "json"], default="json",
                        help="输出格式：md（Markdown）或json（JSON结构化数据）")
    parser.add_argument("--api-key", help="API密钥", default="sk-9806a9e11e6a4a4daf6e588bbed24fcf")
    parser.add_argument("--api-url", help="API基础URL", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--model", default="qwen-omni-turbo", help="使用的模型名称")
    parser.add_argument("--no-save-temp", action="store_true", help="不保存中间文件")

    args = parser.parse_args()

    lecture_path, slide_count = run_pipeline(
        args.pptx_file,
        output_dir=args.output_dir,
        temp_format=args.temp_format,
        lecture_mode=args.lecture_mode,
        output_format=args.output_format,
        api_key=args.api_key,
        api_url=args.api_url,
        model=args.model,
        save_intermediate=not args.no_save_temp
    )
    # 处理完成