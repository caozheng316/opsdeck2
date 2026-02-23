# -*- coding: utf-8 -*-
"""
[功能概述]: 即梦AI（jimeng）图片生成自动化模板，支持多账号登录状态保存与批量图片生成下载。
[启动准备]: 需安装 playwright、requests、Pillow 库，并运行 playwright install chromium。
[输入参数]: 
    - 直接运行: 修改 ACCOUNT_INDEX 配置选择账号，修改 LOOP_CONFIGS 配置任务列表
    - 调用运行: main(account_index=1, loop_configs=[...]) 传参
[输出内容]: 根据 LOOP_CONFIGS 配置，在 download_dir 目录下生成指定格式的图片文件及日志。
[模块调用关系]: 调用 playwright.sync_api、requests、PIL，可被其他模块调用。
[使用流程]: 
    1. 确保已安装 playwright 及浏览器驱动（playwright install chromium）；
    2. 在 ACCOUNTS_CONFIG 中配置多个账号的用户数据目录；
    3. 在 LOOP_CONFIGS 中配置要生成的任务列表（提示词、图片比例、上传图片路径、保存目录等）；
    4. 配置 ASPECT_RATIO_SELECTORS 比例选择器映射表；
    5. 调整 TARGET_URL、HEADLESS、TIMEOUT 等全局参数；
    6. 直接运行脚本或被其他模块调用。
[注意事项]: 
    - Windows 路径请使用 raw string (r"") 防止转义；
    - 首次运行需执行 playwright install chromium；
    - 插件路径需指向插件的根目录；
    - 每个账号使用独立的用户数据目录保存登录状态；
    - 批量生成时 WAIT_IMAGE_TIMEOUT 需设置足够长以等待AI生成完成。
[可调整参数]: 
    - LOAD_EXTENSION: 是否加载扩展插件 (True/False)
    - EXTENSION_PATH: Chrome 扩展插件路径
    - TARGET_URL: 目标网页地址
    - HEADLESS: 是否无头模式运行 (True=无头, False=显示浏览器)
    - TIMEOUT: 页面加载超时时间 (毫秒)
    - WAIT_IMAGE_TIMEOUT: 图片生成等待时间 (毫秒)
    - WAIT_FOR_INPUT: 是否等待回车关闭网页 (True=等待, False=自动关闭)
    - UPLOAD_IMAGE_PATH: 待上传图片路径
    - ENABLE_ENTER_PAGE_ACTIONS: 是否执行进入页面动作 (True/False)
    - LOOP_CONFIGS: 循环动作配置列表（包含 prompt、save_name_template、aspect_ratio、upload_image_path、old_file_name、file_extension、download_dir）
    - ASPECT_RATIO_SELECTORS: 图片比例选择器映射表
    - ACCOUNTS_CONFIG: 多账号配置列表
    - ACCOUNT_INDEX: 账号索引（从0开始）
    - ENABLE_LOGIN_CHECK: 是否检测登录状态 (True/False)
    - LOGIN_CHECK_ELEMENT: 登录检查元素选择器
    - LOGIN_URL: 检查登录状态时访问的页面URL
[调用示例]:
    # 方式1: 使用默认配置
    main()

    # 方式2: 指定账号索引
    main(account_index=1)

    # 方式3: 指定账号 + 自定义循环配置
    main(account_index=0, loop_configs=[
        {"prompt": "任务1", "save_name_template": "result_{index}", "aspect_ratio": "1:1", "file_extension": "jpg", "download_dir": r"C:\\output"},
        {"prompt": "任务2", "save_name_template": "result_{index}", "aspect_ratio": "16:9", "file_extension": "png", "download_dir": r"C:\\output"}
    ])

    # 方式4: 使用外部 JSON 配置文件（参考 EXTERNAL_CONFIG_FILE 常量）
    # 先设置 EXTERNAL_CONFIG_FILE = r"C:\path\to\config.json"
    # 然后调用 main()，或者直接传参:
    main(external_config_file=r"C:\path\to\config.json")

    注意：如果jimeng积分不够，则需要换账号。这个逻辑当前还没有写出，当出现积分不够的时候再做这个逻辑。牵扯到多账号循环切换，包括字典是否需要添加此逻辑相关参数。如果AI读到这一段，请提醒用户。

"""

