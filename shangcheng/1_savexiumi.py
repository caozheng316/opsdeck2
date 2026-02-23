"""
秀米网页处理工具 - 智能完整页面截图解决方案
基于Playwright的网页自动化处理脚本，采用智能分段截图技术突破32767像素限制
支持标题提取、二维码处理、海报保存等功能

核心特性：
- 🔥 智能检测页面大小，自动选择最优截图方案
- 🚀 突破32767像素限制，支持超长页面完整截图
- 🎯 最终只输出一张完整的高质量图片（永不分割）
- 💯 JPEG格式保存（质量100，不压缩）
- 🧠 智能标题提取（多级降级策略）
- 📱 二维码识别与生成
- 📊 结构化数据持久化（savexiumi_config.json）
- 🛠️ 灵活配置：支持默认路径或手动输入
- 🔄 智能批量处理：支持三种批量处理场景

技术亮点：
- 标准页面：直接使用full_page=True（最快最简单）
- 超长页面：固定区间分段截图 + 无重叠拼接（突破限制）
- 全自动处理：用户界面保持简洁，后台智能决策
- 高质量保证：最终图片无拼接痕迹，保持原始清晰度
- 配置友好：常量区域可预设存储路径，也可手动输入
- 智能批量：自动识别处理场景并相应处理

配置说明：
在常量配置区修改 DEFAULT_STORAGE_PATH 可设置默认存储路径
留空则每次运行时手动输入路径

批量模式支持的三种处理场景：
1. 目录批量处理：输入目录路径，自动处理目录中所有图片
2. 图片链接批量：粘贴多个图片链接，批量提取二维码
3. 网页链接批量：粘贴多个网页链接，批量截图处理
"""

# --- 1. 模块引入区 ---
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import qrcode
from PIL import Image, ImageGrab
from playwright.async_api import async_playwright
import pyperclip
import pyzbar.pyzbar as pyzbar

# --- 2. 常量配置区 ---
# 省份映射字典
PROVINCE_MAPPING = {
    "黑吉辽": "HJL",
    "山东": "SD",
    "西藏": "XZ",
    "新疆": "XJ",
    "内蒙古": "NM",
    "青甘宁": "QGN",
    "云南": "YN",
    "福建": "FJ",
    "粤港澳": "YGA",
    "湖南": "HN",
    "海南": "HI",
    "江西": "JX",
    "贵州": "GZ",
    "川渝": "CY",
    "江浙沪": "JZH",
    "河北": "HB",
    "河南": "HE",
    "京津冀": "JJJ",
    "陕西": "SN",
    "山西": "SX",
    "安徽": "AH"
}

# 支持的图片格式
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

# 设备视口配置 - 桌面浏览器模式
DEVICE_VIEWPORT = {
    "width": 1170,  # 桌面浏览器宽度
    "height": 1000,  # 桌面浏览器高度
    "device_scale_factor": 1,  # 桌面设备像素比
    "is_mobile": False,
    "has_touch": False
}

# 分段截图配置
SEGMENT_HEIGHT = 10000  # 每段截图的高度像素（固定区间，无重叠）
MAX_SEGMENTS = 100  # 最大分段数限制，防止无限循环

# 默认存储路径配置
DEFAULT_STORAGE_PATH = r"C:\Users\Administrator\Desktop\野途2"  # 默认存储路径，为空时需要手动输入


# 示例：r"C:\Users\Administrator\Desktop\秀米截图"

# --- 3. 函数区 ---

def validate_directory_path(path: str) -> bool:
    """
    验证目录路径的有效性
    检查路径是否存在且为目录
    """
    path_obj = Path(path)
    return path_obj.exists() and path_obj.is_dir()


def get_province_abbreviation() -> str:
    """
    获取用户选择的省份缩写
    展示省份列表供用户选择，返回对应缩写
    """
    print("\n请选择省份（输入编号）：")
    province_list = list(PROVINCE_MAPPING.keys())

    for i, province in enumerate(province_list, 1):
        print(f"{i}. {province}")

    while True:
        try:
            choice = int(input("请输入编号: "))
            if 1 <= choice <= len(province_list):
                selected_province = province_list[choice - 1]
                abbreviation = PROVINCE_MAPPING[selected_province]
                print(f"已选择: {selected_province} ({abbreviation})")
                return abbreviation
            else:
                print("输入编号超出范围，请重新输入")
        except ValueError:
            print("请输入有效的数字")


