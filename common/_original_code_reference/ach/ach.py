# -*- coding: utf-8 -*-
"""
=============================================================
ACH自动化处理模块使用说明
=============================================================

功能概述:
--------
该模块是一个基于Playwright的自动化脚本，专门用于处理AI绘画任务。
主要功能包括：自动登录认证、模型选择、图片上传、提示词输入、
结果等待和图片下载等完整流程的自动化执行。

启动时的准备界面:
----------------
1. 系统会自动检查登录状态
2. 如未登录且为无头模式，会提示错误并退出
3. 如未登录且为有头模式，会暂停等待用户手动登录
4. 登录完成后会自动保存认证状态供下次使用

输入参数要求:
------------
配置文件格式 (ach_config.json):
[
    {
        "banana_prompt": "提示词内容",
        "banana_ref_img1": "参考图片1路径",
        "banana_ref_img2": "参考图片2路径",
        "banana_model": "模型选择(1或2)",
        "banana_wait_time": "等待时间(秒)",
        "banana_img_dir": "输出目录路径",
        "banana_save_name": "保存文件名前缀"
    }
]

或者字典格式:
{
    "headless": false,
    "configs": [
        {...},  # 同上配置项
        {...}
    ]
}

输出内容:
--------
- 处理后的图片文件：自动转换为 {save_name}_{model}.jpg 格式（最高保真度）
- 临时文件：下载过程中会产生_temp.png临时文件，处理完成后自动删除
- 运行日志：控制台实时输出处理进度和状态
- 桌面通知：任务完成时的气泡提醒（Windows系统）
- 认证状态：自动保存的登录cookies文件

模块调用关系:
------------
被调用模块:
- 3_poster_background_extractor.py (上级调用)
- save_xiumi.py (可能的调用)

调用的外部模块:
- playwright.sync_api (浏览器自动化)
- requests (图片下载)
- PIL.Image (图片处理，如果安装)
- win10toast (桌面通知，可选)

使用流程:
--------
1. 首次运行：需要手动登录并保存认证状态
2. 配置准备：准备ach_config.json配置文件
3. 脚本执行：运行main()函数开始自动化处理
4. 结果获取：在指定目录查看处理完成的图片
5. 断点续传：支持从失败的任务点继续执行

注意事项:
--------
1. 首次运行必须在有头模式下完成登录认证
2. 确保网络连接稳定，避免请求超时
3. 图片文件路径必须存在且可访问
4. 配置文件编码应为UTF-8格式
5. 建议在稳定的网络环境下运行
6. 处理大量任务时注意系统资源占用

可调整参数说明:
----------------
1. banana_prompt: AI绘画的提示词内容
2. banana_model: 模型选择 (1=基础模型, 2=专业模型)
3. banana_wait_time: 结果等待时间(秒)，根据网络情况调整
4. banana_img_dir: 输出图片保存的目录路径
5. headless: 浏览器模式 (True=无头模式, False=有头模式)
6. TARGET_URL: 目标网站地址(一般不需要修改)
7. 超时设置: 各种等待操作的超时时间可在代码中调整

=============================================================
"""
# 1. 【导入区】
import os
import json
import time
import datetime
import requests
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 尝试导入 Windows 通知模块
try:
    from win10toast import ToastNotifier

    TOASTER = ToastNotifier()
except ImportError:
    TOASTER = None
    print("[System]: win10toast模块未安装，将不显示桌面气泡通知 (pip install win10toast)")

# 2. 【配置区】
# -----------------------------------------------------------------------------
# 全局配置
# -----------------------------------------------------------------------------
# 获取脚本所在目录（动态路径）
SCRIPT_DIR = Path(__file__).parent.absolute()
# 认证状态存储文件路径
STORAGE_STATE_FILE = str(SCRIPT_DIR / "storage_state.json")
# 默认配置文件路径
CONFIG_FILE = str(SCRIPT_DIR / "ach_config.json")
# 目标网站地址
TARGET_URL = "https://ai.kangda1818.com/auth"

# -----------------------------------------------------------------------------
# 页面元素选择器 (Selectors)
# -----------------------------------------------------------------------------
# 登录/欢迎页 "今日内不再提示" 按钮或文本
LOGO_OK_TEXT = "今日内不再提示"
LOGO_OK_BTN = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > aside > div.n-layout-sider-scroll-container > div > div > div.flex.justify-between.p-3 > div.n-space.flex-shrink-0 > div:nth-child(1) > button"

# 提示词输入框
TEXTAREA_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.flex.items-center > div > div > div.n-input__textarea.n-scrollbar > textarea"