# === 1. 模块引入区 ===
import os
import logging
from pathlib import Path
from typing import Optional
import requests
from PIL import Image

from playwright.sync_api import sync_playwright, BrowserContext, Page

# === 2. 常量配置区 ===
# 是否加载Chrome扩展插件 (True/False)
LOAD_EXTENSION = False
# Chrome扩展插件路径
EXTENSION_PATH = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data\Default\Extensions\ndgimibanhlabgdgjcpbbndiehljcpfh\5.6.2_0"
# 目标网页地址
TARGET_URL = "https://jimeng.jianying.com/ai-tool/generate?type=image"
# 是否无头模式运行 (True=无头, False=显示浏览器)
HEADLESS = False
# 超时时间 (毫秒)
TIMEOUT = 60000
# 图片生成等待时间 (毫秒)
WAIT_IMAGE_TIMEOUT = 120000
# 是否按回车关闭网页 (这是调试模式，调试模式允许报错后不关闭浏览器，方便检查错误。True=按回车关闭, False=自动关闭)
WAIT_FOR_INPUT = True
# 待上传图片路径
UPLOAD_IMAGE_PATH = r"C:\Users\Administrator\Desktop\会员酒店11.png"
# 是否执行进入页面动作 (循环前的准备动作，True=执行, False=跳过)
ENABLE_ENTER_PAGE_ACTIONS = False

# 循环动作默认配置 (外部传参可覆盖)
# save_name_template: 动态文件名模板，使用 f-string 格式，可用的变量有:
#   - {index}: 任务索引（从1开始）
#   - {prompt}: 提示词内容（仅保留前20个字符）
#   - {aspect_ratio}: 图片比例
# 示例: "result_{index}_{prompt}_{aspect_ratio}" -> "result_1_去掉图片中的建筑_9:16"
# file_extension: 图片输出格式，如 "jpg", "png", "bmp" 等
LOOP_CONFIGS = [
    {
        "prompt": "黄昏的场景，天空中有一只会飞的翼龙剪影，注意不改变参考图中主体的比例。",
        "save_name_template": "大理洱海游船",
        "aspect_ratio": "1:1",
        "upload_image_path": r"C:\Users\Administrator\Desktop\公众号文章\output\大理洱海游船1.jpg",
        "old_file_name": "大理洱海游船1",
        "file_extension": "jpg",
        "download_dir": r"C:\Users\Administrator\Desktop\公众号文章\output"
    },
        {
        "prompt": "黄昏的场景，天空中有一只会飞的翼龙剪影，注意不改变参考图中主体的比例。",
        "save_name_template": "古镇吊脚楼",
        "aspect_ratio": "1:1",
        "upload_image_path": r"C:\Users\Administrator\Desktop\公众号文章\output\古镇吊脚楼1.jpg",
        "old_file_name": "古镇吊脚楼1",
        "file_extension": "jpg",
        "download_dir": r"C:\Users\Administrator\Desktop\公众号文章\output"
    },    {
        "prompt": "黄昏的场景，天空中有一只会飞的翼龙剪影，注意不改变参考图中主体的比例。",
        "save_name_template": "泸沽湖猪槽船",
        "aspect_ratio": "1:1",
        "upload_image_path": r"C:\Users\Administrator\Desktop\公众号文章\output\泸沽湖猪槽船1.jpg",
        "old_file_name": "泸沽湖猪槽船1",
        "file_extension": "jpg",
        "download_dir": r"C:\Users\Administrator\Desktop\公众号文章\output"
    },    {
        "prompt": "黄昏的场景，天空中有一只会飞的翼龙剪影，注意不改变参考图中主体的比例。",
        "save_name_template": " 芽庄五指岩",
        "aspect_ratio": "1:1",
        "upload_image_path": r"C:\Users\Administrator\Desktop\公众号文章\output\芽庄五指岩1.jpg",
        "old_file_name": "芽庄五指岩1",
        "file_extension": "jpg",
        "download_dir": r"C:\Users\Administrator\Desktop\公众号文章\output"
    },
]

