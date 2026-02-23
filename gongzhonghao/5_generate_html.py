# -*- coding: utf-8 -*-
"""
[功能概述]: 将 txt 文章 + 本地图片 → 上传图床 → 生成 mdnice 格式 HTML（一文件一文件处理）
[启动准备]: 需要安装依赖: pip install requests
[输入参数]: 无（配置在 5_config.json 中）
[输出内容]:
    - 控制台输出处理进度和日志
    - 生成 HTML 文件到 output_folder
    - 更新 upload_cache.json 缓存文件
[模块调用关系]: 无
[使用流程]:
    1. 确保 5_config.json 配置正确
    2. 确保 txt 文件夹中有待处理的文章
    3. 确保 imgoutput 文件夹中有对应的图片
    4. 运行: python 5_generate_html.py
[注意事项]:
    - Windows 路径使用正斜杠 / 或 raw string
    - 图床 API 有频率限制，脚本已内置重试和等待机制
    - 图片上传失败不会中断程序，会记录日志并跳过
    - 支持两种图片标记格式：【xxx】 和 [画面描述：xxx]
    - 所有文件读写统一使用 UTF-8 编码，避免乱码
[可调整参数]:
    - 在 5_config.json 中修改各项配置
    - upload_interval: 上传间隔时间（秒）
    - max_retries: 最大重试次数
    - fuzzy_match_length: 模糊匹配时使用的字符长度
"""

# ==================== 模块引入区 ====================
# 标准库
import os
import re
import json
import time
from datetime import datetime
from pathlib import Path

# 第三方库
import requests

# 本地模块
# 无

# ==================== 常量配置区 ====================
# 获取当前脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "5_config.json")

# 默认配置（当配置文件不存在时使用）
DEFAULT_CONFIG = {
    "txt_folder": "C:/Users/Administrator/Desktop/公众号文章/txt",
    "img_folder": "C:/Users/Administrator/Desktop/公众号文章/imgoutput",
    "output_folder": "C:/Users/Administrator/Desktop/公众号文章/html",
    "cache_file": "C:/Users/Administrator/Desktop/公众号文章/upload_cache.json",
    "image_host_url": "https://img.scdn.io/api/v1.php",
    "upload_interval": 2,
    "fuzzy_match_length": 15,
    "max_retries": 3
}

# mdnice HTML 模板常量
SECTION_STYLE = (
    'margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; '
    'padding-top: 0px; padding-bottom: 0px; padding-left: 10px; padding-right: 10px; '
    'background-attachment: scroll; background-clip: border-box; background-color: rgba(0, 0, 0, 0); '
    'background-image: none; background-origin: padding-box; '
    'background-position-x: left; background-position-y: top; background-repeat: no-repeat; '
    'background-size: auto; width: auto; '
    'font-family: Optima, "Microsoft YaHei", PingFangSC-regular, serif; font-size: 16px; '
    'color: rgb(0, 0, 0); line-height: 1.5em; word-spacing: 0em; letter-spacing: 0em; '
    'word-break: break-word; overflow-wrap: break-word; text-align: left;'
)

FIGURE_STYLE = (
    'margin-top: 10px; margin-bottom: 10px; margin-left: 0px; margin-right: 0px; '
    'padding-top: 0px; padding-bottom: 0px; padding-left: 0px; padding-right: 0px; '
    'display: flex; flex-direction: column; justify-content: center; align-items: center;'
)

IMG_STYLE = (
    'display: block; margin-top: 0px; margin-right: auto; margin-bottom: 0px; margin-left: auto; '
    'max-width: 100%; border-top-style: none; border-bottom-style: none; border-left-style: none; '
    'border-right-style: none; border-top-width: 3px; border-bottom-width: 3px; border-left-width: 3px; '
    'border-right-width: 3px; border-top-color: rgba(0, 0, 0, 0.4); border-bottom-color: rgba(0, 0, 0, 0.4); '
    'border-left-color: rgba(0, 0, 0, 0.4); border-right-color: rgba(0, 0, 0, 0.4); '
    'border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-right-radius: 0px; '
    'border-bottom-left-radius: 0px; object-fit: fill; box-shadow: rgba(0, 0, 0, 0) 0px 0px 0px 0px;'
)

