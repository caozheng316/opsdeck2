# -*- coding: utf-8 -*-
"""
[功能概述]: Playwright 网页自动化模板，支持多账号登录状态保存与切换。
[启动准备]: 需安装 playwright 库，并运行 playwright install chromium。
[输入参数]: 
    - 直接运行: 修改 ACCOUNT_INDEX 配置选择账号
    - 调用运行: main(account_index=1, loop_configs=[...]) 传参
[输出内容]: 打开指定网页并等待用户操作，无文件输出。
[模块调用关系]: 调用 playwright.sync_api，可被其他模块调用。
[使用流程]: 
    1. 确保已安装 playwright 及浏览器驱动；
    2. 在 ACCOUNTS_CONFIG 中配置多个账号的用户数据目录；
    3. 填写 LOGIN_CHECK_ELEMENT 元素选择器（留空则不检查）；
    4. 配置 ENABLE_ENTER_PAGE_ACTIONS 和 LOOP_CONFIGS；
    5. 直接运行脚本或被其他模块调用。
[注意事项]: 
    - Windows 路径请使用 raw string (r"") 防止转义；
    - 首次运行需执行 playwright install chromium；
    - 插件路径需指向插件的根目录；
    - 每个账号使用独立的用户数据目录保存登录状态。
[可调整参数]: 
    - LOAD_EXTENSION: 是否加载扩展插件 (True/False)
    - EXTENSION_PATH: Chrome 扩展插件路径
    - ACCOUNTS_CONFIG: 多账号配置列表
    - ACCOUNT_INDEX: 账号索引（从0开始）
    - ENABLE_LOGIN_CHECK: 是否检测登录状态 (True/False)
    - LOGIN_CHECK_ELEMENT: 登录检查元素选择器
    - TARGET_URL: 目标网页地址
    - HEADLESS: 是否无头模式运行
    - ENABLE_ENTER_PAGE_ACTIONS: 是否执行进入页面动作 (True/False)
    - LOOP_CONFIGS: 循环动作配置列表
[调用示例]:
    # 方式1: 使用默认配置
    main()

    # 方式2: 指定账号索引
    main(account_index=1)

    # 方式3: 指定账号 + 自定义循环配置
    main(account_index=0, loop_configs=[
        {"prompt": "任务1", "save_name": "result1"},
        {"prompt": "任务2", "save_name": "result2"}
    ])

    # 方式4: 跳过进入页面动作（设置常量 ENABLE_ENTER_PAGE_ACTIONS = False）
    # 然后调用
    main(account_index=0, loop_configs=[{"prompt": "单任务", "save_name": "output"}])
"""

# === 1. 模块引入区 ===
import os
import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, BrowserContext, Page

# === 2. 常量配置区 ===
# 是否加载Chrome扩展插件 (True/False)
LOAD_EXTENSION = True
# Chrome扩展插件路径
EXTENSION_PATH = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data\Default\Extensions\ndgimibanhlabgdgjcpbbndiehljcpfh\5.6.2_0"
# 目标网页地址
TARGET_URL = "https://jimeng.jianying.com/ai-tool/generate?type=image"
# 是否无头模式运行 (True=无头, False=显示浏览器)
HEADLESS = False
# 超时时间 (毫秒)
TIMEOUT = 60000
# 是否按回车关闭网页 (这是调试模式，调试模式允许报错后不关闭浏览器，方便检查错误。True=按回车关闭, False=自动关闭)
WAIT_FOR_INPUT = True
# 待上传图片路径
UPLOAD_IMAGE_PATH = r"C:\Users\Administrator\Desktop\会员酒店11.png"

# 是否执行进入页面动作 (循环前的准备动作，True=执行, False=跳过)
ENABLE_ENTER_PAGE_ACTIONS = False

# 循环动作默认配置 (外部传参可覆盖)
LOOP_CONFIGS = [
    {
        "prompt": "任务1",
        "save_name": "result1"
    },
    # {
    #     "prompt": "任务2",
    #     "save_name": "result2"
    # }
]