# 比例选择按钮选择器映射表 (由用户填写实际选择器)
ASPECT_RATIO_SELECTORS = {
    "智能": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(1) > div > div > span",      # TODO: 填写选择器
    "21:9": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(2) > div > div > span",      # TODO: 填写选择器
    "16:9": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(3) > div > div > span",      # TODO: 填写选择器
    "3:2": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(4) > div > div > span",       # TODO: 填写选择器
    "4:3": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(5) > div > div > span",       # TODO: 填写选择器
    "1:1": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(6) > div > div > span",       # TODO: 填写选择器
    "3:4": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(7) > div > div > span",       # TODO: 填写选择器
    "2:3": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(8) > div > div > span",       # TODO: 填写选择器
    "9:16": "body > div:nth-child(74) > span > div > div > div > div > div > div:nth-child(1) > div.lv-radio-group.lv-radio-size-small.lv-radio-mode-outline.radio-group-nSistg.radio-group-csT79P > label:nth-child(9) > div > div > span",      # TODO: 填写选择器
}

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
ENABLE_LOGIN_CHECK = False
# 已登录状态下的元素选择器 (如用户头像、用户名等)
LOGIN_CHECK_ELEMENT = "#Personal > div > div > div > div > img"
# 检查登录状态时访问的页面URL
LOGIN_URL = "https://jimeng.jianying.com/ai-tool/generate?type=image"

# 外部配置文件路径（用于字典调用方法）
# 设置为外部 JSON 配置文件的绝对路径，为 None 时不使用外部配置
# JSON 文件格式参考下方 EXTERNAL_CONFIG_TEMPLATE
EXTERNAL_CONFIG_FILE = None