PARAGRAPH_STYLE = (
    'color: rgb(18, 0, 0); font-size: 14px; line-height: 1.8em; letter-spacing: 0em; '
    'text-align: left; text-indent: 0em; margin-top: 8px; margin-bottom: 0px; '
    'margin-left: 0px; margin-right: 0px; padding-top: 8px; padding-bottom: 8px; '
    'padding-left: 0px; padding-right: 0px;'
)

H2_STYLE = (
    'margin-top: 30px; margin-bottom: 10px; margin-left: 0px; margin-right: 0px; '
    'align-items: unset; background-attachment: scroll; background-clip: border-box; '
    'background-color: unset; background-image: none; background-origin: padding-box; '
    'background-position-x: 0%; background-position-y: 0%; background-repeat: no-repeat; '
    'background-size: auto; border-top-style: none; border-bottom-style: none; '
    'border-left-style: none; border-right-style: none; border-top-width: 1px; '
    'border-bottom-width: 1px; border-left-width: 1px; border-right-width: 1px; '
    'border-top-color: rgb(0, 0, 0); border-bottom-color: rgb(0, 0, 0); '
    'border-left-color: rgb(0, 0, 0); border-right-color: rgb(0, 0, 0); '
    'border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-left-radius: 0px; '
    'border-bottom-right-radius: 0px; box-shadow: none; display: block; flex-direction: unset; '
    'float: unset; height: auto; justify-content: unset; line-height: 1.5em; overflow-x: unset; '
    'overflow-y: unset; padding-top: 0px; padding-bottom: 0px; padding-left: 0px; padding-right: 0px; '
    'position: relative; text-align: left; text-shadow: none; transform: none; width: auto; -webkit-box-reflect: unset;'
)

H2_CONTENT_STYLE = (
    'font-size: 18px; color: rgb(34, 34, 34); line-height: 1.8em; letter-spacing: 0em; '
    'padding-top: 0px; padding-bottom: 0px; padding-left: 10px; padding-right: 0px; '
    'border-top-style: none; border-bottom-style: none; border-left-style: solid; border-right-style: none; '
    'border-top-width: 1px; border-bottom-width: 1px; border-left-width: 5px; border-right-width: 1px; '
    'border-top-color: rgb(0, 0, 0); border-bottom-color: rgb(0, 0, 0); '
    'border-left-color: rgb(3, 128, 18); border-right-color: rgb(0, 0, 0); '
    'border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-left-radius: 0px; '
    'border-bottom-right-radius: 0px; align-items: unset; background-attachment: scroll; '
    'background-clip: border-box; background-color: unset; background-image: none; '
    'background-origin: padding-box; background-position-x: 0%; background-position-y: 0%; '
    'background-repeat: no-repeat; background-size: auto; box-shadow: none; display: block; '
    'font-weight: bold; flex-direction: unset; float: unset; height: auto; justify-content: unset; '
    'margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; overflow-x: unset; '
    'overflow-y: unset; position: relative; text-align: left; text-indent: 0em; text-shadow: none; '
    'transform: none; width: auto; -webkit-box-reflect: unset;'
)

STRONG_STYLE = (
    'color: rgb(30, 115, 8); font-weight: bold; background-attachment: scroll; '
    'background-clip: border-box; background-color: rgba(0, 0, 0, 0); background-image: none; '
    'background-origin: padding-box; background-position-x: left; background-position-y: top; '
    'background-repeat: no-repeat; background-size: auto; width: auto; height: auto; '
    'margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; '
    'padding-top: 0px; padding-bottom: 0px; padding-left: 0px; padding-right: 0px; '
    'border-top-style: none; border-bottom-style: none; border-left-style: none; border-right-style: none; '
    'border-top-width: 3px; border-bottom-width: 3px; border-left-width: 3px; border-right-width: 3px; '
    'border-top-color: rgba(0, 0, 0, 0.4); border-bottom-color: rgba(0, 0, 0, 0.4); '
    'border-left-color: rgba(0, 0, 0, 0.4); border-right-color: rgba(0, 0, 0, 0.4); '
    'border-top-left-radius: 0px; border-top-right-radius: 0px; border-bottom-right-radius: 0px; '
    'border-bottom-left-radius: 0px;'
)


# ==================== 函数区 ====================

def load_config():
    """
    加载配置文件，如果不存在则使用默认配置。

    Returns:
        dict: 配置字典，包含路径、URL等配置项
    """
    # 先使用默认配置
    config = DEFAULT_CONFIG.copy()

    # 如果配置文件存在，则覆盖默认配置
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception as e:
            print(f"[WARN] 加载配置文件失败，使用默认配置: {e}")
    else:
        print(f"[WARN] 配置文件不存在，使用默认配置")

    return config


