# -*- coding: utf-8 -*-
"""
=============================================================
2_poster_background_extractor.py 海报背景提取工具（完全独立版本）
=============================================================

功能概述:
--------
批量处理图片，通过调用AI API为每张图片生成提示词，
并执行相关任务以去除海报水印并获取海报背景原图。

特点:
------
- 完全独立运行，无需 common 文件夹
- 自动生成配置文件（如不存在）
- 内置 API4 图像分析和 ACH 自动化功能

使用流程:
--------
1. 启动脚本后，输入图片目录路径
2. 选择执行模式（清空配置/跳过已处理）
3. 设置运行参数（可选）
4. 脚本开始处理图片，调用 ACH 自动化
"""

import os
import json
import glob
import re
import sys
import time
import datetime
import requests
import base64
from pathlib import Path

# Playwright 导入
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 尝试导入可选模块
try:
    from win10toast import ToastNotifier
    TOASTER = ToastNotifier()
except ImportError:
    TOASTER = None

# =============================================================================
# 配置区
# =============================================================================
CONFIG_FILENAME = "ach_config.json"
DEFAULT_PROMPT = "pan camera slightly left, low angle"
DEFAULT_MODEL = "2"
DEFAULT_WAIT_TIME = "180"
SUPPORTED_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png']

# API4 配置
DEFAULT_API_KEY = "sk-Jsqk6zfznVkeMsjLEqNLtv4eWFs3bvyLXfn3IzWhSsLg7wSK"
DEFAULT_BASE_URL = "https://one.api4gpt.com/v1"
DEFAULT_MODEL_API4 = "gemini-3-pro-preview"

# -----------------------------------------------------------------------------
# ACH 自动化配置
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.absolute()
STORAGE_STATE_FILE = str(SCRIPT_DIR / "storage_state.json")
ACH_CONFIG_FILE = str(SCRIPT_DIR / "ach_config.json")
TARGET_URL = "https://ai.kangda1818.com/auth"

# 页面元素选择器
LOGO_OK_TEXT = "今日内不再提示"
LOGO_OK_BTN = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > aside > div.n-layout-sider-scroll-container > div > div > div.flex.justify-between.p-3 > div.n-space.flex-shrink-0 > div:nth-child(1) > button"
TEXTAREA_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.flex.items-center > div > div > div.n-input__textarea.n-scrollbar > textarea"
MODEL_BTN_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.input-tools > div > div:nth-child(1) > div > div:nth-child(1) > button"
MODEL_LIST_CONTAINER = "body > div.v-binder-follower-container > div > div > div > div.n-scrollbar-container > div > div"
MODEL_OPTIONS_SELECTOR = 'body > div.v-binder-follower-container > div > div > div.n-scrollbar > div.n-scrollbar-container > div > div > div > div > div'
ATTACHMENT_BTN_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.input-tools > div > div:nth-child(1) > div > div:nth-child(3) > div > div > button"
UPLOAD_CONFIRM_BTN = "div.n-card:has-text('多模态上传') button:has-text('确认')"
SEND_BTN_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.input-tools > div > div:nth-child(2) > div > div:nth-child(2) > div > button:nth-child(1)"
RESULT_IMG_SELECTOR = '#chat-content > div.n-scrollbar-container > div > div.chat-item.p-3.mode-list.ai > div > div.chat-text > div > div > div > p > img'

# =============================================================================
# API4 图像分析函数（内联）
# =============================================================================