def initialize_config(storage_path: Path, province_abbr: str) -> Path:
    """
    初始化配置文件
    在指定目录创建savexiumi_config.json并初始化基本结构
    """
    config_path = storage_path / "savexiumi_config.json"

    if not config_path.exists():
        initial_config = {
            "province": province_abbr,
            "created_time": datetime.now().isoformat(),
            "items": []
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(initial_config, f, ensure_ascii=False, indent=2)
        print(f"已创建配置文件: {config_path}")
    else:
        print(f"配置文件已存在: {config_path}")

    return config_path


def detect_input_type(input_str: str) -> str:
    """
    检测输入内容的类型
    返回类型标识：'url', 'local_image', 'image_url', 'directory', 'clipboard', 'unknown'
    """
    if not input_str.strip():
        return 'clipboard'

    input_str = input_str.strip()

    # 检查是否为目录路径
    path_obj = Path(input_str)
    if path_obj.exists() and path_obj.is_dir():
        return 'directory'

    # 检查是否为URL
    url_pattern = re.compile(
        r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?$'
    )

    if url_pattern.match(input_str):
        # 判断是否为图片URL
        if any(input_str.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
            return 'image_url'
        else:
            return 'url'

    # 检查是否为本地图片文件路径
    if path_obj.exists() and path_obj.suffix.lower() in IMAGE_EXTENSIONS:
        return 'local_image'

    return 'unknown'


async def extract_qr_from_image_bytes(image_bytes: bytes) -> Optional[str]:
    """
    从图片字节数据中提取二维码内容
    支持多种解码方式提高成功率
    """
    from io import BytesIO

    # 方法1: 使用PIL + pyzbar
    try:
        pil_image = Image.open(BytesIO(image_bytes))
        # 预处理：如果图片不是 RGB，转换一下
        if pil_image.mode not in ('L', 'RGB'):
            pil_image = pil_image.convert('RGB')
        decoded_objects = pyzbar.decode(pil_image)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        print(f"PIL字节数据解码失败: {e}")

    # 方法2: 使用OpenCV + pyzbar
    try:
        import numpy as np
        # 将字节数据转换为numpy数组
        nparr = np.frombuffer(image_bytes, np.uint8)
        cv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if cv_image is not None:
            decoded_objects = pyzbar.decode(cv_image)
            if decoded_objects:
                return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        print(f"OpenCV字节数据解码失败: {e}")

    return None


async def extract_qr_from_image(image_path: Union[str, Path]) -> Optional[str]:
    """
    从图片文件中提取二维码内容
    支持多种解码方式提高成功率
    """
    image_path = str(image_path)

    # 方法1: 使用PIL + pyzbar
    try:
        pil_image = Image.open(image_path)
        # 预处理：如果图片不是 RGB，转换一下
        if pil_image.mode not in ('L', 'RGB'):
            pil_image = pil_image.convert('RGB')
        decoded_objects = pyzbar.decode(pil_image)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        print(f"PIL解码失败: {e}")

    # 方法2: 使用OpenCV + pyzbar
    try:
        cv_image = cv2.imread(image_path)
        if cv_image is not None:
            decoded_objects = pyzbar.decode(cv_image)
            if decoded_objects:
                return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        print(f"OpenCV解码失败: {e}")

    return None


def generate_qr_code(url: str, save_path: Path) -> bool:
    """
    生成二维码图片并保存
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(str(save_path), 'JPEG')
        return True
    except Exception as e:
        print(f"生成二维码失败: {e}")
        return False


async def get_page_title(page) -> str:
    """
    智能获取页面标题
    采用多级降级策略确保获取到有效标题
    """
    title_text = "未获取到标题"

    # 方式1: 查找页面中的主要标题元素
    title_selectors = [
        "h1:first-child",
        "h1",
        "h2:first-child",
        "h2",
        ".title:first-child",
        ".headline:first-child",
        "[class*='title']:first-child",
        "[data-testid*='title']",
        "header h1",
        ".page-title"
    ]

    for selector in title_selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                if text and len(text.strip()) > 0:
                    title_text = text.strip()
                    print(f"通过选择器 '{selector}' 获取到标题: {title_text}")
                    return title_text
        except:
            continue

    # 方式2: 使用页面title
    try:
        page_title = await page.title()
        if page_title and len(page_title.strip()) > 0:
            title_text = page_title.strip()
            print(f"通过页面title获取到标题: {title_text}")
        else:
            print("无法获取到有效的页面标题")
    except Exception as e:
        print(f"获取页面title异常: {e}")
        title_text = "获取标题失败"

    return title_text


async def capture_full_page_screenshot(page, save_path: Path) -> bool:
    """
    一次性完整网页截图
    使用Playwright的full_page功能直接截图整个页面
    保证最大分辨率和最清晰度，保存为JPG格式
    """
    try:
        # 直接使用full_page=True进行完整截图
        await page.screenshot(path=str(save_path), full_page=True, quality=100)

        # 确保保存为JPG格式（如果需要转换）
        if save_path.suffix.lower() != '.jpg':
            temp_path = save_path.with_suffix('.jpg')
            from PIL import Image
            # 使用最高质量保存
            img = Image.open(save_path)
            img.save(temp_path, 'JPEG', quality=100, optimize=False)
            save_path.unlink()  # 删除临时文件
            save_path = temp_path

        print(f"✓ 完整网页截图已保存: {save_path}")
        print(f"  文件大小: {save_path.stat().st_size / 1024 / 1024:.2f} MB")
        return True

    except Exception as e:
        print(f"✗ 完整网页截图失败: {e}")
        return False


async def capture_full_page_screenshot_v2(page, save_path: Path) -> bool:
    """
    智能全网页截图解决方案
    自动检测页面大小，对于超长页面采用无缝分段截图拼接技术
    最终只输出一张完整的高质量图片
    """
    print("🔍 开始智能全网页截图...")

    # 首先尝试标准方法
    try:
        print("尝试标准full_page截图...")
        await page.screenshot(path=str(save_path), full_page=True, quality=100)
        if save_path.suffix.lower() != '.jpg':
            temp_path = save_path.with_suffix('.jpg')
            from PIL import Image
            img = Image.open(save_path)
            img.save(temp_path, 'JPEG', quality=100, optimize=False)
            save_path.unlink()
            save_path = temp_path
        print(f"✓ 标准全页面截图成功: {save_path}")
        return True
    except Exception as e1:
        print(f"⚠ 标准方法失败: {e1}")

        # 检查是否是因为尺寸限制
        if "32767" in str(e1) or "Cannot take screenshot larger" in str(e1):
            print("检测到页面超出尺寸限制，启动智能分段截图方案...")
            return await _smart_segmented_screenshot(page, save_path)
        else:
            print("其他错误，尝试备用方案...")
            return await capture_full_page_screenshot(page, save_path)


async def _smart_segmented_screenshot(page, save_path: Path) -> bool:
    """
    智能分段截图核心功能
    采用固定区间截图方式：1-10000, 10001-20000, 20001-30000...
    无重叠拼接，最终输出一张完整图片
    """
    try:
        print("🚀 启动固定区间分段截图引擎...")

        # 获取页面信息
        viewport_size = page.viewport_size
        viewport_width = viewport_size['width']

        # 获取实际页面总高度
        page_height = await page.evaluate("document.body.scrollHeight")
        print(f"页面总高度: {page_height}px")
        print(f"每段高度: {SEGMENT_HEIGHT}px")

        # 计算分段数量
        total_segments = (page_height + SEGMENT_HEIGHT - 1) // SEGMENT_HEIGHT  # 向上取整
        total_segments = min(total_segments, MAX_SEGMENTS)  # 限制最大分段数
        print(f"计划分段数: {total_segments}")

        # 创建临时目录存储分段
        temp_dir = save_path.parent / f"temp_segments_{int(time.time())}"
        temp_dir.mkdir(exist_ok=True)

        # 固定区间分段截图
        segment_files = []

        for i in range(total_segments):
            # 计算截图区间
            start_y = i * SEGMENT_HEIGHT
            end_y = min((i + 1) * SEGMENT_HEIGHT, page_height)
            segment_height = end_y - start_y

            print(f"  处理第 {i + 1}/{total_segments} 段: {start_y}-{end_y}px (高度: {segment_height}px)")

            # 设置视口高度为当前段落高度
            await page.set_viewport_size({"width": viewport_width, "height": segment_height})
            await page.wait_for_timeout(500)  # 等待视口调整

            # 滚动到该段落起始位置
            await page.evaluate(f"window.scrollTo(0, {start_y})")
            await page.wait_for_timeout(1000)  # 等待滚动和渲染完成

            # 截图
            segment_path = temp_dir / f"segment_{i:03d}.png"
            await page.screenshot(path=str(segment_path), full_page=False)
            segment_files.append(segment_path)

            print(f"    ✓ 已保存片段: {segment_path.name}")

            # 显示进度
            progress = ((i + 1) / total_segments) * 100
            print(f"    进度: {progress:.1f}%")

        # 无重叠垂直拼接
        print("正在进行无重叠图像拼接...")
        merged_success = await _simple_vertical_merge_no_overlap(segment_files, save_path)

        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
            print("✓ 临时文件已清理")
        except Exception as cleanup_error:
            print(f"⚠ 临时文件清理警告: {cleanup_error}")

        if merged_success:
            print(f"🎉 固定区间分段截图完成! 最终图片: {save_path}")
            print(f"  文件大小: {save_path.stat().st_size / 1024 / 1024:.2f} MB")
            return True
        else:
            print("✗ 图像拼接失败")
            return False

    except Exception as e:
        print(f"✗ 固定区间分段截图失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def _simple_vertical_merge_no_overlap(segment_files: List[Path], save_path: Path) -> bool:
    """
    无重叠垂直拼接
    专门用于固定区间截图的简单拼接
    """
    try:
        from PIL import Image

        print(f"开始无重叠拼接 {len(segment_files)} 个片段...")

        # 读取所有片段获取尺寸信息
        images = []
        total_height = 0
        width = None

        for segment_file in segment_files:
            img = Image.open(segment_file)
            if width is None:
                width = img.width
            images.append(img)
            total_height += img.height
            print(f"  片段 {segment_file.name}: {img.width} x {img.height}px")

        print(f"最终图像尺寸: {width} x {total_height}px")

        # 创建合并图像
        merged_image = Image.new('RGB', (width, total_height), (255, 255, 255))

        # 简单垂直粘贴（无重叠）
        current_y = 0
        for i, img in enumerate(images):
            merged_image.paste(img, (0, current_y))
            current_y += img.height
            print(f"    已粘贴片段 {i + 1}/{len(images)}")
            img.close()

        # 保存最终图像（JPG格式，最高质量）
        merged_image.save(str(save_path), 'JPEG', quality=100, optimize=False)
        merged_image.close()

        print(f"✓ 无重叠拼接完成: {save_path}")
        return True

    except Exception as e:
        print(f"✗ 无重叠拼接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def _intelligent_merge_segments(segment_files: List[Path], save_path: Path, overlap_pixels: int) -> bool:
    """
    智能图像拼接
    使用OpenCV进行特征匹配实现无缝拼接
    """
    try:
        from PIL import Image
        import numpy as np

        print(f"开始拼接 {len(segment_files)} 个片段...")

        # 读取第一个片段作为基准
        base_image = Image.open(segment_files[0])
        base_array = np.array(base_image)
        base_width = base_array.shape[1]
        total_height = base_array.shape[0]

        # 计算最终图像高度
        for i in range(1, len(segment_files)):
            segment_img = Image.open(segment_files[i])
            segment_array = np.array(segment_img)
            total_height += segment_array.shape[0] - overlap_pixels

        # 创建最终图像
        final_array = np.zeros((int(total_height), base_width, 3), dtype=np.uint8)
        current_y = 0

        # 逐个拼接片段
        for i, segment_file in enumerate(segment_files):
            segment_img = Image.open(segment_file)
            segment_array = np.array(segment_img)
            segment_height = segment_array.shape[0]

            if i == 0:
                # 第一个片段完整复制
                final_array[current_y:current_y + segment_height] = segment_array
                current_y += segment_height
            else:
                # 后续片段需要去除重叠部分
                actual_height = segment_height - overlap_pixels
                final_array[current_y:current_y + actual_height] = segment_array[overlap_pixels:]
                current_y += actual_height

            print(f"    拼接进度: {(i + 1)}/{len(segment_files)}")

        # 转换为PIL图像并保存
        final_image = Image.fromarray(final_array)
        final_image.save(str(save_path), 'JPEG', quality=100, optimize=False)

        print(f"✓ 图像拼接成功，最终尺寸: {final_array.shape[1]} x {final_array.shape[0]} px")
        return True

    except Exception as e:
        print(f"✗ 图像拼接失败: {e}")
        # 回退到简单的垂直拼接
        return await _simple_vertical_merge(segment_files, save_path)


async def _simple_vertical_merge(segment_files: List[Path], save_path: Path) -> bool:
    """
    简单垂直拼接（备用方案）
    当智能拼接失败时使用
    """
    try:
        from PIL import Image

        print("使用简单垂直拼接方案...")

        # 读取所有片段获取尺寸信息
        images = []
        total_height = 0
        width = None

        for segment_file in segment_files:
            img = Image.open(segment_file)
            if width is None:
                width = img.width
            images.append(img)
            total_height += img.height

        # 创建合并图像（减去重叠部分）
        overlap_reduction = 30 * (len(images) - 1)  # 每个重叠减少30像素
        final_height = total_height - overlap_reduction

        merged_image = Image.new('RGB', (width, final_height), (255, 255, 255))

        # 粘贴图像
        current_y = 0
        for i, img in enumerate(images):
            if i == 0:
                merged_image.paste(img, (0, current_y))
                current_y += img.height
            else:
                # 去除重叠部分
                paste_height = img.height - 30
                merged_image.paste(img.crop((0, 30, img.width, img.height)), (0, current_y))
                current_y += paste_height

            img.close()

        # 保存最终图像
        merged_image.save(str(save_path), 'JPEG', quality=100, optimize=False)
        merged_image.close()

        print(f"✓ 简单拼接完成: {save_path}")
        return True

    except Exception as e:
        print(f"✗ 简单拼接也失败: {e}")
        return False


# 旧的拼接函数已移除，使用新的无重叠拼接方案

# 所有分段截图相关功能已移除
# 现在只使用完整的full_page截图功能

def generate_filename(province_abbr: str, timestamp: str, sequence: int, file_type: str) -> str:
    """
    生成符合规范的文件名
    格式: {省份缩写}-{时间戳}-{序号}-{类型标识}.jpg
    """
    sequence_str = f"{sequence:04d}"
    return f"{province_abbr}-{timestamp}-{sequence_str}-{file_type}.jpg"


def scan_directory_for_images(directory_path: str) -> List[Path]:
    """
    扫描目录中的所有支持的图片文件
    返回图片文件路径列表
    """
    directory = Path(directory_path)
    image_files = []

    if not directory.exists() or not directory.is_dir():
        print(f"✗ 目录不存在或不是有效目录: {directory_path}")
        return image_files

    # 递归扫描目录中的所有图片文件
    for file_path in directory.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
            image_files.append(file_path)

    print(f"在目录 {directory_path} 中找到 {len(image_files)} 个图片文件")
    return image_files


def update_config(config_path: Path, item_data: Dict) -> bool:
    """
    更新配置文件，添加新的item记录
    """
    try:
        # 读取现有配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 添加新项
        config['items'].append(item_data)

        # 写回文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"更新 savexiumi_config.json 配置文件失败: {e}")
        return False


# --- 4. 主流程区 ---
async def process_single_item(input_source: str, storage_path: Path, province_abbr: str,
                              sequence_num: int, config_path: Path) -> bool:
    """
    处理单个项目的核心流程
    包括输入解析、网页处理、截图、二维码处理、数据记录等
    """
    print(f"\n{'=' * 50}")
    print(f"开始处理第 {sequence_num} 个项目")
    print(f"输入源: {input_source}")
    print(f"{'=' * 50}")

    # 1. 解析输入源
    input_type = detect_input_type(input_source)
    target_url = None
    poster_path = None
    poster_bytes = None  # 用于存储图片字节数据

    if input_type == 'clipboard':
        # 处理剪贴板内容（支持文本链接和图片）
        try:
            # 首先尝试获取剪贴板文本
            clipboard_text = pyperclip.paste()
            if clipboard_text and clipboard_text.startswith(('http://', 'https://')):
                target_url = clipboard_text.strip()
                print(f"从剪贴板获取到链接: {target_url}")
            else:
                # 如果没有有效文本链接，尝试读取剪贴板图片
                print("剪贴板中没有有效链接，尝试读取图片...")
                clipboard_content = ImageGrab.grabclipboard()

                if isinstance(clipboard_content, Image.Image):
                    # 剪贴板里直接是图片像素（如截图、网页右键复制图片）
                    print("✓ 检测到剪贴板中的图片数据")
                    # 转换为字节数据
                    from io import BytesIO
                    bio = BytesIO()
                    clipboard_content.save(bio, format="PNG")
                    poster_bytes = bio.getvalue()

                    # 尝试从图片中解码二维码
                    qr_content = await extract_qr_from_image_bytes(poster_bytes)
                    if qr_content:
                        target_url = qr_content
                        print(f"✓ 从剪贴板图片中提取到链接: {target_url}")
                    else:
                        print("⚠ 剪贴板图片中未检测到二维码，将作为普通海报处理")
                        # 保存为临时文件以便后续处理
                        temp_path = storage_path / f"temp_clipboard_{int(time.time())}.png"
                        clipboard_content.save(temp_path, 'PNG')
                        poster_path = temp_path

                elif isinstance(clipboard_content, list):
                    # 剪贴板里是文件列表（在资源管理器复制了文件）
                    if len(clipboard_content) > 0 and os.path.isfile(clipboard_content[0]):
                        file_path = clipboard_content[0]
                        print(f"✓ 检测到剪贴板中的文件: {file_path}")
                        # 检查是否为支持的图片格式
                        if Path(file_path).suffix.lower() in IMAGE_EXTENSIONS:
                            poster_path = Path(file_path)
                            # 尝试从图片文件中解码二维码
                            qr_content = await extract_qr_from_image(poster_path)
                            if qr_content:
                                target_url = qr_content
                                print(f"✓ 从剪贴板图片文件中提取到链接: {target_url}")
                        else:
                            print(f"⚠ 文件格式不支持: {Path(file_path).suffix}")
                else:
                    print("✗ 剪贴板中没有有效的链接或图片内容")
                    return False

        except Exception as e:
            print(f"处理剪贴板内容失败: {e}")
            return False

    elif input_type == 'local_image':
        # 处理本地图片文件
        qr_content = await extract_qr_from_image(input_source)
        if qr_content:
            target_url = qr_content
            poster_path = Path(input_source)  # 保存原始海报
            print(f"从本地图片提取到链接: {target_url}")
        else:
            print("本地图片中未检测到二维码，跳过处理")
            return False  # 没有二维码直接返回False，跳过此图片

    elif input_type == 'image_url':
        # 处理网络图片URL
        try:
            import requests
            response = requests.get(input_source)
            if response.status_code == 200:
                temp_path = storage_path / f"temp_download_{int(time.time())}.jpg"
                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                qr_content = await extract_qr_from_image(temp_path)
                if qr_content:
                    target_url = qr_content
                    print(f"从网络图片提取到链接: {target_url}")
                temp_path.unlink()
        except Exception as e:
            print(f"下载网络图片失败: {e}")
            return False

    elif input_type == 'url':
        # 直接使用URL
        target_url = input_source.strip()
        print(f"使用直接链接: {target_url}")

    else:
        print(f"无法识别的输入类型: {input_source}")
        return False

    if not target_url:
        print("未获取到有效的目标URL")
        return False

    # 2. 生成基础文件名组件
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_filename = f"{province_abbr}-{timestamp}-{sequence_num:04d}"

    # 3. Playwright网页处理
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=True)
        # 使用自定义视口配置而非预设设备
        context = await browser.new_context(
            viewport={"width": DEVICE_VIEWPORT["width"], "height": DEVICE_VIEWPORT["height"]},
            device_scale_factor=DEVICE_VIEWPORT["device_scale_factor"],
            is_mobile=DEVICE_VIEWPORT["is_mobile"],
            has_touch=DEVICE_VIEWPORT["has_touch"]
        )
        page = await context.new_page()

        try:
            # 访问网页
            print(f"正在访问: {target_url}")
            await page.goto(target_url, wait_until="networkidle")
            await page.wait_for_timeout(3000)  # 等待页面加载
            1
            # 获取标题
            title = await get_page_title(page)

            # 截图（使用高级全网页截图方法）
            screenshot_path = storage_path / f"{base_filename}-XQY.jpg"
            success = await capture_full_page_screenshot_v2(page, screenshot_path)
            if not success:
                print("截图失败，尝试备用方案...")
                # 回退到原有方法
                success = await capture_full_page_screenshot(page, screenshot_path)
                if not success:
                    print("所有截图方法都失败")
                    return False

        except Exception as e:
            print(f"网页处理失败: {e}")
            await browser.close()
            return False
        finally:
            await browser.close()

    # 4. 海报处理（优先处理）
    hb_path = None
    hb_success = False
    if poster_path and poster_path.exists():
        hb_path = storage_path / f"{base_filename}-HB.jpg"
        try:
            poster_image = Image.open(poster_path)
            poster_image.save(hb_path, 'JPEG')
            print(f"海报已保存: {hb_path}")
            hb_success = True
        except Exception as e:
            print(f"保存海报失败: {e}")
            hb_path = None
            hb_success = False

    # 5. 二维码生成（仅在海报处理失败或不存在时生成）
    qr_path = None
    qr_success = False
    if not hb_success:
        qr_path = storage_path / f"{base_filename}-QR.jpg"
        qr_success = generate_qr_code(target_url, qr_path)
        if qr_success:
            print(f"二维码已生成: {qr_path}")
        else:
            print("二维码生成失败")

    # 6. 构建配置项数据
    # 按照规范，所有字段都应该有值，详情页和首图路径按规范格式预先填写
    detail_page_path = storage_path / f"{base_filename}-XQY.jpg"
    first_image_path = storage_path / f"{base_filename}-ST.jpg"
    oss_url = f"https://travel-static.hydtrip.net/crmebimage/image/PDP/{base_filename}-XQY.jpg"

    item_data = {
        "线路标题": title,
        "线路唯一编码": f"{province_abbr}-{timestamp}-{sequence_num:04d}",
        "价格": "",
        "海报路径": str(hb_path.relative_to(storage_path)) if hb_path else "",
        "二维码路径": str(qr_path.relative_to(storage_path)) if qr_success else "",
        "详情页路径": str(detail_page_path.relative_to(storage_path)),
        "首图路径": str(first_image_path.relative_to(storage_path)),
        "oss地址": oss_url,
        "省份": province_abbr  # 添加省份缩写字段
    }

    # 7. 更新配置文件
    if update_config(config_path, item_data):
        print(f"✓ 项目处理完成，数据已记录到 savexiumi_config.json")
        # 清理临时文件
        if poster_path and poster_path.name.startswith('temp_clipboard_'):
            try:
                poster_path.unlink()
                print(f"✓ 已清理临时文件: {poster_path.name}")
            except Exception as e:
                print(f"⚠ 清理临时文件失败: {e}")
        return True
    else:
        print("✗ savexiumi_config.json 配置文件更新失败")
        return False


async def main():
    """
    主控函数
    负责整体流程调度：路径获取、省份选择、模式选择、循环处理
    """
    print(">>> 秀米网页处理工具启动")
    print("支持手动模式和批量模式，自动识别输入类型")

    # 1. 获取存储路径
    if DEFAULT_STORAGE_PATH and validate_directory_path(DEFAULT_STORAGE_PATH):
        # 使用预设的默认路径
        storage_path = Path(DEFAULT_STORAGE_PATH)
        print(f"✓ 使用默认存储路径: {storage_path}")
        print("  （可通过修改 DEFAULT_STORAGE_PATH 常量更改默认路径）")
    else:
        # 手动输入路径
        if DEFAULT_STORAGE_PATH:
            print(f"⚠ 默认路径无效: {DEFAULT_STORAGE_PATH}")
        print("请手动输入存储文件夹路径:")
        while True:
            storage_input = input(">>> 存储路径: ").strip()
            if validate_directory_path(storage_input):
                storage_path = Path(storage_input)
                print(f"✓ 存储路径有效: {storage_path}")
                break
            else:
                print("✗ 路径无效或不存在，请重新输入")

    # 2. 省份选择
    province_abbr = get_province_abbreviation()

    # 3. 配置初始化
    config_path = initialize_config(storage_path, province_abbr)

    # 4. 模式选择
    print("\n请选择处理模式:")
    print("1. 手动模式（逐个处理）")
    print("2. 批量模式（一次处理多个）")

    mode_choice = input("请选择模式 (1/2): ").strip()

    sequence_counter = 1

    if mode_choice == "1":
        # 手动模式
        print("\n=== 手动模式 ===")
        print("提示：直接按回车可读取剪贴板内容")
        print("输入 'quit' 退出程序")

        while True:
            user_input = input(f"\n请输入第 {sequence_counter} 个项目的链接或路径: ").strip()

            if user_input.lower() == 'quit':
                print("程序退出")
                break

            if await process_single_item(user_input, storage_path, province_abbr,
                                         sequence_counter, config_path):
                sequence_counter += 1
                print(f"当前已处理 {sequence_counter - 1} 个项目")
            else:
                print("该项目处理失败，继续下一个")

    elif mode_choice == "2":
        # 批量模式 - 支持三种批量处理场景
        print("\n=== 批量模式 ===")
        print("支持三种批量处理方式：")
        print("1. 目录批量处理 - 输入目录路径，自动处理目录中所有图片")
        print("2. 图片链接批量处理 - 粘贴多个图片链接，批量提取二维码")
        print("3. 网页链接批量处理 - 粘贴多个网页链接，批量截图处理")
        print("\n请输入批量处理内容（支持以上任意一种方式）:")

        # 读取多行输入
        batch_lines = []
        print("(输入完成后按两次回车结束)")
        while True:
            line = input().strip()
            if not line:
                # 检查是否是连续的空行（表示输入结束）
                if batch_lines and not batch_lines[-1]:  # 前一行也是空行
                    batch_lines.pop()  # 移除最后一个空行
                    break
                else:
                    batch_lines.append(line)  # 添加空行作为分隔符标记
            else:
                batch_lines.append(line)

        if not batch_lines:
            print("未输入任何内容")
            return

        # 分析输入内容类型
        all_inputs = [line for line in batch_lines if line.strip()]

        if len(all_inputs) == 1:
            # 单行输入，可能是目录路径
            single_input = all_inputs[0]
            input_type = detect_input_type(single_input)

            if input_type == 'directory':
                # 场景1：目录批量处理
                print(f"\n📁 检测到目录输入: {single_input}")
                image_files = scan_directory_for_images(single_input)
                if not image_files:
                    print("✗ 目录中未找到支持的图片文件")
                    return

                print(f"\n开始批量处理目录中的 {len(image_files)} 个图片文件...")
                successful_count = 0

                for i, image_path in enumerate(image_files, 1):
                    print(f"\n--- 处理第 {i}/{len(image_files)} 个图片 ---")
                    print(f"图片路径: {image_path}")

                    if await process_single_item(str(image_path), storage_path, province_abbr,
                                                 sequence_counter, config_path):
                        sequence_counter += 1
                        successful_count += 1
                        print(f"✓ 图片处理成功")
                    else:
                        print(f"✗ 图片处理失败")

                    # 添加小延迟
                    if i < len(image_files):
                        await asyncio.sleep(1)

            else:
                # 单个项目处理
                print(f"\n检测到单个项目输入，按手动模式处理")
                if await process_single_item(single_input, storage_path, province_abbr,
                                             sequence_counter, config_path):
                    sequence_counter += 1
                    print(f"✓ 项目处理成功")
                else:
                    print(f"✗ 项目处理失败")
                return

        else:
            # 多行输入，分析是图片链接还是网页链接
            image_links = []
            web_links = []
            unknown_inputs = []

            for line in all_inputs:
                line_type = detect_input_type(line)
                if line_type == 'image_url':
                    image_links.append(line)
                elif line_type == 'url':
                    web_links.append(line)
                else:
                    unknown_inputs.append((line, line_type))

            # 处理不同类型的内容
            total_processed = 0
            successful_count = 0

            # 场景2：图片链接批量处理
            if image_links:
                print(f"\n🖼️  检测到 {len(image_links)} 个图片链接，开始批量处理...")
                for i, image_url in enumerate(image_links, 1):
                    print(f"\n--- 处理第 {i}/{len(image_links)} 个图片链接 ---")
                    print(f"图片链接: {image_url}")

                    if await process_single_item(image_url, storage_path, province_abbr,
                                                 sequence_counter, config_path):
                        sequence_counter += 1
                        successful_count += 1
                        total_processed += 1
                        print(f"✓ 图片链接处理成功")
                    else:
                        total_processed += 1
                        print(f"✗ 图片链接处理失败")

                    if i < len(image_links):
                        await asyncio.sleep(1)

            # 场景3：网页链接批量处理
            if web_links:
                print(f"\n🌐 检测到 {len(web_links)} 个网页链接，开始批量处理...")
                for i, web_url in enumerate(web_links, 1):
                    print(f"\n--- 处理第 {i}/{len(web_links)} 个网页链接 ---")
                    print(f"网页链接: {web_url}")

                    if await process_single_item(web_url, storage_path, province_abbr,
                                                 sequence_counter, config_path):
                        sequence_counter += 1
                        successful_count += 1
                        total_processed += 1
                        print(f"✓ 网页链接处理成功")
                    else:
                        total_processed += 1
                        print(f"✗ 网页链接处理失败")

                    if i < len(web_links):
                        await asyncio.sleep(1)

            # 处理未知类型输入
            if unknown_inputs:
                print(f"\n⚠  检测到 {len(unknown_inputs)} 个无法识别的输入:")
                for input_content, detected_type in unknown_inputs:
                    print(f"  - '{input_content}' (检测为: {detected_type})")
                print("这些输入将被跳过处理")

        # 显示最终统计
        if 'total_processed' in locals() and total_processed > 0:
            print(f"\n📊 批量处理完成！")
            print(f"总计处理: {total_processed} 个项目")
            print(f"成功: {successful_count} 个")
            print(f"失败: {total_processed - successful_count} 个")
        elif 'successful_count' in locals() and successful_count > 0:
            print(f"\n📊 批量处理完成！")
            print(f"成功处理 {successful_count} 个项目")
    else:
        print("无效的选择")


# --- 5. 执行区 ---
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        import traceback

        traceback.print_exc()