def log(message, level="INFO"):
    """
    输出带时间戳的日志信息。

    Args:
        message: 日志内容
        level: 日志级别，默认 INFO
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def load_cache(cache_file):
    """
    加载图片上传缓存。

    Args:
        cache_file: 缓存文件路径

    Returns:
        dict: 缓存字典，{图片名: 图床URL}
    """
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"加载缓存失败，将创建新缓存: {e}", "WARN")
    return {}


def save_cache(cache, cache_file):
    """
    保存图片上传缓存。

    Args:
        cache: 缓存字典
        cache_file: 缓存文件路径
    """
    try:
        # 确保目录存在
        cache_dir = os.path.dirname(cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"保存缓存失败: {e}", "ERROR")


def read_txt_file(file_path):
    """
    读取文本文件，自动处理编码问题。

    Args:
        file_path: 文件路径

    Returns:
        str: 文件内容
    """
    # 尝试多种编码
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                # 验证内容是否正常（检查是否有乱码特征 \ufffd 是替换字符）
                if '\ufffd' not in content[:500]:
                    return content
        except (UnicodeDecodeError, UnicodeError):
            continue

    # 最后尝试使用 utf-8 并忽略错误
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()


def write_html_file(file_path, content):
    """
    写入HTML文件，统一使用UTF-8编码。

    Args:
        file_path: 文件路径
        content: 文件内容
    """
    # 确保目录存在
    file_dir = os.path.dirname(file_path)
    if file_dir and not os.path.exists(file_dir):
        os.makedirs(file_dir, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def extract_image_markers(content):
    """
    从文章内容中提取所有图片标记。

    支持两种格式：
    1. 【xxx】 - 秘境系列旅游文章
    2. [画面描述：xxx] - 机场小妙招文章

    Args:
        content: 文章内容字符串

    Returns:
        list: 图片标记列表，每个元素为 (标记类型, 图片名称, 原始标记, 行号)
    """
    markers = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        line = line.strip()

        # 格式1: 【xxx】
        pattern1 = r'^【(.+?)】$'
        match1 = re.match(pattern1, line)
        if match1:
            markers.append(('bracket', match1.group(1), line, line_num))
            continue

        # 格式2: [画面描述：xxx]
        pattern2 = r'^\[画面描述[：:](.+?)\]$'
        match2 = re.match(pattern2, line)
        if match2:
            markers.append(('description', match2.group(1), line, line_num))
            continue

    return markers


def find_image_file(image_name, img_folder, fuzzy_length=15):
    """
    在图片文件夹中查找匹配的图片文件。

    查找策略：
    1. 精确匹配：文件名 = 图片名.jpg
    2. 带"画面描述"前缀的精确匹配：文件名 = 画面描述 + 图片名.jpg
    3. 模糊匹配：文件名以图片名前N字符开头
    4. 带"画面描述"前缀的模糊匹配
    5. 去除标点后的模糊匹配（处理文件名中缺少标点的情况）

    Args:
        image_name: 图片名称（不含扩展名）
        img_folder: 图片文件夹路径
        fuzzy_length: 模糊匹配时使用的字符长度

    Returns:
        str or None: 找到的图片完整路径，未找到返回 None
    """
    if not os.path.exists(img_folder):
        return None

    # 支持的图片扩展名
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

    # 获取图片名前N个字符用于模糊匹配
    prefix = image_name[:fuzzy_length] if len(image_name) > fuzzy_length else image_name

    # 辅助函数：移除标点符号
    def remove_punctuation(text):
        import string
        # 中文和英文标点
        punctuations = '，。！？、；：""''（）【】《》·…—～,.!?;:\'"()[]<>~'
        return ''.join(c for c in text if c not in punctuations)

    # 清理后的图片名（去除标点）
    clean_image_name = remove_punctuation(image_name)
    clean_prefix = remove_punctuation(prefix)

    try:
        for filename in os.listdir(img_folder):
            name_without_ext = os.path.splitext(filename)[0]

            # 1. 精确匹配
            if name_without_ext == image_name:
                return os.path.join(img_folder, filename)

            # 2. 带"画面描述"前缀的精确匹配
            if name_without_ext == "画面描述" + image_name:
                return os.path.join(img_folder, filename)

            # 3. 模糊匹配（文件名以图片名前缀开头）
            if name_without_ext.startswith(prefix):
                return os.path.join(img_folder, filename)

            # 4. 带"画面描述"前缀的模糊匹配
            if name_without_ext.startswith("画面描述" + prefix):
                return os.path.join(img_folder, filename)

            # 5. 反向模糊匹配（图片名以文件名开头，处理文件名截断情况）
            file_name_clean = name_without_ext.replace("画面描述", "")
            if clean_prefix.startswith(file_name_clean[:fuzzy_length]):
                return os.path.join(img_folder, filename)

            # 6. 去除标点后的模糊匹配
            clean_filename = remove_punctuation(name_without_ext)
            if clean_filename.startswith(clean_prefix) or clean_filename.startswith("画面描述" + clean_prefix):
                return os.path.join(img_folder, filename)

            # 7. 检查文件名（去掉画面描述）是否是图片名（去除标点）的前缀
            if clean_image_name.startswith(file_name_clean):
                return os.path.join(img_folder, filename)

    except Exception:
        pass

    return None


def upload_to_image_host_with_retry(image_path, api_url, max_retries=3, base_interval=2, timeout=30):
    """
    上传图片到图床，带重试机制。

    Args:
        image_path: 本地图片路径
        api_url: 图床API地址
        max_retries: 最大重试次数
        base_interval: 基础等待间隔（秒），每次重试递增
        timeout: 请求超时时间（秒）

    Returns:
        str: 图片公网URL

    Raises:
        Exception: 所有重试都失败后抛出最后一次的异常
    """
    last_error = Exception("未知错误")  # 初始化默认错误

    for attempt in range(1, max_retries + 1):
        try:
            with open(image_path, 'rb') as f:
                files = {'image': f}
                data = {'outputFormat': 'webp'}

                response = requests.post(api_url, files=files, data=data, timeout=timeout)
                result = response.json()

                if result.get('success'):
                    return result['url']
                else:
                    last_error = Exception(result.get('message', '服务器返回错误'))

        except requests.exceptions.Timeout:
            last_error = Exception("请求超时")
        except requests.exceptions.ConnectionError:
            last_error = Exception("网络连接错误")
        except json.JSONDecodeError:
            last_error = Exception("响应解析失败")
        except Exception as e:
            last_error = e

        # 重试前等待，每次重试等待时间递增
        if attempt < max_retries:
            wait_time = base_interval * attempt
            log(f"    第 {attempt} 次上传失败，{wait_time} 秒后重试: {last_error}", "WARN")
            time.sleep(wait_time)

    raise last_error


def process_single_file(txt_path, config, cache):
    """
    处理单个文件：读取 → 上传图片 → 生成HTML → 保存

    这是核心处理函数，一个文件一个文件地处理。

    Args:
        txt_path: 文章txt文件路径
        config: 配置字典
        cache: 缓存字典（会被修改）

    Returns:
        dict: 处理结果，包含成功/失败统计
    """
    result = {
        'success': True,
        'images_total': 0,
        'images_uploaded': 0,
        'images_cached': 0,
        'images_failed': 0,
        'failed_markers': []  # 记录失败的图片信息: (图片名, 原因)
    }

    filename = os.path.basename(txt_path)
    log(f"处理文件: {filename}")

    # 步骤1: 读取文章
    try:
        content = read_txt_file(txt_path)
        if not content:
            log(f"  文件内容为空", "ERROR")
            result['success'] = False
            return result
    except Exception as e:
        log(f"  读取文件失败: {e}", "ERROR")
        result['success'] = False
        return result

    # 步骤2: 提取图片标记
    markers = extract_image_markers(content)
    result['images_total'] = len(markers)
    log(f"  发现 {len(markers)} 个图片标记")

    if not markers:
        log(f"  没有图片标记，直接生成HTML", "WARN")

    # 步骤3: 逐个处理图片
    image_url_map = {}  # 原始标记 -> 图床URL

    for idx, (marker_type, image_name, original_marker, line_num) in enumerate(markers, 1):
        log(f"  [{idx}/{len(markers)}] 处理图片: {image_name[:30]}...")

        # 查找图片文件
        image_path = find_image_file(
            image_name,
            config['img_folder'],
            config.get('fuzzy_match_length', 15)
        )

        if not image_path:
            log(f"    图片文件未找到", "ERROR")
            result['images_failed'] += 1
            result['failed_markers'].append((image_name, "文件未找到"))
            continue

        # 检查缓存
        cache_key = os.path.basename(image_path)
        if cache_key in cache:
            log(f"    使用缓存")
            image_url_map[original_marker] = cache[cache_key]
            result['images_cached'] += 1
            continue

        # 上传图片（带重试）
        try:
            url = upload_to_image_host_with_retry(
                image_path,
                config['image_host_url'],
                max_retries=config.get('max_retries', 3),
                base_interval=config.get('upload_interval', 2)
            )
            log(f"    上传成功")

            # 更新映射和缓存
            image_url_map[original_marker] = url
            cache[cache_key] = url
            result['images_uploaded'] += 1

            # 每次成功上传后保存缓存
            save_cache(cache, config['cache_file'])

            # 等待间隔
            time.sleep(config.get('upload_interval', 2))

        except Exception as e:
            log(f"    上传失败: {e}", "ERROR")
            result['images_failed'] += 1
            result['failed_markers'].append((image_name, f"上传失败: {e}"))

    # 步骤4: 生成HTML
    log(f"  生成HTML...")
    html_content = convert_article_to_html(content, image_url_map)

    # 步骤5: 保存HTML
    output_filename = os.path.splitext(filename)[0] + '.html'
    output_path = os.path.join(config['output_folder'], output_filename)

    try:
        write_html_file(output_path, html_content)
        log(f"  保存成功: {output_filename}")
    except Exception as e:
        log(f"  保存失败: {e}", "ERROR")
        result['success'] = False

    return result


def convert_bold_text(text):
    """
    将 **加粗** 格式转换为 HTML strong 标签。

    Args:
        text: 原始文本

    Returns:
        str: 转换后的 HTML 文本
    """
    pattern = r'\*\*(.+?)\*\*'
    replacement = f'<strong style="{STRONG_STYLE}">\\1</strong>'
    return re.sub(pattern, replacement, text)


def generate_figure_html(image_url):
    """
    生成图片的 figure HTML 标签。

    Args:
        image_url: 图片URL

    Returns:
        str: figure HTML 字符串
    """
    return (
        f'<figure data-tool="mdnice编辑器" style="{FIGURE_STYLE}">'
        f'<img src="{image_url}" alt style="{IMG_STYLE}">'
        f'</figure>'
    )


def generate_paragraph_html(text):
    """
    生成段落 p HTML 标签。

    Args:
        text: 段落文本

    Returns:
        str: p HTML 字符串
    """
    processed_text = convert_bold_text(text)
    return f'<p data-tool="mdnice编辑器" style="{PARAGRAPH_STYLE}">{processed_text}</p>'


def generate_h2_html(title):
    """
    生成二级标题 h2 HTML 标签。

    Args:
        title: 标题文本

    Returns:
        str: h2 HTML 字符串
    """
    return (
        f'<h2 data-tool="mdnice编辑器" style="{H2_STYLE}">'
        f'<span class="prefix" style="display: none;"></span>'
        f'<span class="content" style="{H2_CONTENT_STYLE}">{title}</span>'
        f'<span class="suffix" style="display: none;"></span>'
        f'</h2>'
    )


def is_image_marker(line):
    """
    判断一行是否是图片标记。

    Args:
        line: 文本行

    Returns:
        bool: 是否是图片标记
    """
    line = line.strip()
    if re.match(r'^【.+?】$', line):
        return True
    if re.match(r'^\[画面描述[：:].+?\]$', line):
        return True
    return False


def is_h2_title(line):
    """
    判断一行是否是二级标题。

    Args:
        line: 文本行

    Returns:
        bool: 是否是二级标题
    """
    return line.strip().startswith('## ')


def convert_article_to_html(content, image_url_map):
    """
    将文章内容转换为HTML。

    Args:
        content: 原始文章内容
        image_url_map: 图片标记到URL的映射 {原始标记: URL}

    Returns:
        str: 完整的HTML字符串
    """
    html_parts = []
    lines = content.strip().split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行
        if not line:
            i += 1
            continue

        # 处理图片标记
        if is_image_marker(line):
            if line in image_url_map:
                html_parts.append(generate_figure_html(image_url_map[line]))
            else:
                html_parts.append(f'<!-- 图片未上传: {line} -->')
            i += 1
            continue

        # 处理二级标题
        if is_h2_title(line):
            title = line[3:].strip()  # 去掉 "## "
            html_parts.append(generate_h2_html(title))
            i += 1
            continue

        # 处理段落：合并连续的非特殊行
        paragraph_lines = [line]
        i += 1

        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line:
                i += 1
                break
            if is_image_marker(next_line) or is_h2_title(next_line):
                break
            paragraph_lines.append(next_line)
            i += 1

        paragraph_text = ''.join(paragraph_lines)
        html_parts.append(generate_paragraph_html(paragraph_text))

    # 包装在 section 中（完全匹配 mdnice 格式）
    html_content = '\n'.join(html_parts)
    return (
        f'<section id="nice" data-tool="mdnice编辑器" data-website="https://www.mdnice.com" style="{SECTION_STYLE}">\n'
        f'{html_content}\n'
        f'</section>'
    )


def main():
    """
    主流程函数，一个文件一个文件地处理。
    """
    log("=" * 60)
    log("公众号文章 HTML 生成器 v2.0 启动")
    log("=" * 60)

    # 加载配置
    config = load_config()
    log(f"配置: 输入目录={config['txt_folder']}")
    log(f"配置: 图片目录={config['img_folder']}")
    log(f"配置: 输出目录={config['output_folder']}")

    # 确保输出目录存在
    os.makedirs(config['output_folder'], exist_ok=True)

    # 加载缓存
    cache = load_cache(config['cache_file'])
    log(f"缓存: 已加载 {len(cache)} 条记录")

    # 扫描txt文件
    txt_folder = config['txt_folder']
    if not os.path.exists(txt_folder):
        log(f"输入目录不存在: {txt_folder}", "ERROR")
        return

    txt_files = [f for f in os.listdir(txt_folder) if f.endswith('.txt')]

    if not txt_files:
        log("没有找到待处理的文章", "WARN")
        return

    log(f"发现 {len(txt_files)} 个待处理文章")
    log("=" * 60)

    # 统计
    total_stats = {
        'files_success': 0,
        'files_failed': 0,
        'images_uploaded': 0,
        'images_cached': 0,
        'images_failed': 0,
        'all_failed_images': []  # 记录所有失败的图片
    }

    # 一个文件一个文件地处理
    for file_idx, txt_file in enumerate(txt_files, 1):
        log("")
        log(f"{'='*60}")
        log(f"[{file_idx}/{len(txt_files)}] 开始处理")
        log(f"{'='*60}")

        txt_path = os.path.join(txt_folder, txt_file)

        try:
            result = process_single_file(txt_path, config, cache)

            if result['success']:
                total_stats['files_success'] += 1
            else:
                total_stats['files_failed'] += 1

            total_stats['images_uploaded'] += result['images_uploaded']
            total_stats['images_cached'] += result['images_cached']
            total_stats['images_failed'] += result['images_failed']

            # 收集失败图片信息
            if result['failed_markers']:
                total_stats['all_failed_images'].extend([
                    (txt_file, img_name, reason)
                    for img_name, reason in result['failed_markers']
                ])

            # 输出该文件的处理结果
            log(f"  结果: 图片总计={result['images_total']}, "
                f"上传={result['images_uploaded']}, "
                f"缓存={result['images_cached']}, "
                f"失败={result['images_failed']}")

            # 如果有失败的图片，输出详细信息
            if result['failed_markers']:
                log(f"  失败图片详情:", "WARN")
                for img_name, reason in result['failed_markers']:
                    log(f"    - {img_name[:50]}... ({reason})", "WARN")

        except Exception as e:
            log(f"处理文件时发生异常: {e}", "ERROR")
            total_stats['files_failed'] += 1

    # 输出总结
    log("")
    log("=" * 60)
    log("处理完成!")
    log("=" * 60)
    log(f"文件统计: 成功={total_stats['files_success']}, 失败={total_stats['files_failed']}")
    log(f"图片统计: 上传={total_stats['images_uploaded']}, 缓存={total_stats['images_cached']}, 失败={total_stats['images_failed']}")
    log(f"输出目录: {config['output_folder']}")

    # 输出所有失败的图片汇总
    if total_stats['all_failed_images']:
        log("")
        log("=" * 60)
        log("失败图片汇总 (共 {} 张):".format(len(total_stats['all_failed_images'])))
        log("=" * 60)
        for txt_file, img_name, reason in total_stats['all_failed_images']:
            log(f"  [{txt_file}] {img_name[:40]}... -> {reason}")

    log("=" * 60)


# ==================== 执行区 ====================
if __name__ == '__main__':
    main()