# 模型选择按钮
MODEL_BTN_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.input-tools > div > div:nth-child(1) > div > div:nth-child(1) > button"

# 模型列表容器 (用于等待列表出现)
MODEL_LIST_CONTAINER = "body > div.v-binder-follower-container > div > div > div > div.n-scrollbar-container > div > div"

# 模型选项列表 (用于遍历)
MODEL_OPTIONS_SELECTOR = 'body > div.v-binder-follower-container > div > div > div.n-scrollbar > div.n-scrollbar-container > div > div > div > div > div'

# 附件上传按钮
ATTACHMENT_BTN_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.input-tools > div > div:nth-child(1) > div > div:nth-child(3) > div > div > button"

# 上传弹窗确认按钮
UPLOAD_CONFIRM_BTN = "div.n-card:has-text('多模态上传') button:has-text('确认')"

# 发送按钮
SEND_BTN_SELECTOR = "#app-main > div.global-layout.user-layout.h-full.flex.flex-col > div > div > div > div > div > div > div > div > div > div > div > div.text-left > div.aa-chat-input > div.input-tools > div > div:nth-child(2) > div > div:nth-child(2) > div > button:nth-child(1)"

# 生成结果图片
RESULT_IMG_SELECTOR = '#chat-content > div.n-scrollbar-container > div > div.chat-item.p-3.mode-list.ai > div > div.chat-text > div > div > div > p > img'


# 3. 【功能区】
def log_message(msg, level="info", show_toast=False):
    """
    统一日志记录
    功能：控制台打印 + 气泡通知
    Args:
        msg (str): 日志内容
        level (str): 日志级别 (info/error)
        show_toast (bool): 是否显示桌面气泡
    """
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{current_time}] {msg}"
    print(formatted_msg)

    if show_toast and TOASTER:
        title = "自动化脚本提醒" if level == "info" else "自动化脚本错误"
        try:
            TOASTER.show_toast(title, msg, duration=5, threaded=True)
        except Exception:
            pass


def load_config(config_path=None):
    """
    加载配置文件
    Args:
        config_path (str, optional): 配置文件路径，默认使用脚本目录下的ach_config.json
    Returns:
        tuple: (配置列表, headless模式布尔值)
    """
    default_config = [{
        "banana_prompt": "默认提示词",
        "banana_ref_img1": "",
        "banana_ref_img2": "",
        "banana_model": "2",
        "banana_wait_time": "30",
        "banana_img_dir": os.getcwd(),
        "banana_save_name": "default_output"
    }]

    # 如果没有提供配置路径，则使用默认路径
    if config_path is None:
        config_path = CONFIG_FILE
    
    if not os.path.exists(config_path):
        log_message(f"配置文件 {config_path} 未找到，使用默认配置")
        return default_config, False

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 兼容列表格式或字典格式
            configs = data if isinstance(data, list) else data.get('configs', [data])
            return configs, headless
    except Exception as e:
        log_message(f"读取配置文件出错: {e}，使用默认配置", level="error")
        return default_config, False


def init_browser(playwright_instance, headless=True, storage_state_path=None):
    """
    初始化浏览器和上下文
    功能：自动加载本地存储状态(Cookies)
    Args:
        playwright_instance: Playwright实例
        headless (bool): 是否无头模式
        storage_state_path (str, optional): 存储状态文件路径，默认使用脚本目录下的storage_state.json
    """
    browser = playwright_instance.chromium.launch(headless=headless)

    # 如果没有提供存储状态路径，则使用默认路径
    if storage_state_path is None:
        storage_state_path = STORAGE_STATE_FILE
    
    if os.path.exists(storage_state_path):
        context = browser.new_context(storage_state=storage_state_path)
        log_message(f"已加载历史认证状态，浏览器模式: {'无头' if headless else '有头'}")
    else:
        context = browser.new_context()
        log_message(f"创建新会话，浏览器模式: {'无头' if headless else '有头'}")

    page = context.new_page()
    return browser, context, page


