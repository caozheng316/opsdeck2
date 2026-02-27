# -*- coding: utf-8 -*-
"""
Banana 图生图 API 工具 - 正方形海报批量处理
=============================================
功能：批量处理 -HB.jpg 文件，生成正方形(1:1)比例的 -ST.jpg 图片
"""

import os
import time
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

# API 配置
API_URL = "https://one.api4gpt.com/v1/images/edits"
API_KEY = "sk-xPVPKwOMF7XIlGmDIcWSND6mBZIpqPsIEvJ5hUVIIKDcEdsk"
MODEL = "nano-banana"
DEFAULT_SIZE = "1:1"
DEFAULT_PROMPT = "clean raw photography, keep the scenery in the reference image completely unchanged, cinematic depth of field, natural lighting, photorealistic, 8k resolution, --ar 1:1 --no text, chinese characters, english text, logo, qr code, barcode, typography, borders, frames, gradient overlays, color blocks, straight lines, graphic design elements, poster layout"
MAX_RETRY = 3  # API请求最大重试次数
MAX_WORKERS = 10  # 并发数


def get_folder_path():
    """获取文件夹路径"""
    print("\n" + "=" * 50)
    print("请输入文件夹路径：")
    print("=" * 50)

    user_input = input().strip()

    # 去除可能的引号
    if user_input.startswith('"') and user_input.endswith('"'):
        user_input = user_input[1:-1]
    if user_input.startswith("'") and user_input.endswith("'"):
        user_input = user_input[1:-1]

    if not os.path.isdir(user_input):
        print(f"错误：文件夹不存在 - {user_input}")
        return None

    return user_input


def collect_unprocessed_files(folder_path):
    """
    第一步：遍历目录，收集待处理的文件
    - 找出所有 -HB.jpg 后缀的文件
    - 检查是否存在对应的 -ST.jpg
    - 返回不存在 -ST.jpg 的文件列表
    """
    pending_files = []

    for filename in os.listdir(folder_path):
        # 检查是否为 -HB.jpg 文件（不区分大小写）
        if not filename.lower().endswith('-hb.jpg'):
            continue

        # 提取前缀（去掉 -HB.jpg 后缀）
        prefix = filename[:-7]  # 去掉 "-HB.jpg" (7个字符)

        # 检查对应的 -ST.jpg 是否存在
        st_filename = f"{prefix}-ST.jpg"
        st_filepath = os.path.join(folder_path, st_filename)

        if os.path.exists(st_filepath):
            print(f"跳过（已有ST）: {filename}")
            continue

        # 记录待处理文件
        hb_filepath = os.path.join(folder_path, filename)
        pending_files.append({
            'hb_path': hb_filepath,
            'prefix': prefix,
            'st_path': st_filepath
        })

    return pending_files


def call_banana_api(image_path, prompt, size):
    """调用 Banana API（带重试机制）"""
    headers = {
        'Authorization': f'Bearer {API_KEY}'
    }

    last_error = None
    filename = os.path.basename(image_path)

    for attempt in range(1, MAX_RETRY + 1):
        with open(image_path, 'rb') as f:
            files = {
                'image': (filename, f, 'image/jpeg')
            }
            data = {
                'prompt': prompt,
                'n': '1',
                'model': MODEL,
                'size': size
            }

            try:
                response = requests.post(
                    API_URL,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=300
                )

                if response.status_code == 200:
                    json_data = response.json()
                    if 'data' in json_data and len(json_data['data']) > 0:
                        return {'success': True, 'image_url': json_data['data'][0]['url']}
                    else:
                        last_error = f"API返回格式异常"
                else:
                    last_error = f"HTTP {response.status_code}"

            except Exception as e:
                last_error = str(e)[:50]

        # 重试前等待
        if attempt < MAX_RETRY:
            time.sleep(2)

    return {'success': False, 'error': f"重试{MAX_RETRY}次后失败: {last_error}"}


def download_and_convert_to_jpg(image_url, save_path):
    """
    下载图片并转换为JPG格式保存
    - 支持PNG等格式自动转换
    """
    response = requests.get(image_url, timeout=60)
    response.raise_for_status()

    # 使用PIL打开图片
    img = Image.open(BytesIO(response.content))

    # 转换为RGB（JPG不支持透明通道）
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # 保存为JPG
    img.save(save_path, 'JPEG', quality=95)

    return img.size


