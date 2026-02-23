# -*- coding: utf-8 -*-
"""
[功能概述]: 即梦AI图片生成自动化脚本，实现参考图+提示词生成图片的完整流程。
[启动准备]: 需安装 playwright 库，首次运行需要手动登录保存认证状态。
[输入参数]: 通过 CONFIG_DICT 配置运行参数，包括参考图片路径、提示词等。
[输出内容]: 自动化操作日志，生成的图片将在网页上显示。
[模块调用关系]: 独立运行模块，使用 playwright 进行浏览器自动化。
[使用流程]: 
    1. 首次运行需要手动登录；
    2. 修改 CONFIG_DICT 中的参数；
    3. 运行脚本自动执行图片生成流程。
[注意事项]: 遇到错误时不会关闭浏览器，需手动关闭；Windows路径使用raw string。
[可调整参数]: 
    - HEADLESS: 浏览器无头模式
    - REFERENCE_IMAGE_PATH: 参考图片路径
    - PROMPT_TEXT: 提示词内容
    - TIMEOUT: 超时时间设置
"""
# === 1. 模块引入区 ===
import os
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# === 2. 常量配置区 ===
SCRIPT_DIR = Path(__file__).parent.absolute()
STORAGE_STATE_FILE = str(SCRIPT_DIR / "jimeng_storage_state.json")

TARGET_URL = "https://jimeng.jianying.com/ai-tool/home"

TIMEOUT = 60000
UPLOAD_WAIT_TIME = 5000
GENERATION_WAIT_TIME = 120000

HEADLESS = False

REFERENCE_IMAGE_PATH = r"C:\Users\Administrator\Desktop\野途2\NM-20260210-082110-0001-ST.jpg"
PROMPT_TEXT = "pan camera slightly left, low angle"

CONFIG_DICT = {
    "headless": HEADLESS,
    "configs": [
        {
            "reference_image": REFERENCE_IMAGE_PATH,
            "prompt": PROMPT_TEXT
        }
    ]
}