# 多账号配置：直接运行时通过 ACCOUNT_INDEX 选择账号，调用时可通过参数覆盖
# 账号配置列表：每个账号独立的用户数据目录
ACCOUNTS_CONFIG = [
    {
        "name": "账号1",
        "user_data_dir": r"C:\Users\Administrator\Desktop\OpsDeck\playwright_user_data_account1"
    },
    {
        "name": "账号2",
        "user_data_dir": r"C:\Users\Administrator\Desktop\OpsDeck\playwright_user_data_account2"
    }
]

# 选择要使用的账号索引 (从0开始)
ACCOUNT_INDEX = 0

# 登录状态检测开关 (True=检测登录状态, False=跳过检测直接使用保存的登录状态)
ENABLE_LOGIN_CHECK = True
# 已登录状态下的元素选择器 (如用户头像、用户名等)
LOGIN_CHECK_ELEMENT = "#Personal > div > div > div > div > img"
# 检查登录状态时访问的页面URL
LOGIN_URL = "https://jimeng.jianying.com/ai-tool/generate?type=image"

# === 3. 函数区 ===
def setup_logging() -> None:
    """配置日志格式与级别"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def check_login_status(context: BrowserContext, check_url: str, check_element: str) -> tuple[bool, Optional[Page]]:
    """
    检查浏览器上下文是否已登录
    
    Args:
        context (BrowserContext): 浏览器上下文
        check_url (str): 检查登录状态时访问的页面URL
        check_element (str): 已登录状态下的元素选择器
        
    Returns:
        tuple[bool, Optional[Page]]: (是否已登录, 页面对象，如果不需要复用则返回None)
    """
    logger = logging.getLogger(__name__)
    
    try:
        page = context.new_page()
        page.goto(check_url, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle")
        
        if check_element:
            try:
                element = page.wait_for_selector(check_element, timeout=5000)
                if element:
                    logger.info("检测到登录状态元素，认为已登录")
                    return True, page
            except Exception:
                logger.info("未检测到登录状态元素，认为未登录")
                page.close()
                return False, None
        else:
            logger.warning("未配置登录检查元素，请手动确认登录状态")
            page.close()
            return False, None
            
    except Exception as e:
        logger.error(f"检查登录状态失败: {e}")
        return False, None


def select_account(accounts_config: list, account_index: int) -> dict:
    """
    选择要使用的账号
    
    Args:
        accounts_config (list): 账号配置列表
        account_index (int): 账号索引
        
    Returns:
        dict: 选中的账号配置
    """
    logger = logging.getLogger(__name__)
    
    if account_index < 0 or account_index >= len(accounts_config):
        logger.error(f"账号索引 {account_index} 超出范围，有效范围: 0-{len(accounts_config)-1}")
        raise ValueError(f"无效的账号索引: {account_index}")
    
    selected = accounts_config[account_index]
    logger.info(f"选中账号: {selected['name']}, 用户数据目录: {selected['user_data_dir']}")
    return selected


def validate_extension_path(extension_path: str) -> bool:
    """
    验证插件路径是否存在
    
    Args:
        extension_path (str): 插件路径
        
    Returns:
        bool: 路径是否存在
    """
    logger = logging.getLogger(__name__)
    if not os.path.exists(extension_path):
        logger.error(f"插件路径不存在: {extension_path}")
        return False
    logger.info(f"插件路径验证通过: {extension_path}")
    return True


def create_browser_context(playwright_instance, user_data_dir: str, extension_path: str, headless: bool = False, load_extension: bool = True) -> BrowserContext:
    """
    创建带有扩展插件的浏览器上下文
    
    Args:
        playwright_instance: Playwright 实例
        user_data_dir (str): 用户数据目录
        extension_path (str): 扩展插件路径
        headless (bool): 是否无头模式
        load_extension (bool): 是否加载扩展插件
        
    Returns:
        BrowserContext: 浏览器上下文对象
    """
    logger = logging.getLogger(__name__)
    
    user_data_path = Path(user_data_dir)
    user_data_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"用户数据目录: {user_data_path}")
    
    if load_extension:
        logger.info(f"加载扩展插件: {extension_path}")
        context = playwright_instance.chromium.launch_persistent_context(
            str(user_data_path),
            headless=headless,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--allow-running-insecure-content",
            ]
        )
    else:
        logger.info("跳过扩展插件加载")
        context = playwright_instance.chromium.launch_persistent_context(
            str(user_data_path),
            headless=headless
        )
    
    return context


def open_page(context: BrowserContext, url: str) -> Page:
    """
    打开指定网页
    
    Args:
        context (BrowserContext): 浏览器上下文
        url (str): 目标网址
        
    Returns:
        Page: 页面对象
    """
    logger = logging.getLogger(__name__)
    logger.info(f"正在打开网页: {url}")
    
    page = context.new_page()
    page.goto(url, timeout=TIMEOUT)
    
    logger.info("网页打开成功")
    return page


def enter_page_actions(page: Page, upload_image_path: str = None) -> None:
    """
    进入页面时执行一次的动作
    
    在页面刚加载完成后执行一次的操作，如：
    - 初始化页面设置
    - 点击模型选择按钮
    - 打开某个面板
    
    Args:
        page (Page): Playwright 页面对象
        upload_image_path (str): 待上传图片路径
    """
    logger = logging.getLogger(__name__)
    logger.info("执行进入页面动作...")
    
    if upload_image_path is None:
        upload_image_path = UPLOAD_IMAGE_PATH
    
    # === 在此处编写进入页面动作 ===
    # 示例：点击某个元素
    # page.click("#some-button")
    
    # 示例：等待元素加载
    # page.wait_for_selector("#element-id")
    
    # 示例：初始化页面设置
    # page.evaluate("() => { /* 初始化代码 */ }")
    
    logger.info("进入页面动作执行完成")


def loop_actions(page: Page, loop_config: dict, upload_image_path: str = None) -> bool:
    """
    循环执行的动作
    
    在 for in 循环中每次迭代执行的操作，如：
    - 上传图片
    - 输入提示词
    - 点击生成按钮
    - 保存结果
    
    Args:
        page (Page): Playwright 页面对象
        loop_config (dict): 循环任务配置，包含 prompt, save_name 等
        upload_image_path (str): 待上传图片路径
        
    Returns:
        bool: 执行是否成功
    """
    logger = logging.getLogger(__name__)
    
    if upload_image_path is None:
        upload_image_path = UPLOAD_IMAGE_PATH
    
    prompt = loop_config.get("prompt", "")
    save_name = loop_config.get("save_name", "result")
    
    logger.info(f"执行循环动作: {save_name}")
    
    try:
        # 点击模型选择按钮
        model_selector = page.locator('#dreamina-ui-configuration-content-wrapper > div.content-TZbgMr > div > div.dimension-layout-FUl4Nj.default-layout-bOIxyJ > div > div.toolbar-tBNbB3 > div.container-yMr4oW.toolbar-settings-YNMCja > div > div:nth-child(2) > div > span > span > svg')
        if model_selector.is_visible():
            print(f"模型选择按钮存在，文本内容为: {model_selector.text_content()}")
            model_selector.click()
        else:
            logger.error("模型选择按钮不存在")
            return False
        
        # === 在此处编写循环动作 ===
        # 示例：输入提示词
        # page.fill("#prompt-input", prompt)
        
        # 示例：上传图片
        # with page.expect_file_chooser() as fc_info:
        #     page.click("#upload-button")
        # file_chooser = fc_info.value
        # file_chooser.set_files(upload_image_path)
        
        # 示例：点击生成按钮
        # page.click("#generate-button")
        
        # 示例：等待生成完成
        # page.wait_for_selector("#result-container", timeout=120000)
        
        # 示例：保存结果
        # page.screenshot(path=f"output/{save_name}.png")
        
        logger.info(f"循环动作执行完成: {save_name}")
        return True
    except Exception as e:
        logger.error(f"循环动作执行失败: {e}")
        return False


def wait_for_user_input(prompt: str = "按回车键关闭浏览器...") -> None:
    """
    等待用户输入回车键
    
    Args:
        prompt (str): 提示信息
    """
    input(prompt)


# === 4. 主流程区 ===
def main(account_index: Optional[int] = None, loop_configs: list = None) -> None:
    """
    主流程入口，负责浏览器启动、页面操作与资源清理
    
    Args:
        account_index (Optional[int]): 账号索引，用于调用时指定账号。为 None 时使用常量 ACCOUNT_INDEX
        loop_configs (list): 循环任务配置列表，为 None 时使用常量 LOOP_CONFIGS
    """
    logger = logging.getLogger(__name__)
    
    setup_logging()
    
    if not validate_extension_path(EXTENSION_PATH) and LOAD_EXTENSION:
        logger.error("插件路径验证失败，程序退出")
        return
    
    selected_index = ACCOUNT_INDEX if account_index is None else account_index
    
    final_loop_configs = LOOP_CONFIGS if loop_configs is None else loop_configs
    
    try:
        account_config = select_account(ACCOUNTS_CONFIG, selected_index)
    except ValueError as e:
        logger.error(f"账号选择失败: {e}")
        return
    
    user_data_dir = account_config["user_data_dir"]
    
    playwright_instance = None
    context: Optional[BrowserContext] = None
    should_close_browser = True
    
    try:
        playwright_instance = sync_playwright().start()
        context = create_browser_context(
            playwright_instance,
            user_data_dir,
            EXTENSION_PATH,
            HEADLESS,
            LOAD_EXTENSION
        )
        
        page = None
        
        if LOAD_EXTENSION:
            logger.info("正在初始化扩展插件...")
            ext_id = Path(EXTENSION_PATH).parent.name
            ext_url = f"chrome-extension://{ext_id}/background.html"
            
            logger.info(f"扩展ID: {ext_id}")
            logger.info(f"扩展URL: {ext_url}")
            
            page = context.new_page()
            page.goto(TARGET_URL, timeout=TIMEOUT)
            page.wait_for_timeout(5000)
            logger.info(f"已导航到{TARGET_URL}激活扩展")
            
            if ENABLE_LOGIN_CHECK and LOGIN_CHECK_ELEMENT:
                try:
                    element = page.wait_for_selector(LOGIN_CHECK_ELEMENT, timeout=5000)
                    if element:
                        logger.info("检测到登录状态元素，认为已登录")
                except Exception as e:
                    logger.info(f"未检测到登录状态元素: {e}")
                    logger.info("请手动登录后再运行以保存登录状态")
                    input("按回车键退出...")
                    return
            elif not LOGIN_CHECK_ELEMENT:
                logger.warning("未配置登录检查元素，请手动确认登录状态")
            else:
                logger.info("跳过登录状态检测，直接使用保存的登录状态")
        else:
            if ENABLE_LOGIN_CHECK:
                logger.info("正在检查登录状态...")
                is_logged_in, page = check_login_status(context, LOGIN_URL, LOGIN_CHECK_ELEMENT)
                
                if is_logged_in:
                    logger.info("检测到已登录状态，将使用保存的登录状态")
                else:
                    logger.info("未检测到的登录状态，请手动登录后再运行以保存登录状态")
                    return
            else:
                logger.info("跳过登录状态检测，直接使用保存的登录状态")
        
        if page is None:
            page = open_page(context, TARGET_URL)
        # === 进入页面动作 ===
        if ENABLE_ENTER_PAGE_ACTIONS:
            enter_page_actions(page)
        else:
            logger.info("跳过进入页面动作")
        # === 循环动作 ===
        base_loop_config = final_loop_configs[0] if final_loop_configs else {}
        for loop_config in final_loop_configs:
            merged_config = {**base_loop_config, **loop_config}
            loop_actions(page, merged_config)
        
        if WAIT_FOR_INPUT:
            wait_for_user_input()
        else:
            logger.info("自动关闭模式，直接关闭浏览器")
        
        should_close_browser = True
        
    except Exception as e:
        logger.error(f"运行出错: {e}")
        logger.info("浏览器将保持打开状态以便调试，请手动关闭浏览器")
        should_close_browser = False
        logger.info(f"DEBUG: should_close_browser 设置为 {should_close_browser}")
        logger.info("脚本将阻塞等待，请手动关闭浏览器后再按回车退出...")
        try:
            input()
        except Exception:
            pass
    finally:
        logger.info(f"DEBUG: 进入 finally，should_close_browser = {should_close_browser}")
        if context and should_close_browser:
            context.close()
            logger.info("浏览器已关闭")
        elif context and not should_close_browser:
            logger.info("浏览器保持打开状态，请手动关闭")
        if playwright_instance and should_close_browser:
            try:
                playwright_instance.stop()
            except Exception:
                pass
        elif playwright_instance and not should_close_browser:
            logger.info("Playwright 保持运行，浏览器由用户手动关闭")


# === 5. 执行区 ===
if __name__ == '__main__':
    main()