# === 3. 函数区 ===
def setup_logging() -> None:
    """配置日志格式与级别"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def load_external_config(config_file: str) -> dict:
    """
    从外部 JSON 文件加载配置
    
    Args:
        config_file (str): 外部配置文件路径
        
    Returns:
        dict: 加载的配置字典，包含 account_index 和 loop_configs
    """
    import json
    logger = logging.getLogger(__name__)
    
    if not config_file or not os.path.exists(config_file):
        logger.error(f"外部配置文件不存在: {config_file}")
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"成功加载外部配置文件: {config_file}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}")
        return {}
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {}


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


def download_preview_image(url: str, save_path: str) -> bool:
    """
    下载预览图片
    
    Args:
        url (str): 图片的 URL 地址
        save_path (str): 保存路径
        
    Returns:
        bool: 下载是否成功
    """
    logger = logging.getLogger(__name__)
    try:
        headers = {
            "Referer": "https://jimeng.jianying.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(response.content)
        logger.info(f"图片已保存到: {save_path}")
        return True
    except Exception as e:
        logger.error(f"图片下载失败: {e}")
        return False


def convert_image_format(source_path: str, target_extension: str) -> str:
    """
    将图片转换为指定格式
    
    Args:
        source_path (str): 源图片路径
        target_extension (str): 目标格式，如 "jpg", "png", "bmp" 等
        
    Returns:
        str: 转换后的文件路径，失败返回原路径
    """
    logger = logging.getLogger(__name__)
    try:
        target_ext = target_extension.lower().strip(".")
        base_path = os.path.splitext(source_path)[0]
        target_path = f"{base_path}.{target_ext}"
        
        with Image.open(source_path) as img:
            if target_ext == "jpg" or target_ext == "jpeg":
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(target_path, quality=95, optimize=False)
            elif target_ext == "png":
                img.save(target_path, compress_level=0)
            else:
                img.save(target_path)
        
        logger.info(f"图片已转换为 {target_ext} 格式: {target_path}")
        if source_path != target_path and os.path.exists(source_path):
            os.remove(source_path)
            logger.info(f"已删除原文件: {source_path}")
        return target_path
    except Exception as e:
        logger.error(f"图片格式转换失败: {e}")
        return source_path


def loop_actions(page: Page, loop_config: dict, task_index: int = 1) -> bool:
    """
    循环执行的动作
    
    在 for in 循环中每次迭代执行的操作，如：
    - 上传图片
    - 输入提示词
    - 点击生成按钮
    - 保存结果
    
    Args:
        page (Page): Playwright 页面对象
        loop_config (dict): 循环任务配置，包含 save_name_template, prompt, upload_image_path 等
        task_index (int): 任务索引（从1开始），用于 save_name_template 模板渲染
        
    Returns:
        bool: 执行是否成功
    """
    logger = logging.getLogger(__name__)
    
    upload_image_path = loop_config.get("upload_image_path") or UPLOAD_IMAGE_PATH
    download_dir = loop_config.get("download_dir", "output")
    
    prompt = loop_config.get("prompt", "")
    aspect_ratio = loop_config.get("aspect_ratio", "1:1")
    
    save_name_template = loop_config.get("save_name_template")
    prompt_short = prompt[:20] if prompt else "empty"
    save_file_name = save_name_template.format(index=task_index, prompt=prompt_short, aspect_ratio=aspect_ratio)
    
    logger.info(f"执行循环动作: {save_file_name}")
    
    try:
        # 点击模型选择按钮
        model_selector = page.locator('#dreamina-ui-configuration-content-wrapper > div.content-TZbgMr > div > div.dimension-layout-FUl4Nj.default-layout-bOIxyJ > div > div.toolbar-tBNbB3 > div.container-yMr4oW.toolbar-settings-YNMCja > div > div:nth-child(2) > div > span > span > svg')       
        model_selector.click()
        # 点击第一个匹配文本的元素
        page.locator("//li[@class='lv-select-option lv-select-option-wrapper-selected lv-select-option-wrapper-hover']//div[@class='option-content-ythv8w']").click()
        print("已选择第一个模型")
        #点击比例选择按钮
        page.locator("//button[@class='lv-btn lv-btn-secondary lv-btn-size-default lv-btn-shape-square button-lc3WzE toolbar-button-FhFnQ_']//*[name()='svg']//*[name()='g']//*[name()='path' and contains(@data-follow-fill,'currentCol')]").click()
        print("已点击选择比例按钮")
        
        # === 比例选择逻辑 ===
        aspect_ratio = loop_config.get("aspect_ratio", "1:1")
        if aspect_ratio and aspect_ratio in ASPECT_RATIO_SELECTORS:
            ratio_selector = ASPECT_RATIO_SELECTORS[aspect_ratio]
            if ratio_selector:
                page.locator(ratio_selector).click()
                logger.info(f"已选择比例: {aspect_ratio}")
            else:
                logger.warning(f"比例 {aspect_ratio} 的选择器未填写，跳过")
        else:
            logger.warning(f"未配置有效比例，使用默认比例")
        # === 比例选择逻辑结束 ===
        # 点击空白确认选择
        page.locator('textarea.lv-textarea.textarea-rfj34A.prompt-textarea-l5tJNE').click()
        print("已点击输入框")
        # 输入框page.locator('textarea.lv-textarea.textarea-rfj34A.prompt-textarea-l5tJNE')里输入文字prompt
        page.locator('textarea.lv-textarea.textarea-rfj34A.prompt-textarea-l5tJNE').fill(prompt)
        print(f"已输入提示词: {prompt}")
        
        # 点击上传区域（含隐藏的 input[type=file]），静默上传图片
        upload_div = page.locator("div.reference-upload-h7tmnr input[type='file']")
        upload_div.set_input_files(upload_image_path)
        logger.info(f"静默上传图片完成: {upload_image_path}")

        # 方法四（改进版）：用JS给旧图片打标记，点击发送后等待新图片
        page.evaluate("""() => {
            const images = document.querySelectorAll('.image-record-content-TuJi21 img');
            images.forEach((img, index) => {
                img.setAttribute('data-old-image', 'true');
                img.setAttribute('data-image-index', index);
            });
        }""")
        print("已给现有图片打标记")

        #点击发送按钮
        page.locator("#dreamina-ui-configuration-content-wrapper > div.content-TZbgMr > div > div.dimension-layout-FUl4Nj.default-layout-bOIxyJ > div > div.toolbar-tBNbB3 > div.toolbar-actions-DsJHmQ > div:nth-child(2) > button").click()
        print("已点击发送按钮")

        # 等待新图片出现 - 等待没有 data-old-image 属性的新图片
        new_image_element = page.locator('.image-record-content-TuJi21 img:not([data-old-image="true"])').first
        new_image_element.wait_for(state="visible", timeout=WAIT_IMAGE_TIMEOUT)
        print("已加载生成图片")

        # 点击新生成的图片元素
        new_image_element.click()
        print("已点击图片")
        
        # 等待预览图片加载完成 - 使用稳定的类名，排除隐藏元素
        page.locator(".image-player-container-NU4Ona .image-TLmgkP:not(.imageHide-ye_uQO)").wait_for(state="visible", timeout=WAIT_IMAGE_TIMEOUT)
        print("已加载预览图片")

        # 点击元素page.locator(".image-player-container-NU4Ona .image-TLmgkP:not(.imageHide-ye_uQO)")
        page.locator(".image-player-container-NU4Ona .image-TLmgkP:not(.imageHide-ye_uQO)").click()
        print("已点击预览图片")
        
        # 获取预览图片 - 使用更稳定的选择器方式
        # 方式1: 通过modal类的 img 标签定位
        try:
            preview_img = page.locator(".enlarge-image-preview-modal-Fn89FO img").first
            preview_img.wait_for(state="visible", timeout=30000)
            preview_image_src = preview_img.get_attribute("src")
        except Exception:
            # 方式2: 尝试查找modal容器内的img标签
            try:
                preview_img = page.locator(".lv-modal-content img").first
                preview_img.wait_for(state="visible", timeout=30000)
                preview_image_src = preview_img.get_attribute("src")
            except Exception:
                # 方式3: 查找任何可见的大图img（排除缩略图）
                preview_img = page.locator("div.lv-modal-content img[src*='http']").first
                preview_img.wait_for(state="visible", timeout=30000)
                preview_image_src = preview_img.get_attribute("src")
        
        print(f"预览图片的src属性值: {preview_image_src}")

        # 下载预览图片（临时保存为 webp）
        temp_preview_path = os.path.join(download_dir, f"{save_file_name}.webp")
        download_preview_image(preview_image_src, temp_preview_path)
        
        # 转换为指定格式
        file_extension = loop_config.get("file_extension", "png")
        final_preview_path = convert_image_format(temp_preview_path, file_extension)
        print(f"已保存预览图片: {final_preview_path}")
        #刷新网页
        page.reload()
        print("已刷新网页")
        # 等待元素出现#dreamina-ui-configuration-content-wrapper > div.content-TZbgMr > div > div.dimension-layout-FUl4Nj.default-layout-bOIxyJ > div > div.content-oZ2zsI > div.main-content-pao8ef > div > textarea
        page.locator("textarea.lv-textarea.textarea-rfj34A.prompt-textarea-l5tJNE").wait_for(state="visible", timeout=WAIT_IMAGE_TIMEOUT)
        print("已加载输入框")
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
        # page.wait_for_selector("#result-container", timeout=WAIT_IMAGE_TIMEOUT)
        
        # 示例：保存结果
        # page.screenshot(path=os.path.join("output", f"{save_file_name}.png"))
        
        logger.info(f"循环动作执行完成: {save_file_name}")
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
def main(account_index: Optional[int] = None, loop_configs: list = None, external_config_file: str = None) -> None:
    """
    主流程入口，负责浏览器启动、页面操作与资源清理
    
    Args:
        account_index (Optional[int]): 账号索引，用于调用时指定账号。为 None 时使用常量 ACCOUNT_INDEX 或外部配置文件
        loop_configs (list): 循环任务配置列表，为 None 时使用常量 LOOP_CONFIGS 或外部配置文件
        external_config_file (str): 外部配置文件路径，为 None 时使用常量 EXTERNAL_CONFIG_FILE
    """
    logger = logging.getLogger(__name__)
    
    setup_logging()
    
    config_file = external_config_file if external_config_file else EXTERNAL_CONFIG_FILE
    
    if config_file:
        external_config = load_external_config(config_file)
        if external_config:
            if account_index is None and 'account_index' in external_config:
                account_index = external_config['account_index']
            if loop_configs is None and 'loop_configs' in external_config:
                loop_configs = external_config['loop_configs']
            logger.info("已从外部配置文件加载配置")
    
    if not validate_extension_path(EXTENSION_PATH) and LOAD_EXTENSION:
        logger.error("插件路径验证失败，程序退出")
        return
    
    if not LOAD_EXTENSION:
        logger.info("当前配置不加载扩展插件，跳过扩展路径验证")
    
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
        for task_index, loop_config in enumerate(final_loop_configs, start=1):
            merged_config = {**base_loop_config, **loop_config}
            loop_actions(page, merged_config, task_index=task_index)
        
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