def chat_with_ai_api(image_path, prompt, api_key=DEFAULT_API_KEY, base_url=DEFAULT_BASE_URL, model=DEFAULT_MODEL_API4):
    """与聊天AI API交互（支持图片）"""
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API密钥不能为空且必须是字符串类型")
    if not base_url or not isinstance(base_url, str):
        raise ValueError("API基础URL不能为空且必须是字符串类型")
    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词不能为空且必须是字符串类型")

    def _encode_image_to_base64(image_path):
        """将图片文件编码为base64格式"""
        try:
            with open(image_path, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except FileNotFoundError:
            raise FileNotFoundError(f"图片文件未找到: {image_path}")
        except Exception as e:
            raise Exception(f"读取图片文件失败: {str(e)}")

    def _send_chat_request(api_key, url, payload):
        """发送聊天API请求"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=160)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")

    # 编码图片为base64
    base64_image = _encode_image_to_base64(image_path)

    # 构建API请求URL
    chat_url = f"{base_url.rstrip('/')}/chat/completions"

    # 构建请求payload
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.7
    }

    # 发送请求并获取响应
    response_data = _send_chat_request(api_key, chat_url, payload)

    # 提取AI回复内容
    try:
        response_content = response_data['choices'][0]['message']['content']
        return response_content
    except (KeyError, IndexError) as e:
        raise Exception(f"解析API响应失败: {str(e)}, 响应内容: {response_data}")


# =============================================================================
# ACH 自动化函数（内联）
# =============================================================================

def ach_log_message(msg, level="info", show_toast=False):
    """ACH日志记录"""
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[ACH-{current_time}] {msg}"
    print(formatted_msg)
    if show_toast and TOASTER:
        title = "自动化脚本提醒" if level == "info" else "自动化脚本错误"
        try:
            TOASTER.show_toast(title, msg, duration=5, threaded=True)
        except Exception:
            pass


def ach_load_config(config_path=None):
    """加载ACH配置文件"""
    default_config = [{
        "banana_prompt": "默认提示词",
        "banana_ref_img1": "",
        "banana_ref_img2": "",
        "banana_model": "2",
        "banana_wait_time": "30",
        "banana_img_dir": os.getcwd(),
        "banana_save_name": "default_output"
    }]

    if config_path is None:
        config_path = ACH_CONFIG_FILE

    if not os.path.exists(config_path):
        ach_log_message(f"配置文件 {config_path} 未找到，使用默认配置")
        return default_config, False

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            configs = data if isinstance(data, list) else data.get('configs', [data])
            headless = data.get('headless', False) if isinstance(data, dict) else False
            return configs, headless
    except Exception as e:
        ach_log_message(f"读取配置文件出错: {e}，使用默认配置", level="error")
        return default_config, False


def ach_init_browser(playwright_instance, headless=True, storage_state_path=None):
    """初始化浏览器"""
    browser = playwright_instance.chromium.launch(headless=headless)
    if storage_state_path is None:
        storage_state_path = STORAGE_STATE_FILE
    if os.path.exists(storage_state_path):
        context = browser.new_context(storage_state=storage_state_path)
        ach_log_message(f"已加载历史认证状态，浏览器模式: {'无头' if headless else '有头'}")
    else:
        context = browser.new_context()
        ach_log_message(f"创建新会话，浏览器模式: {'无头' if headless else '有头'}")
    page = context.new_page()
    return browser, context, page


def ach_check_and_handle_login(page):
    """检查登录状态并处理"""
    try:
        page.goto(TARGET_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_load_state("domcontentloaded")
        content = page.text_content('body')
        is_logged_in = LOGO_OK_TEXT in content or page.locator(LOGO_OK_BTN).count() > 0
        if is_logged_in:
            ach_log_message("检测到已登录状态")
            if LOGO_OK_TEXT in content:
                try:
                    page.click(f"text={LOGO_OK_TEXT}", timeout=2000)
                    ach_log_message("已点击关闭提示弹窗")
                except:
                    pass
            elif page.locator(LOGO_OK_BTN).count() > 0:
                try:
                    page.locator(LOGO_OK_BTN).click(timeout=2000)
                    ach_log_message("已点击关闭提示按钮")
                except:
                    pass
            return True
        else:
            return False
    except Exception as e:
        ach_log_message(f"登录检查异常: {e}", level="error")
        return False


def ach_select_model(page, model_id):
    """选择模型"""
    page.locator(MODEL_BTN_SELECTOR).click()
    page.wait_for_selector(MODEL_LIST_CONTAINER)
    target_model_name = 'Chat-香蕉-画图-pro' if str(model_id) == "2" else 'Chat-香蕉-画图'
    options = page.locator(MODEL_OPTIONS_SELECTOR)
    count = options.count()
    for i in range(count):
        option = options.nth(i)
        text = option.text_content()
        if target_model_name in text:
            ach_log_message(f"选中模型: 【{text}】")
            option.click()
            return True
    ach_log_message(f"未找到模型: {target_model_name}，使用默认", level="error")
    return False


def ach_upload_images(page, img_path1, img_path2):
    """上传图片"""
    valid_paths = []
    for path in [img_path1, img_path2]:
        if path:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                valid_paths.append(abs_path)
            else:
                ach_log_message(f"警告: 图片文件不存在 {abs_path}", level="error")
    if not valid_paths:
        ach_log_message("无有效图片需上传")
        return
    page.locator(ATTACHMENT_BTN_SELECTOR).click()
    page.wait_for_selector("div.n-card:has-text('多模态上传')", timeout=10000)
    page.set_input_files("div.n-card:has-text('多模态上传') input[type='file']", valid_paths)
    ach_log_message(f"已上传 {len(valid_paths)} 个文件")
    page.wait_for_timeout(2000)
    page.locator(UPLOAD_CONFIRM_BTN).click()


def ach_convert_png_to_jpg(png_path, jpg_path):
    """PNG转JPG"""
    try:
        from PIL import Image
        with Image.open(png_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                rgb_img = background
            else:
                rgb_img = img.convert('RGB')
            rgb_img.save(jpg_path, 'JPEG', quality=100, optimize=False, subsampling=0)
        os.remove(png_path)
        ach_log_message(f"格式转换完成: {os.path.basename(png_path)} -> {os.path.basename(jpg_path)}")
        return True
    except Exception as e:
        ach_log_message(f"PNG转JPG失败: {e}", level="error")
        return False


def ach_download_image_result(page, config):
    """下载图片结果"""
    wait_sec = int(config.get("banana_wait_time", 60))
    wait_ms = wait_sec * 1000
    save_dir = config.get("banana_img_dir", os.getcwd())
    save_name = config.get("banana_save_name", "downloaded_image")
    model_suffix = config.get("banana_model", "1")
    temp_png_path = os.path.join(save_dir, f"{save_name}_{model_suffix}_temp.png")
    final_jpg_path = os.path.join(save_dir, f"{save_name}_{model_suffix}.jpg")

    ach_log_message(f"等待生成结果，最大等待 {wait_sec} 秒...")
    img_src = None
    try:
        img_locator = page.locator(RESULT_IMG_SELECTOR)
        img_locator.wait_for(state="visible", timeout=wait_ms)
        img_src = img_locator.get_attribute('src')
        ach_log_message("图片元素已出现")
    except Exception as e:
        ach_log_message(f"等待图片超时或出错: {e}", level="error")
        return False

    if img_src:
        try:
            os.makedirs(save_dir, exist_ok=True)
            response = requests.get(img_src)
            if response.status_code == 200:
                with open(temp_png_path, 'wb') as f:
                    f.write(response.content)
                ach_log_message(f"PNG图片下载成功: {temp_png_path}")
                if ach_convert_png_to_jpg(temp_png_path, final_jpg_path):
                    ach_log_message(f"最终图片保存成功: {final_jpg_path}", show_toast=True)
                    return True
                else:
                    ach_log_message(f"格式转换失败，保留PNG文件: {temp_png_path}", level="error")
                    return True
            else:
                ach_log_message(f"下载失败 HTTP Code: {response.status_code}", level="error")
        except Exception as e:
            ach_log_message(f"保存文件出错: {e}", level="error")
    return False


def ach_execute_single_task(page, config):
    """执行单个任务"""
    try:
        page.wait_for_load_state("networkidle")
        try:
            if page.locator(LOGO_OK_BTN).is_visible():
                page.locator(LOGO_OK_BTN).click()
        except:
            pass
        prompt = config.get("banana_prompt", "")
        textarea = page.locator(TEXTAREA_SELECTOR)
        textarea.wait_for(timeout=10000)
        textarea.fill(prompt)
        ach_log_message(f"已输入提示词: {prompt[:20]}...")
        ach_select_model(page, config.get("banana_model", "1"))
        ach_upload_images(page, config.get("banana_ref_img1"), config.get("banana_ref_img2"))
        ach_log_message("点击发送...")
        page.locator(SEND_BTN_SELECTOR).click()
        return ach_download_image_result(page, config)
    except Exception as e:
        ach_log_message(f"任务执行过程出错: {e}", level="error")
        return False


def ach_main(config_path=None, storage_state_path=None):
    """ACH主函数"""
    ach_log_message("=== ACH自动化脚本启动 ===")
    configs, headless_mode = ach_load_config(config_path)
    browser = None
    try:
        with sync_playwright() as p:
            browser, context, page = ach_init_browser(p, headless=headless_mode, storage_state_path=storage_state_path)
            if not ach_check_and_handle_login(page):
                ach_log_message("未检测到登录状态，需要手动登录")
                if headless_mode:
                    ach_log_message("错误：无头模式下无法手动登录", level="error")
                    return
                ach_log_message("请在浏览器中完成登录...")
                input(">>> 登录完成后，请按 Enter 键继续...")
                save_path = storage_state_path if storage_state_path else STORAGE_STATE_FILE
                context.storage_state(path=save_path)
                ach_log_message("登录状态已保存")
            save_path = storage_state_path if storage_state_path else STORAGE_STATE_FILE
            context.storage_state(path=save_path)
            total = len(configs)
            for i, config in enumerate(configs):
                ach_log_message(f"--- 开始执行任务 {i + 1}/{total} ---")
                success = ach_execute_single_task(page, config)
                if not success:
                    ach_log_message("任务失败，尝试切换至模型1重试...")
                    retry_config = config.copy()
                    retry_config["banana_model"] = "1"
                    if ach_execute_single_task(page, retry_config):
                        ach_log_message(f"任务 {i + 1} 重试成功")
                    else:
                        ach_log_message(f"任务 {i + 1} 重试仍然失败", level="error")
                ach_log_message(f"--- 任务 {i + 1} 结束 ---")
            ach_log_message("=== 所有任务已完成 ===", show_toast=True)
    except Exception as e:
        ach_log_message(f"全局未捕获异常: {e}", level="error", show_toast=True)
    finally:
        if browser:
            try:
                browser.close()
            except:
                pass
        ach_log_message("ACH程序已退出。")


# =============================================================================
# 主程序函数
# =============================================================================

def log_message(msg):
    """统一日志记录"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def get_output_folder_path(input_folder_path):
    """获取输出文件夹路径（与输入目录相同）"""
    return input_folder_path


def load_previous_config():
    """读取上次使用的配置信息"""
    config_file_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
    last_folder = ""
    last_prompt = DEFAULT_PROMPT

    # 如果配置文件不存在，创建默认配置
    if not os.path.exists(config_file_path):
        default_config = {
            "last_input_folder": "",
            "banana_prompt": DEFAULT_PROMPT,
            "configs": []
        }
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            log_message(f"已创建默认配置文件: {config_file_path}")
        except Exception as e:
            log_message(f"创建默认配置文件失败: {e}")
        return last_folder, last_prompt

    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    last_folder = data.get('last_input_folder', "")
                    last_prompt = data.get('banana_prompt', DEFAULT_PROMPT)
        except Exception as e:
            log_message(f"读取旧配置失败: {e}")

    return last_folder, last_prompt


def get_image_files(directory):
    """获取目录下所有图片文件"""
    if not os.path.exists(directory):
        raise FileNotFoundError(f"目录不存在: {directory}")

    # 递归查找所有子文件夹中的"*HB.jpg"文件
    poster_files = glob.glob(os.path.join(directory, "**", "*HB.jpg"), recursive=True)

    # 去重 (基于绝对路径)
    unique_image_paths = set()
    deduplicated_image_list = []
    for img_path in poster_files:
        abs_path = os.path.abspath(img_path)
        if abs_path not in unique_image_paths:
            unique_image_paths.add(abs_path)
            deduplicated_image_list.append(img_path)

    # 排序
    deduplicated_image_list = sorted(deduplicated_image_list)

    log_message(f"在目录 '{directory}' 及其子目录中找到 {len(deduplicated_image_list)} 个*HB.jpg文件")
    return deduplicated_image_list


def generate_prompt_for_image(image_path):
    """为单张图片生成提示词（带重试机制）"""
    # 提示词模板
    prompt_template = """# Role: 视觉重构导演 (Visual Reconstruction Director)

1. 核心任务
你的任务是接收用户上传的任意尺寸、带有复杂商业设计的海报（参考图），从中**提取核心视觉主体**，并编写一段中文自然语言提示词（Prompt）。这段提示词将用于指导AI模型生成一张**全新的、正方形（1:1）、纯净无杂质**的图片。

2. 必须遵守的铁律 (Iron Laws)

1.  **正方形强制重构 (Square Re-composition)**
    *   **重绘逻辑**：不要描述原图的长宽比。必须在脑海中将画面主体"剪切"下来，放置在一个正方形的画布中央。
    *   **填充与裁剪**：如果原图是长图（竖构图），提示词需描述主体为"半身特写"或"增加左右背景延伸"以填满正方形；如果原图是宽图，提示词需描述"聚焦主体"以去除多余边缘。
    *   **关键词植入**：输出中必须包含"正方形构图"、"居中构图"等词汇。

2.  **彻底去商业化 (De-Commercialization)**
    *   **去文字**：视所有文字、标题、LOGO、水印、二维码为"隐形"，**绝对不要在提示词中提及它们**。
    *   **去设计感**：视所有渐变色背景、透明遮罩、磨砂玻璃效果、光晕装饰为"杂质"，不予描述。
    *   **还原本质**：如果原图人物脚下有渐变阴影，你要描述为"清晰的地面"；如果背景是虚化颜色的色块，你要描述为"干净的纯色背景"或"真实的物理环境"。

3.  **自然语言指令化 (Natural Language Directing)**
    *   输出的不是"图片描述"，而是"生成指令"。
    *   使用高质量的形容词（如：高清、细腻、光影自然、大师级摄影）。
4.  **不允许出现任何其他内容**
    *   不允许出现思考过程、寒暄、任何没被允许的其他文字。


请直接输出以下内容，方便用户复制：


(一段流畅的中文自然语言。必须包含：正方形构图描述 + 主体细节 + 纯净背景描述 + 材质光影描述。**请在开头直接写明：一张正方形构图的...**)

"""

    max_retries = 2  # 最大重试次数

    for attempt in range(max_retries):
        try:
            if attempt == 0:
                log_message(f"正在处理图片: {os.path.basename(image_path)}")
            else:
                log_message(f"重试处理图片 ({attempt + 1}/{max_retries}): {os.path.basename(image_path)}")
                time.sleep(2)  # 重试前等待2秒

            result = chat_with_ai_api(
                image_path=image_path,
                prompt=prompt_template
            )
            log_message("提示词生成成功")
            return result.strip()

        except Exception as e:
            log_message(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt == max_retries - 1:
                log_message(f"所有重试都失败，跳过此图片: {os.path.basename(image_path)}")
                return None  # 返回None表示跳过

    return None  # 理论上不会到达这里


def create_config_item(image_path, prompt, output_dir, model, wait_time):
    """创建单个配置项"""
    image_name = os.path.splitext(os.path.basename(image_path))[0]

    return {
        "banana_prompt": prompt,
        "banana_ref_img1": image_path,
        "banana_ref_img2":"" ,
        "banana_model": model,
        "banana_wait_time": wait_time,
        "banana_link_or_right": "",
        "banana_img_dir": output_dir,
        "banana_save_name": image_name
    }


def clean_prompt_text(prompt):
    """清理提示词文本，删除英文字符和逗号句号之外的符号"""
    # 保留中文字符、数字、逗号、句号和空格，删除其他所有字符
    cleaned = re.sub(r'[a-zA-Z]', '', prompt)  # 删除英文字母
    cleaned = re.sub(r'[^一-龥、。，．0-9\\s]', '', cleaned)  # 保留中文、逗号、句号、数字和空格
    return cleaned.strip()


def rename_processed_files(directory):
    """重命名已处理的文件"""
    if not os.path.exists(directory):
        log_message(f"目录不存在: {directory}")
        return

    renamed_count = 0

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)

        if not os.path.isfile(file_path):
            continue

        if filename.endswith('HB_1.jpg'):
            new_filename = filename.replace('HB_1.jpg', 'ST.jpg')
            new_file_path = os.path.join(directory, new_filename)
        elif filename.endswith('HB_2.jpg'):
            new_filename = filename.replace('HB_2.jpg', 'ST.jpg')
            new_file_path = os.path.join(directory, new_filename)
        else:
            continue

        if os.path.exists(new_file_path):
            log_message(f"警告: 文件已存在，跳过重命名: {new_filename}")
            continue

        try:
            os.rename(file_path, new_file_path)
            log_message(f"重命名成功: {filename} -> {new_filename}")
            renamed_count += 1
        except Exception as e:
            log_message(f"重命名失败: {filename} -> {e}")

    log_message(f"重命名完成，共处理 {renamed_count} 个文件")


def clean_config_prompts(config_path):
    """清理配置文件中所有banana_prompt的值"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        if 'banana_prompt' in config_data:
            original_prompt = config_data['banana_prompt']
            config_data['banana_prompt'] = clean_prompt_text(original_prompt)
            log_message(f"已清理主提示词")

        if 'configs' in config_data and isinstance(config_data['configs'], list):
            cleaned_count = 0
            for item in config_data['configs']:
                if 'banana_prompt' in item:
                    original = item['banana_prompt']
                    item['banana_prompt'] = clean_prompt_text(original)
                    cleaned_count += 1
            log_message(f"已清理 {cleaned_count} 个配置项的提示词")

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        log_message("配置文件提示词清理完成")

    except Exception as e:
        log_message(f"清理配置文件提示词时出错: {e}")


def load_existing_configs(config_path):
    """加载现有的配置文件"""
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"读取配置文件失败: {e}")
            return {}
    return {}


def save_config_item(image_path, prompt, config_path, input_directory, headless, model, wait_time):
    """保存单个配置项到配置文件"""
    config_data = load_existing_configs(config_path)

    if not config_data:
        config_data = {
            "headless": headless,
            "last_input_folder": input_directory,
            "banana_prompt": prompt,
            "configs": []
        }

    output_dir = os.path.dirname(image_path)
    new_item = create_config_item(image_path, prompt, output_dir, model, wait_time)

    existing_paths = [item.get('banana_ref_img1', '') for item in config_data.get('configs', [])]
    if image_path not in existing_paths:
        config_data['configs'].append(new_item)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            log_message(f"已保存配置项: {os.path.basename(image_path)} (总计 {len(config_data['configs'])} 个任务)")
        except Exception as e:
            log_message(f"保存配置文件失败: {e}")
    else:
        log_message(f"配置项已存在，跳过: {os.path.basename(image_path)}")


def get_user_parameters(folder_path, last_prompt):
    """交互式获取用户参数"""
    print("\n默认模式参数:")
    print("- 浏览器模式: 无头模式 (headless)")
    print(f"- 模型选择: {DEFAULT_MODEL}")
    print(f"- 等待时间: {DEFAULT_WAIT_TIME}秒")
    print(f"- 输出文件夹: {get_output_folder_path(folder_path)}")
    print(f"- 提示词: {last_prompt}")
    print()

    mode_choice = input("请选择模式：1-默认模式，2-自定义模式: ").strip()

    headless = True
    model = DEFAULT_MODEL
    wait_time = DEFAULT_WAIT_TIME
    output_folder = get_output_folder_path(folder_path)
    prompt = last_prompt

    if mode_choice == "2":
        print(">>> 进入自定义模式")

        while True:
            h_input = input("请选择浏览器模式 (0-无头, 1-有头): ").strip()
            if h_input in ["0", "1"]:
                headless = not bool(int(h_input))
                break
            print("输入无效，请输入 0 或 1")

        while True:
            m_input = input("请选择模型 (1 或 2): ").strip()
            if m_input in ["1", "2"]:
                model = m_input
                break
            print("输入无效，请输入 1 或 2")

        while True:
            w_input = input("请输入等待时间 (秒): ").strip()
            if w_input.isdigit():
                wait_time = w_input
                break
            print("输入无效，请输入数字")

        o_input = input(f"请输入输出文件夹路径 (回车默认: {output_folder}): ").strip()
        if o_input:
            output_folder = o_input
            os.makedirs(output_folder, exist_ok=True)

        first_image_path = None
        for ext in SUPPORTED_EXTENSIONS:
            image_list = glob.glob(os.path.join(folder_path, ext), recursive=False)
            if image_list:
                first_image_path = image_list[0]
                break

        if first_image_path:
            log_message(f"正在分析图片: {first_image_path}")
            suggested_prompt = generate_prompt_for_image(first_image_path)
            log_message(f"API返回的提示词: {suggested_prompt[:50]}...")
            p_input = input(f"请输入提示词 (回车默认: {suggested_prompt}): ").strip()
            if p_input:
                prompt = p_input
            else:
                prompt = suggested_prompt
        else:
            p_input = input(f"请输入提示词 (回车默认: {prompt}): ").strip()
            if p_input:
                prompt = p_input

        log_message(f"自定义配置: {'无头' if headless else '有头'} | 模型{model} | 等待{wait_time}s")
    else:
        log_message("使用默认配置")

    return headless, model, wait_time, output_folder, prompt


def batch_process_images():
    """主函数：批量处理图片"""
    print("=" * 50)
    print("批量图片处理工具")
    print("=" * 50)

    # 1. 加载历史配置
    last_folder, last_prompt = load_previous_config()

    # 2. 获取输入目录
    default_folder = last_folder if last_folder else ""
    prompt_text = f"请输入要处理的图片目录路径 (留空使用上次: {default_folder}): " if default_folder else "请输入要处理的图片目录路径: "

    # 尝试从剪贴板获取路径
    clipboard_path = None
    try:
        import pyperclip
        clipboard_content = pyperclip.paste().strip()
        if clipboard_content and os.path.isdir(clipboard_content):
            clipboard_path = clipboard_content
            print(f"[检测到剪贴板中的路径: {clipboard_path}]")
    except:
        pass

    input_directory = input(prompt_text).strip()

    if not input_directory and clipboard_path:
        input_directory = clipboard_path
        log_message(f"使用剪贴板中的路径: {input_directory}")

    if not input_directory:
        input_directory = default_folder

    if not input_directory:
        log_message("错误: 目录路径不能为空")
        return

    try:
        if not os.path.isdir(input_directory):
            log_message(f"错误: 路径 '{input_directory}' 无效或不存在")
            return

        log_message(f"当前工作目录: {input_directory}")

        # 4. 选择执行模式
        print("\n执行模式选择:")
        print("1. 清空所有配置，重新开始处理")
        print("2. 跳过已处理项目，仅处理新项目")

        while True:
            mode_choice = input("请选择执行模式 (1 或 2): ").strip()
            if mode_choice in ["1", "2"]:
                execution_mode = int(mode_choice)
                break
            print("输入无效，请输入 1 或 2")

        # 5. 获取运行参数
        headless, model, wait_time, output_folder, prompt = get_user_parameters(input_directory, last_prompt)

        # 6. 根据模式获取待处理图片文件
        image_files = []

        if execution_mode == 1:
            config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
            if os.path.exists(config_path):
                os.remove(config_path)
                log_message("已清空ach配置文件")

            image_files = get_image_files(input_directory)

        elif execution_mode == 2:
            config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
            if os.path.exists(config_path):
                os.remove(config_path)
                log_message("已清空ach配置文件")

            savexiumi_config_path = os.path.join(input_directory, "savexiumi_config.json")
            if not os.path.exists(savexiumi_config_path):
                log_message(f"错误: 找不到savexiumi_config.json文件: {savexiumi_config_path}")
                return

            try:
                with open(savexiumi_config_path, 'r', encoding='utf-8') as f:
                    savexiumi_config = json.load(f)
            except Exception as e:
                log_message(f"读取savexiumi_config.json失败: {e}")
                return

            items = savexiumi_config.get("items", [])
            if not items:
                log_message("savexiumi_config.json中没有items数据")
                return

            log_message(f"从savexiumi_config.json读取到 {len(items)} 个items")

            skipped_count = 0
            error_count = 0

            for item in items:
                try:
                    first_image_relative = item.get("首图路径", "")
                    poster_relative = item.get("海报路径", "")

                    if not first_image_relative or not poster_relative:
                        log_message(f"跳过item: 首图路径或海报路径为空")
                        skipped_count += 1
                        continue

                    first_image_path = os.path.join(input_directory, first_image_relative)
                    poster_path = os.path.join(input_directory, poster_relative)

                    if os.path.exists(first_image_path):
                        log_message(f"跳过已处理项目: {os.path.basename(first_image_relative)}")
                        skipped_count += 1
                    else:
                        if os.path.exists(poster_path):
                            image_files.append(poster_path)
                            log_message(f"待处理: {os.path.basename(poster_path)}")
                        else:
                            log_message(f"错误: 海报文件不存在: {poster_relative}")
                            error_count += 1

                except Exception as e:
                    log_message(f"处理item时出错: {e}")
                    error_count += 1
                    continue

            log_message(f"过滤完成: 跳过 {skipped_count} 个已处理项目，找到 {len(image_files)} 个待处理项目，错误 {error_count} 个")

        if not image_files:
            log_message("没有需要处理的项目")
            return

        log_message(f"开始处理 {len(image_files)} 张图片...")

        # 7. 为每张图片生成提示词并实时保存配置
        config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
        processed_count = 0

        for i, image_path in enumerate(image_files, 1):
            log_message(f"正在处理第 {i}/{len(image_files)} 张图片...")
            prompt_text = generate_prompt_for_image(image_path)

            if prompt_text is not None:
                save_config_item(image_path, prompt_text, config_path, input_directory, headless, model, wait_time)
                processed_count += 1
                log_message(f"提示词: {prompt_text[:50]}...")
                print("-" * 30)
            else:
                log_message(f"跳过图片: {os.path.basename(image_path)}")
                print("-" * 30)

        if processed_count == 0:
            log_message("没有成功处理任何图片，程序结束")
            return

        log_message(f"总共成功处理 {processed_count} 张图片")
        log_message("配置文件已实时更新完成!")
        print("=" * 50)

        # 清理配置文件中的提示词
        clean_config_prompts(config_path)

        # 执行 ach.py
        log_message("开始执行 ach.py...")
        try:
            ach_main(config_path=CONFIG_FILENAME)
            log_message("所有任务执行完成!")
        except Exception as e:
            log_message(f"执行 ach.py 时出错: {e}")
            return

        # 重命名处理后的文件
        log_message("开始重命名处理后的文件...")
        try:
            rename_processed_files(input_directory)
            log_message("文件重命名完成!")
        except Exception as e:
            log_message(f"文件重命名时出错: {e}")

    except Exception as e:
        log_message(f"程序执行出错: {e}")


if __name__ == "__main__":
    try:
        batch_process_images()
    except KeyboardInterrupt:
        log_message("用户中断操作")
    except Exception as e:
        log_message(f"未预期的错误: {e}")
    finally:
        input("按 Enter 键退出...")
