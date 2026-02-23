# -*- coding: utf-8 -*-
"""
=============================================================
CT_DIR.py - 批量图片处理工具（完全独立版本）
=============================================================

功能概述:
--------
批量处理图片文件，生成配置并调用自动化任务。
已将 ach.py 模块代码完全内联，无需外部依赖。

特点:
------
- 完全独立运行，无需 common 文件夹
- 自动生成配置文件（如不存在）
- 批量处理目录中的所有图片
- 自动跳过已处理的图片
- 自动创建输出目录
- 内置 Playwright 自动化脚本

使用方法:
--------
直接运行: python CT_DIR.py
或带参数运行: python CT_DIR.py "C:\Images"
"""

# =============================================================================
# 1. 导入区
# =============================================================================
import os
import json
import glob
import re
import sys
import time
import datetime
import requests
from pathlib import Path

# Playwright 导入
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 尝试导入可选模块
try:
    from win10toast import ToastNotifier
    TOASTER = ToastNotifier()
except ImportError:
    TOASTER = None
    print("[System]: win10toast模块未安装，将不显示桌面气泡通知 (pip install win10toast)")

# =============================================================================
# 2. 配置区
# =============================================================================
# 配置文件名称
CONFIG_FILENAME = "savexiumi_config.json"

# 默认提示词
DEFAULT_PROMPT = "pan camera slightly left, low angle"

# 默认模型选择
DEFAULT_MODEL = "2"

# 默认等待时间
DEFAULT_WAIT_TIME = "180"

# 支持的图片扩展名
SUPPORTED_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png']

# -----------------------------------------------------------------------------
# ACH 自动化配置
# -----------------------------------------------------------------------------
# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.absolute()
# 认证状态存储文件路径
STORAGE_STATE_FILE = str(SCRIPT_DIR / "storage_state.json")
# 默认配置文件路径
ACH_CONFIG_FILE = str(SCRIPT_DIR / "ach_config.json")
# 目标网站地址
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
# 3. 功能区 - ACH 自动化函数
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
# 4. 功能区 - CT_DIR 主函数
# =============================================================================

def log_message(msg):
    """统一日志记录"""
    print(f"[Log]: {msg}")


def get_output_folder_path(input_folder_path):
    """获取输出文件夹路径"""
    parent_dir = os.path.dirname(input_folder_path)
    input_dir_name = os.path.basename(input_folder_path)
    output_dir_name = f"{input_dir_name}_output"
    output_folder_path = os.path.join(parent_dir, output_dir_name)
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path, exist_ok=True)
        log_message(f"创建输出目录: {output_folder_path}")
    return output_folder_path


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


def save_current_config(config_data):
    """保存当前配置到文件"""
    config_file_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
    try:
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        log_message(f"配置已保存到: {config_file_path}")
        return True
    except Exception as e:
        log_message(f"保存配置出错: {e}")
        return False


def scan_and_generate_config(image_folder, headless, model, wait_time, output_folder, prompt):
    """扫描图片并生成配置数据结构"""
    existing_files_base_names = set()
    if os.path.exists(output_folder):
        for filename in os.listdir(output_folder):
            if filename.lower().endswith(tuple(ext.replace('*', '') for ext in SUPPORTED_EXTENSIONS)):
                base_name = os.path.splitext(filename)[0]
                base_name_cleaned = re.sub(r'_\d+$', '', base_name)
                existing_files_base_names.add(base_name_cleaned)

    image_list = []
    for ext in SUPPORTED_EXTENSIONS:
        image_list.extend(glob.glob(os.path.join(image_folder, ext), recursive=False))
        image_list.extend(glob.glob(os.path.join(image_folder, ext.upper()), recursive=False))

    unique_image_paths = set()
    deduplicated_image_list = []
    for img_path in image_list:
        abs_path = os.path.abspath(img_path)
        if abs_path not in unique_image_paths:
            unique_image_paths.add(abs_path)
            deduplicated_image_list.append(img_path)

    config_items = []
    for image_path in deduplicated_image_list:
        image_filename = os.path.basename(image_path)
        save_name = os.path.splitext(image_filename)[0]

        if save_name in existing_files_base_names:
            log_message(f"跳过已存在图片: {image_filename}")
            continue

        item = {
            "banana_prompt": prompt,
            "banana_ref_img1": image_path,
            "banana_ref_img2": "",
            "banana_model": model,
            "banana_wait_time": wait_time,
            "banana_link_or_right": "",
            "banana_img_dir": output_folder,
            "banana_save_name": save_name
        }
        config_items.append(item)

    config_data = {
        "headless": headless,
        "last_input_folder": image_folder,
        "banana_prompt": prompt,
        "configs": config_items
    }
    return config_data


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
        p_input = input(f"请输入提示词 (回车默认: {prompt}): ").strip()
        if p_input:
            prompt = p_input
        log_message(f"自定义配置: {'无头' if headless else '有头'} | 模型{model} | 等待{wait_time}s")
    else:
        log_message("使用默认配置")

    return headless, model, wait_time, output_folder, prompt


# =============================================================================
# 5. 主逻辑区
# =============================================================================

def main(input_folder=None):
    """主程序入口"""
    log_message("程序启动...")
    last_folder, last_prompt = load_previous_config()

    if not input_folder:
        default_folder = last_folder if last_folder else ""
        prompt_text = f"请输入图片文件夹路径 (留空使用上次: {default_folder}): " if default_folder else "请输入图片文件夹路径: "
        user_input = input(prompt_text).strip()
        folder_path = user_input if user_input else default_folder
    else:
        folder_path = input_folder

    if not folder_path or not os.path.isdir(folder_path):
        log_message(f"错误: 路径 '{folder_path}' 无效或不存在")
        return

    log_message(f"当前工作目录: {folder_path}")

    headless, model, wait_time, output_folder, prompt = get_user_parameters(folder_path, last_prompt)

    config_data = scan_and_generate_config(
        image_folder=folder_path,
        headless=headless,
        model=model,
        wait_time=wait_time,
        output_folder=output_folder,
        prompt=prompt
    )

    if not config_data["configs"]:
        log_message("未找到待处理的图片，程序结束。")
        return

    log_message(f"生成任务配置: 共 {len(config_data['configs'])} 个任务")

    if save_current_config(config_data):
        ach_log_message("正在调用ACH自动化脚本...")
        ach_main()
        log_message("所有任务执行完毕！")


# =============================================================================
# 6. 启动区
# =============================================================================
if __name__ == "__main__":
    try:
        initial_path = sys.argv[1] if len(sys.argv) > 1 else None
        main(initial_path)
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"\n发生未预期的错误: {e}")