# === 3. 函数区 ===
def setup_logging() -> logging.Logger:
    """配置日志记录器"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()


def init_browser(playwright_instance, headless: bool = False, storage_state_path: Optional[str] = None):
    """
    初始化浏览器和上下文，自动加载本地存储状态
    
    Args:
        playwright_instance: Playwright实例
        headless (bool): 是否无头模式
        storage_state_path (str, optional): 存储状态文件路径
        
    Returns:
        tuple: (browser, context, page)
    """
    browser = playwright_instance.chromium.launch(headless=headless)
    
    if storage_state_path is None:
        storage_state_path = STORAGE_STATE_FILE
    
    if os.path.exists(storage_state_path):
        context = browser.new_context(storage_state=storage_state_path)
        logger.info(f"已加载历史认证状态，浏览器模式: {'无头' if headless else '有头'}")
    else:
        context = browser.new_context()
        logger.info(f"创建新会话，浏览器模式: {'无头' if headless else '有头'}")
    
    page = context.new_page()
    return browser, context, page


def check_login_status(page) -> bool:
    """
    检查登录状态
    
    Args:
        page: Playwright页面对象
        
    Returns:
        bool: 是否已登录
    """
    try:
        logger.info(f"正在访问目标URL: {TARGET_URL}")
        page.goto(TARGET_URL, timeout=TIMEOUT)
        logger.info("页面加载完成，等待网络空闲...")
        
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("网络空闲状态已达到")
        except Exception as e:
            logger.warning(f"等待网络空闲超时，继续执行: {e}")
        
        page.wait_for_timeout(3000)
        
        login_button_count = page.get_by_text("登录", exact=True).count()
        logger.info(f"登录按钮数量: {login_button_count}")
        
        if login_button_count > 0:
            logger.info("检测到未登录状态")
            return False
        
        logger.info("检测到已登录状态")
        return True
        
    except Exception as e:
        logger.error(f"登录状态检查异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def navigate_to_image_generation(page) -> bool:
    """
    导航到图片生成功能
    
    Args:
        page: Playwright页面对象
        
    Returns:
        bool: 操作是否成功
    """
    try:
        logger.info("步骤1: 点击'生成'按钮")
        page.get_by_text("生成", exact=True).click()
        page.wait_for_timeout(1000)
        
        logger.info("步骤2: 点击下拉菜单")
        page.locator("div.lv-select-view:visible").click()
        page.wait_for_timeout(1000)
        
        logger.info("步骤3: 选择'图片生成'")
        page.locator("span").filter(has_text="图片生成").first.click()
        page.wait_for_timeout(1000)
        
        logger.info("成功导航到图片生成功能")
        return True
        
    except Exception as e:
        logger.error(f"导航到图片生成功能失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def upload_reference_image(page, image_path: str) -> bool:
    """
    静默上传参考图片
    
    Args:
        page: Playwright页面对象
        image_path (str): 参考图片路径
        
    Returns:
        bool: 上传是否成功
    """
    try:
        if not os.path.exists(image_path):
            logger.error(f"参考图片不存在: {image_path}")
            return False
        
        abs_image_path = os.path.abspath(image_path)
        logger.info(f"步骤4: 上传参考图片: {abs_image_path}")
        
        file_input = page.locator("input[type='file']").first
        
        file_input.set_input_files(abs_image_path)
        
        logger.info(f"步骤5: 等待图片上传完成...")
        page.wait_for_timeout(UPLOAD_WAIT_TIME)
        
        logger.info("参考图片上传成功")
        return True
        
    except Exception as e:
        logger.error(f"上传参考图片失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def input_prompt(page, prompt: str) -> bool:
    """
    输入提示词
    
    Args:
        page: Playwright页面对象
        prompt (str): 提示词内容
        
    Returns:
        bool: 输入是否成功
    """
    try:
        logger.info(f"步骤6: 输入提示词: {prompt}")
        
        textarea = page.locator("textarea.lv-textarea.textarea-rfj34A.prompt-textarea-l5tJNE:visible")
        textarea.wait_for(timeout=TIMEOUT)
        textarea.fill(prompt)
        
        logger.info("提示词输入成功")
        return True
        
    except Exception as e:
        logger.error(f"输入提示词失败: {e}")
        return False


def submit_and_wait(page) -> bool:
    """
    发送请求并等待生成结果
    
    Args:
        page: Playwright页面对象
        
    Returns:
        bool: 操作是否成功
    """
    try:
        logger.info("步骤7: 点击发送按钮")
        
        page.wait_for_timeout(2000)
        
        submit_button = page.locator("button.submit-button-KJTUYS").first
        
        for i in range(30):
            if submit_button.is_visible() and submit_button.is_enabled():
                break
            logger.info(f"等待发送按钮变为可用状态... ({i+1}/30)")
            page.wait_for_timeout(1000)
        
        if not submit_button.is_enabled():
            logger.error("发送按钮仍然被禁用")
            return False
        
        submit_button.click()
        
        logger.info(f"步骤8: 等待图片生成完成...")
        
        result_selector = "//div[@class='image-card-wrapper-WOgXrk landscape-Ven8Mz']//div[2]//div[1]//div[1]//div[1]//img[1]"
        
        page.locator(result_selector).wait_for(state="visible", timeout=GENERATION_WAIT_TIME)
        
        logger.info("图片生成完成")
        return True
        
    except Exception as e:
        logger.error(f"发送或等待生成失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def click_result_image(page) -> bool:
    """
    点击生成的图片
    
    Args:
        page: Playwright页面对象
        
    Returns:
        bool: 操作是否成功
    """
    try:
        logger.info("步骤9: 点击生成的图片")
        
        result_selector = "//div[@class='image-card-wrapper-WOgXrk landscape-Ven8Mz']//div[2]//div[1]//div[1]//div[1]//img[1]"
        page.locator(result_selector).click()
        
        logger.info("已点击生成的图片")
        return True
        
    except Exception as e:
        logger.error(f"点击生成图片失败: {e}")
        return False


def execute_single_task(page, config: Dict[str, Any]) -> bool:
    """
    执行单个图片生成任务
    
    Args:
        page: Playwright页面对象
        config (Dict[str, Any]): 任务配置
        
    Returns:
        bool: 任务是否成功
    """
    try:
        reference_image = config.get("reference_image", REFERENCE_IMAGE_PATH)
        prompt = config.get("prompt", PROMPT_TEXT)
        
        if not navigate_to_image_generation(page):
            return False
        
        if not upload_reference_image(page, reference_image):
            return False
        
        if not input_prompt(page, prompt):
            return False
        
        if not submit_and_wait(page):
            return False
        
        if not click_result_image(page):
            return False
        
        logger.info("任务执行成功")
        return True
        
    except Exception as e:
        logger.error(f"任务执行过程出错: {e}")
        return False


# === 4. 主流程区 ===
def main():
    """主流程入口，负责配置加载与循环调度"""
    logger.info("=== 即梦AI图片生成自动化脚本启动 ===")
    
    config_data = CONFIG_DICT
    headless_mode = config_data.get("headless", HEADLESS)
    configs = config_data.get("configs", [{}])
    
    browser = None
    context = None
    
    try:
        logger.info("正在初始化 Playwright...")
        with sync_playwright() as p:
            logger.info("正在启动浏览器...")
            browser, context, page = init_browser(p, headless=headless_mode)
            logger.info("浏览器启动成功，开始检查登录状态...")
            
            login_ok = check_login_status(page)
            logger.info(f"登录状态检查结果: {login_ok}")
            
            if not login_ok:
                logger.info("未检测到登录状态，需要手动登录")
                if headless_mode:
                    logger.error("错误：无头模式下无法手动登录，请先在有头模式下运行一次以保存状态。")
                    return
                
                logger.info("请在浏览器中完成登录...")
                input(">>> 登录完成后，请按 Enter 键继续...")
                
                context.storage_state(path=STORAGE_STATE_FILE)
                logger.info("登录状态已保存")
            else:
                logger.info("已检测到登录状态，继续执行...")
            
            context.storage_state(path=STORAGE_STATE_FILE)
            logger.info("认证状态已保存")
            
            total = len(configs)
            for i, config in enumerate(configs):
                logger.info(f"--- 开始执行任务 {i + 1}/{total} ---")
                
                success = execute_single_task(page, config)
                
                if success:
                    logger.info(f"任务 {i + 1} 执行成功")
                else:
                    logger.error(f"任务 {i + 1} 执行失败")
                
                logger.info(f"--- 任务 {i + 1} 结束 ---")
            
            logger.info("=== 所有任务已完成 ===")
            
            logger.info("脚本执行完毕，浏览器保持打开状态，请手动关闭...")
            input(">>> 按 Enter 键退出脚本（浏览器将保持打开）...")
            
    except Exception as e:
        import traceback
        logger.error(f"全局未捕获异常: {e}")
        logger.error(traceback.format_exc())
        logger.info("发生错误，浏览器保持打开状态，请手动关闭...")
        input(">>> 按 Enter 键退出脚本...")
        
    finally:
        logger.info("程序已退出")


# === 5. 执行区 ===
if __name__ == '__main__':
    main()