def check_and_handle_login(page):
    """
    检查登录状态并处理
    """
    try:
        page.goto(TARGET_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_load_state("domcontentloaded")

        # 检查是否已登录 (通过查找特定文本或按钮)
        content = page.text_content('body')
        is_logged_in = LOGO_OK_TEXT in content or page.locator(LOGO_OK_BTN).count() > 0

        if is_logged_in:
            log_message("检测到已登录状态")
            # 尝试点击"不再提示"
            if LOGO_OK_TEXT in content:
                try:
                    page.click(f"text={LOGO_OK_TEXT}", timeout=2000)
                    log_message("已点击关闭提示弹窗")
                except:
                    pass
            elif page.locator(LOGO_OK_BTN).count() > 0:
                try:
                    page.locator(LOGO_OK_BTN).click(timeout=2000)
                    log_message("已点击关闭提示按钮")
                except:
                    pass
            return True
        else:
            return False
    except Exception as e:
        log_message(f"登录检查异常: {e}", level="error")
        return False


def select_model(page, model_id):
    """
    在下拉列表中选择指定模型
    """
    # 点击模型菜单
    page.locator(MODEL_BTN_SELECTOR).click()
    page.wait_for_selector(MODEL_LIST_CONTAINER)

    # 确定目标模型名称
    target_model_name = 'Chat-香蕉-画图-pro' if str(model_id) == "2" else 'Chat-香蕉-画图'

    # 遍历选项
    options = page.locator(MODEL_OPTIONS_SELECTOR)
    count = options.count()

    for i in range(count):
        option = options.nth(i)
        text = option.text_content()
        if target_model_name in text:
            log_message(f"选中模型: 【{text}】")
            option.click()
            return True

    log_message(f"未找到模型: {target_model_name}，使用默认", level="error")
    return False


def upload_images(page, img_path1, img_path2):
    """
    处理图片上传逻辑
    """
    valid_paths = []
    for path in [img_path1, img_path2]:
        if path:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                valid_paths.append(abs_path)
            else:
                log_message(f"警告: 图片文件不存在 {abs_path}", level="error")

    if not valid_paths:
        log_message("无有效图片需上传")
        return

    # 点击附件按钮
    page.locator(ATTACHMENT_BTN_SELECTOR).click()
    # 等待上传面板
    page.wait_for_selector("div.n-card:has-text('多模态上传')", timeout=10000)

    # 设置文件 (Playwright set_input_files)
    page.set_input_files("div.n-card:has-text('多模态上传') input[type='file']", valid_paths)
    log_message(f"已上传 {len(valid_paths)} 个文件")

    # 点击确认
    page.wait_for_timeout(2000)
    page.locator(UPLOAD_CONFIRM_BTN).click()


def convert_png_to_jpg_high_quality(png_path, jpg_path):
    """
    将PNG图片转换为JPG格式，使用最高保真度设置
    Args:
        png_path (str): PNG文件路径
        jpg_path (str): 输出JPG文件路径
    Returns:
        bool: 转换是否成功
    """
    try:
        from PIL import Image
        
        # 打开PNG图片
        with Image.open(png_path) as img:
            # 处理透明度（如果有）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                # 粘贴图片到白色背景上
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                rgb_img = background
            else:
                # 转换为RGB模式
                rgb_img = img.convert('RGB')
            
            # 保存为JPG格式，使用最高质量设置
            # quality=100: 最高质量
            # optimize=False: 不进行优化压缩
            # subsampling=0: 最高质量的色度子采样
            rgb_img.save(jpg_path, 'JPEG', quality=100, optimize=False, subsampling=0)
            
        # 删除原PNG文件
        os.remove(png_path)
        log_message(f"格式转换完成: {os.path.basename(png_path)} -> {os.path.basename(jpg_path)}")
        return True
        
    except Exception as e:
        log_message(f"PNG转JPG失败: {e}", level="error")
        return False


def download_image_result(page, config):
    """
    等待生成并下载图片，自动转换为JPG格式
    """
    wait_sec = int(config.get("banana_wait_time", 60))
    wait_ms = wait_sec * 1000
    save_dir = config.get("banana_img_dir", os.getcwd())
    save_name = config.get("banana_save_name", "downloaded_image")
    model_suffix = config.get("banana_model", "1")
    
    # 临时PNG文件路径
    temp_png_path = os.path.join(save_dir, f"{save_name}_{model_suffix}_temp.png")
    # 最终JPG文件路径
    final_jpg_path = os.path.join(save_dir, f"{save_name}_{model_suffix}.jpg")

    log_message(f"等待生成结果，最大等待 {wait_sec} 秒...")

    img_src = None

    try:
        # 尝试正常等待图片可见
        img_locator = page.locator(RESULT_IMG_SELECTOR)
        img_locator.wait_for(state="visible", timeout=wait_ms)
        img_src = img_locator.get_attribute('src')
        log_message("图片元素已出现")

    except Exception as e:
        log_message(f"等待图片超时或出错: {e}", level="error")
        return False

    if img_src:
        try:
            os.makedirs(save_dir, exist_ok=True)
            response = requests.get(img_src)
            if response.status_code == 200:
                # 先保存为临时PNG文件
                with open(temp_png_path, 'wb') as f:
                    f.write(response.content)
                log_message(f"PNG图片下载成功: {temp_png_path}")
                
                # 转换为JPG格式并删除PNG文件
                if convert_png_to_jpg_high_quality(temp_png_path, final_jpg_path):
                    log_message(f"最终图片保存成功: {final_jpg_path}", show_toast=True)
                    return True
                else:
                    # 转换失败时保留PNG文件
                    log_message(f"格式转换失败，保留PNG文件: {temp_png_path}", level="error")
                    return True  # PNG保存成功也算成功
            else:
                log_message(f"下载失败 HTTP Code: {response.status_code}", level="error")
        except Exception as e:
            log_message(f"保存文件出错: {e}", level="error")

    return False


def execute_single_task(page, config):
    """
    执行单个任务流程
    """
    try:
        # 1. 确保页面加载
        page.wait_for_load_state("networkidle")

        # 2. 点击可能存在的欢迎弹窗
        try:
            if page.locator(LOGO_OK_BTN).is_visible():
                page.locator(LOGO_OK_BTN).click()
        except:
            pass

        # 3. 输入提示词
        prompt = config.get("banana_prompt", "")
        textarea = page.locator(TEXTAREA_SELECTOR)
        textarea.wait_for(timeout=10000)
        textarea.fill(prompt)
        log_message(f"已输入提示词: {prompt[:20]}...")

        # 4. 选择模型
        select_model(page, config.get("banana_model", "1"))

        # 5. 上传图片
        upload_images(page, config.get("banana_ref_img1"), config.get("banana_ref_img2"))

        # 6. 发送请求
        log_message("点击发送...")
        page.locator(SEND_BTN_SELECTOR).click()

        # 7. 等待并下载
        return download_image_result(page, config)

    except Exception as e:
        log_message(f"任务执行过程出错: {e}", level="error")
        return False


# 4. 【主逻辑区】
def main(manual_login=False, config_path=None, storage_state_path=None):
    """
    主程序入口
    Args:
        manual_login (bool): 是否手动登录
        config_path (str, optional): 配置文件路径
        storage_state_path (str, optional): 存储状态文件路径
    """
    log_message("=== 自动化脚本启动 ===")

    # 1. 加载配置
    configs, headless_mode = load_config(config_path)

    browser = None
    try:
        with sync_playwright() as p:
            # 2. 初始化浏览器
            browser, context, page = init_browser(p, headless=headless_mode, storage_state_path=storage_state_path)

            # 3. 登录检查
            if not check_and_handle_login(page):
                log_message("未检测到登录状态，需要手动登录")
                if headless_mode:
                    log_message("错误：无头模式下无法手动登录，请先在有头模式下运行一次以保存状态。", level="error")
                    return

                log_message("请在浏览器中完成登录...")
                input(">>> 登录完成后，请按 Enter 键继续...")

                # 保存登录状态
                save_path = storage_state_path if storage_state_path else STORAGE_STATE_FILE
                context.storage_state(path=save_path)
                log_message("登录状态已保存")

            # 再次保存状态以防万一
            save_path = storage_state_path if storage_state_path else STORAGE_STATE_FILE
            context.storage_state(path=save_path)

            # 4. 循环执行任务
            total = len(configs)
            for i, config in enumerate(configs):
                log_message(f"--- 开始执行任务 {i + 1}/{total} ---")

                success = execute_single_task(page, config)

                # 失败重试逻辑 (原代码逻辑：失败则尝试模型1)
                if not success:
                    log_message("任务失败，尝试切换至模型1重试...")
                    retry_config = config.copy()
                    retry_config["banana_model"] = "1"
                    if execute_single_task(page, retry_config):
                        log_message(f"任务 {i + 1} 重试成功")
                    else:
                        log_message(f"任务 {i + 1} 重试仍然失败", level="error")

                log_message(f"--- 任务 {i + 1} 结束 ---")

            log_message("=== 所有任务已完成 ===", show_toast=True)

    except Exception as e:
        log_message(f"全局未捕获异常: {e}", level="error", show_toast=True)
    finally:
        if browser:
            # 注意：在 sync 模式下，退出 context manager 会自动关闭，但显式关闭更安全
            try:
                browser.close()
            except:
                pass
        log_message("程序已退出。")


# 5. 【启动区】
if __name__ == "__main__":
    # 支持在最后暂停，防止窗口闪退
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户强制停止")
    finally:
        input("按 Enter 键退出...")
