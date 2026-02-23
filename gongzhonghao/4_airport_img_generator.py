"""
=============================================================
airport_img_generator.py 使用说明
=============================================================

功能概述:
--------
读取「机场小妙招.txt」中的文生图提示词，通过API4调用文生图API生成图片，
并保存为JPG格式到指定目录。
优先使用banana2 API，如果失败则使用备用API(seedream-4)。

输入要求:
--------
- 提示词文件: C:\\Users\\Administrator\\Desktop\\公众号文章\\txt\\机场小妙招.txt

输出内容:
--------
- imgoutput目录下的JPG图片文件

模块调用关系:
------------
- 调用: 无 (直接使用requests库)
- 被调用: 无

使用流程:
--------
1. 直接运行文件: python airport_img_generator.py
2. 程序自动提取[]中的提示词
3. 优先使用banana2生成图片
4. 失败则使用seedream-4生成
5. PNG转JPG并保存

注意事项:
--------
- 并发数为1
- 跳过已存在的图片文件
- 智能重试机制处理超时和速率限制

可调整参数:
----------
- MAX_WORKERS: 并发数量，设为1
- OUTPUT_DIR: 输出目录路径
- INPUT_FILE: 输入提示词文件路径
"""

import os
import re
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from PIL import Image
from io import BytesIO


MAX_WORKERS = 2
OUTPUT_DIR = r"C:\Users\Administrator\Desktop\公众号文章\imgoutput"
INPUT_FILE = r"C:\Users\Administrator\Desktop\公众号文章\txt\机场小妙招.txt"
API_KEY = "sk-RM8xwiFSD9UlpNjPO9ZGxvWy530T9xpsRbS07s4RNfBhXzHg"

API1_URL = "https://one.api4gpt.com/v1beta/models/gemini-3-pro-image-preview:generateContent"
API2_URL = "https://one.api4gpt.com/v1/images/generations"
API_TIMEOUT = 180
REQUEST_DELAY = 5


def extract_prompts_from_file(file_path: str) -> list:
    """提取文件中[]括号内的所有文本作为提示词"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pattern = r'\[(.*?)\]'
    prompts = re.findall(pattern, content, re.DOTALL)
    return [p.strip() for p in prompts if p.strip()]


def generate_filename(prompt: str) -> str:
    """从提示词中提取前10个字符作为文件名（不含符号）"""
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', prompt)
    filename = cleaned[:10] if len(cleaned) >= 10 else cleaned
    return filename


def call_api1(prompt: str) -> bytes:
    """调用banana2 API生成图片"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["Image"],
            "imageConfig": {"aspectRatio": "5:4", "imageSize": "2K"}
        }
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    response = requests.post(API1_URL, json=payload, headers=headers, timeout=API_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])
    if not parts:
        raise ValueError("API1返回parts为空")

    if 'text' in parts[0]:
        raise ValueError(f"API1错误: {parts[0]['text']}")

    if 'inlineData' in parts[0]:
        return base64.b64decode(parts[0]['inlineData']['data'])

    raise ValueError("API1未找到图片数据")


def call_api2(prompt: str) -> bytes:
    """调用seedream-4 API生成图片"""
    payload = {
        "prompt": prompt,
        "n": 1,
        "model": "seedream-4",
        "size": "1024x819"
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    response = requests.post(API2_URL, json=payload, headers=headers, timeout=API_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    image_url = data.get('data', [{}])[0].get('url')
    if not image_url:
        raise ValueError("API2未返回图片URL")

    img_response = requests.get(image_url, timeout=60)
    img_response.raise_for_status()
    return img_response.content


def download_and_save_image(url: str, save_path: str) -> None:
    """下载图片并保存"""
    img_response = requests.get(url, timeout=60)
    img_response.raise_for_status()

    img = Image.open(BytesIO(img_response.content))
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(save_path, 'JPEG', quality=95)


def convert_png_to_jpg(image_data: bytes) -> bytes:
    """将PNG图片数据转换为JPG格式"""
    img = Image.open(BytesIO(image_data))
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    output = BytesIO()
    img.save(output, format='JPEG', quality=95)
    return output.getvalue()


def process_single_prompt(prompt: str, output_dir: str) -> dict:
    """处理单个提示词：生成图片并保存为JPG"""
    filename = generate_filename(prompt)
    jpg_path = os.path.join(output_dir, f"{filename}.jpg")

    if os.path.exists(jpg_path):
        return {"status": "skipped", "filename": filename, "reason": "文件已存在"}

    try:
        print(f"  [API1] 尝试生成: {filename}")
        image_data = call_api1(prompt)
        jpg_data = convert_png_to_jpg(image_data)
        with open(jpg_path, 'wb') as f:
            f.write(jpg_data)
        time.sleep(REQUEST_DELAY)
        return {"status": "success", "filename": filename, "method": "API1(banana2)"}
    except Exception as e:
        print(f"  [API1] 失败: {e}")
        print(f"  [API2] 尝试备用API: {filename}")
        try:
            image_data = call_api2(prompt)
            jpg_data = convert_png_to_jpg(image_data)
            with open(jpg_path, 'wb') as f:
                f.write(jpg_data)
            time.sleep(REQUEST_DELAY)
            return {"status": "success", "filename": filename, "method": "API2(seedream-4)"}
        except Exception as e2:
            return {"status": "error", "filename": filename, "error": f"API1: {e}, API2: {e2}"}


def main():
    """主函数：提取提示词并生成图片"""
    print(f"正在读取提示词文件: {INPUT_FILE}")
    prompts = extract_prompts_from_file(INPUT_FILE)
    print(f"共提取到 {len(prompts)} 条提示词")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"并发数: {MAX_WORKERS}")
    print("-" * 50)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_prompt, prompt, OUTPUT_DIR): prompt for prompt in prompts}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["status"] == "success":
                method = result.get("method", "")
                print(f"✓ 生成成功: {result['filename']}.jpg [{method}]")
            elif result["status"] == "skipped":
                print(f"- 跳过: {result['filename']}.jpg ({result['reason']})")
            else:
                print(f"✗ 生成失败: {result['filename']} - {result.get('error', '未知错误')}")

    success_count = sum(1 for r in results if r["status"] == "success")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    error_count = sum(1 for r in results if r["status"] == "error")
    print("-" * 50)
    print(f"完成! 成功: {success_count}, 跳过: {skipped_count}, 失败: {error_count}")


if __name__ == '__main__':
    main()