def process_single_item(item, index, total, prompt, size):
    """
    处理单个文件（用于并发）
    返回结果包含原始item信息，确保一一对应
    """
    hb_path = item['hb_path']
    st_path = item['st_path']
    filename = os.path.basename(hb_path)

    print(f"[{index}/{total}] 开始处理: {filename}")

    # 调用API
    result = call_banana_api(hb_path, prompt, size)

    if result['success']:
        try:
            # 下载并保存
            img_size = download_and_convert_to_jpg(result['image_url'], st_path)
            print(f"[{index}/{total}] 成功: {os.path.basename(st_path)} ({img_size[0]}x{img_size[1]})")
            return {
                'success': True,
                'item': item,
                'filename': filename
            }
        except Exception as e:
            print(f"[{index}/{total}] 保存失败: {filename} - {e}")
            return {
                'success': False,
                'item': item,
                'filename': filename,
                'error': str(e)
            }
    else:
        print(f"[{index}/{total}] API失败: {filename} - {result['error']}")
        return {
            'success': False,
            'item': item,
            'filename': filename,
            'error': result['error']
        }


def process_files_concurrent(pending_files, prompt, size):
    """
    第二步：并发处理文件列表
    """
    total = len(pending_files)
    success_count = 0
    fail_count = 0

    print(f"\n共 {total} 个文件待处理，并发数: {MAX_WORKERS}")
    print("-" * 50)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务，传入index用于显示进度
        futures = {
            executor.submit(process_single_item, item, i, total, prompt, size): item
            for i, item in enumerate(pending_files, 1)
        }

        # 收集结果
        for future in as_completed(futures):
            result = future.result()
            if result['success']:
                success_count += 1
            else:
                fail_count += 1

    return success_count, fail_count


def check_file_completeness(folder_path):
    """
    第三步：检查文件完整性
    - 检查每个前缀是否都有 -ST.jpg, -HB.jpg, -XQY.jpg 三个文件
    """
    # 收集所有前缀（从-HB.jpg文件中提取）
    prefixes = set()
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('-hb.jpg'):
            prefix = filename[:-7]  # 去掉 "-HB.jpg"
            prefixes.add(prefix)

    complete_count = 0
    incomplete_list = []

    for prefix in sorted(prefixes):
        hb_file = f"{prefix}-HB.jpg"
        st_file = f"{prefix}-ST.jpg"
        xqy_file = f"{prefix}-XQY.jpg"

        hb_exists = os.path.exists(os.path.join(folder_path, hb_file))
        st_exists = os.path.exists(os.path.join(folder_path, st_file))
        xqy_exists = os.path.exists(os.path.join(folder_path, xqy_file))

        if hb_exists and st_exists and xqy_exists:
            complete_count += 1
        else:
            missing = []
            if not hb_exists:
                missing.append("HB")
            if not st_exists:
                missing.append("ST")
            if not xqy_exists:
                missing.append("XQY")
            incomplete_list.append({
                'prefix': prefix,
                'missing': missing
            })

    return complete_count, len(prefixes), incomplete_list


def main():
    print("\n" + "=" * 50)
    print("    Banana 图生图 - 正方形海报批量处理")
    print("=" * 50)
    print(f"模型: {MODEL}")
    print(f"尺寸: {DEFAULT_SIZE}")
    print(f"并发数: {MAX_WORKERS}")

    # 获取文件夹路径
    folder_path = get_folder_path()
    if not folder_path:
        return

    print(f"\n已选择文件夹: {folder_path}")

    # 第一步：遍历收集待处理文件
    print("\n" + "-" * 50)
    print("正在扫描文件夹...")
    print("-" * 50)

    pending_files = collect_unprocessed_files(folder_path)

    if not pending_files:
        print("\n没有需要处理的文件（所有-HB.jpg都已有对应的-ST.jpg）")
        return

    # 显示统计
    print(f"\n待处理文件数: {len(pending_files)}")

    # 第二步：执行处理（使用默认提示词和尺寸）
    print("\n" + "=" * 50)
    print("开始处理...")
    print("=" * 50)

    success_count, fail_count = process_files_concurrent(
        pending_files, DEFAULT_PROMPT, DEFAULT_SIZE
    )

    # 显示结果
    print("\n" + "=" * 50)
    print("处理完成！")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print("=" * 50)

    # 第三步：检查文件完整性
    print("\n正在检查文件完整性...")
    print("-" * 50)

    complete_count, total_prefixes, incomplete_list = check_file_completeness(folder_path)

    if not incomplete_list:
        print(f"图片完整！共 {complete_count} 组，每组都有 HB、ST、XQY 三个文件。")
    else:
        print(f"发现 {len(incomplete_list)} 组不完整：")
        for item in incomplete_list:
            print(f"  {item['prefix']}: 缺少 {', '.join(item['missing'])}")
        print(f"\n完整: {complete_count}/{total_prefixes} 组")

    print("=" * 50)


if __name__ == "__main__":
    main()