"""
[功能概述]
使用 Playwright 自动化小红书图片下载：打开搜索页面，人工点击笔记后检测图片，弹窗确认后下载到本地。

[启动准备]
1. 安装依赖：pip install playwright requests
2. 安装浏览器：playwright install chromium
3. 确保下载目录存在：C:\\Users\\Administrator\\Desktop\\公众号文章\\img

[输入参数]
- keyword: 搜索关键词（默认：青岛栈桥）
- 可通过命令行参数覆盖

[输出内容]
- 控制台日志：显示操作步骤和下载状态
- 下载图片：保存到桌面 "公众号文章/img" 文件夹

[模块调用关系]
- 调用：playwright (浏览器自动化)
- 调用：requests (图片下载)
- 调用：ctypes (Windows对话框)

[使用流程]
1. 运行脚本：python 2_xhs_img.py
2. 浏览器自动打开小红书搜索页
3. 人工在页面点击某个笔记
4. 检测到图片后弹出 Windows 对话框
5. 点击"是"下载图片，点击"否"跳过
6. 循环等待下一个图片

[注意事项]
- 小红书有反爬机制，需要设置合适的等待时间
- 图片可能是懒加载，需要等待加载完成
- 长时间运行记得手动关闭浏览器

[可调整参数]
- DOWNLOAD_DIR: 下载目录路径
- KEYWORD: 默认搜索关键词
- TIMEOUT: 页面加载超时时间
"""

import ctypes
import os
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
import requests

try:
    from playwright._impl._api_types import Error as PlaywrightError
except ImportError:
    PlaywrightError = Exception


SEARCH_KEYWORD = "青岛栈桥"
DOWNLOAD_DIR = Path(r"C:\Users\Administrator\Desktop\公众号文章\img")
XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}"
PAGE_LOAD_TIMEOUT = 30000
IMAGE_WAIT_TIMEOUT = 10000
STORAGE_STATE_PATH = Path(__file__).parent / "xhs_state.json"
LOGIN_SELECTOR = "#global > div.main-container > div.side-bar > ul > div.channel-list-content > li.user.side-bar-component > div > a > span.channel"

TXT_DIR = Path(r"C:\Users\Administrator\Desktop\公众号文章\txt")
KEYWORD_FILE_PREFIX = "秘境"

# 已处理关键词记录文件路径（用于防止幻觉）- 放在公众号文章目录下
PROCESSED_KEYWORDS_PATH = Path(r"C:\Users\Administrator\Desktop\公众号文章\downloaded_keywords.txt")


def ensure_download_directory(directory: Path) -> None:
    """确保下载目录存在，不存在则创建。"""
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)


def find_keyword_files(txt_dir: Path, prefix: str) -> list[Path]:
    """遍历txt目录，查找以指定前缀开头的文件。"""
    if not txt_dir.exists():
        print(f"目录不存在: {txt_dir}")
        return []
    
    files = sorted(txt_dir.glob(f"{prefix}*.txt"))
    return files


def extract_keywords_from_file(file_path: Path) -> list[str]:
    """读取txt文件内容，提取所有【】方括号内的文本。"""
    import re
    
    try:
        content = file_path.read_text(encoding="utf-8")
        keywords = re.findall(r'【(.+?)】', content)
        return keywords
    except Exception as e:
        print(f"读取文件失败 {file_path}: {e}")
        return []


def sanitize_filename(keyword: str) -> str:
    """将关键词转换为合法的文件名。"""
    import re
    filename = re.sub(r'[\\/:*?"<>|]', '_', keyword)
    filename = filename.strip()
    if not filename:
        return "unknown"
    return filename


def is_keyword_processed(keyword: str, download_dir: Path, processed_keywords: set = None) -> bool:
    """检查关键词是否已处理。

    采用混合检测模式：
    1. 优先检查记录文件（最准确）
    2. 退而求其次检查文件名（向后兼容）

    Args:
        keyword: 关键词
        download_dir: 下载目录
        processed_keywords: 已处理关键词集合（从记录文件加载）

    Returns:
        bool: 是否已处理
    """
    # 优先检查记录文件（如果有加载）
    if processed_keywords is not None and keyword in processed_keywords:
        return True

    # 退而求其次：检查文件名（向后兼容旧文件）
    sanitized = sanitize_filename(keyword)
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        if (download_dir / f"{sanitized}{ext}").exists():
            return True

    return False


def load_processed_keywords(record_path: Path) -> set:
    """从记录文件加载已处理的关键词。"""
    if record_path.exists():
        try:
            content = record_path.read_text(encoding="utf-8")
            keywords = set(line.strip() for line in content.splitlines() if line.strip())
            print(f"已加载 {len(keywords)} 个已处理关键词记录")
            return keywords
        except Exception as e:
            print(f"加载记录文件失败：{e}")
    return set()


def save_processed_keyword(record_path: Path, keyword: str) -> None:
    """保存已处理的关键词到记录文件。"""
    try:
        with open(record_path, "a", encoding="utf-8") as f:
            f.write(keyword + "\n")
    except Exception as e:
        print(f"保存关键词记录失败：{e}")


def search_keyword(page, keyword: str) -> None:
    """在当前浏览器页面中执行关键词搜索。"""
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = XHS_SEARCH_URL.format(keyword=encoded_keyword)
    page.goto(search_url)
    page.wait_for_load_state("networkidle")


class KeyboardListener:
    """全局键盘监听器，用于在弹窗未激活时也能检测TAB键。"""
    
    def __init__(self):
        self.tab_pressed = False
        self.hook_id = None
        self.hook_proc = None
    
    def _keyboard_hook(self, code, wparam, lparam):
        """键盘钩子回调函数。"""
        import ctypes
        from ctypes import wintypes
        
        WM_KEYDOWN = 0x0100
        VK_TAB = 0x09
        
        try:
            if code >= 0 and wparam == WM_KEYDOWN:
                vk_code = int(wparam) & 0xFFFF
                if vk_code == VK_TAB:
                    self.tab_pressed = True
        except Exception:
            pass
        
        try:
            return ctypes.windll.user32.CallNextHookEx(self.hook_id, code, wparam, lparam)
        except Exception:
            return 0
    
    def start(self):
        """启动键盘监听。"""
        import ctypes
        from ctypes import wintypes
        
        WH_KEYBOARD_LL = 13
        self.tab_pressed = False
        
        prototype = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_int,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM
        )
        self.hook_proc = prototype(self._keyboard_hook)
        self.hook_id = ctypes.windll.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self.hook_proc,
            None,
            0
        )
    
    def stop(self):
        """停止键盘监听。"""
        if self.hook_id:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None
    
    def is_tab_pressed(self) -> bool:
        """检查是否按下了TAB键。"""
        return self.tab_pressed


def show_download_confirmation(image_info: str = "当前图片", current_index: int = 0, total_count: int = 0) -> bool:
    """显示置顶确认对话框，返回用户选择。支持TAB键触发。"""
    import ctypes
    import time
    import threading
    
    MB_YESNO = 0x04
    MB_ICONQUESTION = 0x20
    MB_TOPMOST = 0x00040000
    IDYES = 6
    
    progress_text = f"\n\n[{current_index}/{total_count}] 任务进度" if total_count > 0 else ""
    
    keyboard_listener = KeyboardListener()
    keyboard_listener.start()
    
    tab_pressed = {"value": False}
    message_result = {"value": 0}
    stop_thread = {"value": False}
    
    def wait_for_message():
        while not stop_thread["value"]:
            if keyboard_listener.is_tab_pressed():
                tab_pressed["value"] = True
                ctypes.windll.user32.PostMessageW(None, 0, 0, 0)
                break
            time.sleep(0.05)
    
    thread = threading.Thread(target=wait_for_message, daemon=True)
    thread.start()
    
    try:
        while not stop_thread["value"]:
            if tab_pressed["value"]:
                return True
            
            result = ctypes.windll.user32.MessageBoxW(
                None,
                f"检测到图片：{image_info}\n\n是否下载这张图片？{progress_text}\n\n提示：按TAB键可直接下载",
                "图片下载确认",
                MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
            )
            
            message_result["value"] = result
            break
        
        if tab_pressed["value"]:
            return True
        
        return message_result["value"] == IDYES
        
    except Exception:
        return False
        
    finally:
        stop_thread["value"] = True
        keyboard_listener.stop()


def generate_filename(directory: Path, extension: str = "jpg") -> str:
    """生成带时间戳的唯一文件名。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    index = 1
    filename = f"xhs_{timestamp}.{extension}"

    while (directory / filename).exists():
        filename = f"xhs_{timestamp}_{index}.{extension}"
        index += 1

    return filename


def download_image(image_url: str, save_path: Path) -> bool:
    """下载图片到指定路径。"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()

        with open(save_path, "wb") as f:
            f.write(response.content)

        return True

    except Exception as e:
        print(f"下载失败: {e}")
        return False


def get_main_image_selector() -> str:
    """获取小红书笔记详情页当前显示图片的 CSS 选择器（动态检测swiper-slide-active）。"""
    selectors = [
        "#noteContainer > div.media-container > div > div > div.note-slider > div > div.swiper-slide-active > div > div > img",
        "#noteContainer > div.media-container > div > div > div.note-slider > div > div.swiper-slide-active > div > div.live-photo-contain > div.live-video-wrapper > div > img",
    ]
    return ",".join(selectors)


def find_main_image(page) -> str | None:
    """在页面中查找当前显示的图片URL（swiper-slide-active状态）。"""
    selector = get_main_image_selector()

    try:
        image_element = page.wait_for_selector(selector, timeout=IMAGE_WAIT_TIMEOUT)

        if image_element:
            image_url = image_element.get_attribute("src")
            if not image_url:
                image_url = image_element.get_attribute("data-src")

            if image_url and image_url.startswith("http"):
                return image_url

            fwebp_url = image_element.get_attribute("fwebp")
            if fwebp_url:
                return fwebp_url

    except PlaywrightError:
        pass

    return None


def is_note_detail_page(page) -> bool:
    """判断当前是否在笔记详情页（通过检测页面元素）。"""
    detail_selectors = [
        "#noteContainer",
        ".note-detail-page",
        ".note-detail-container",
    ]
    
    for selector in detail_selectors:
        try:
            if page.locator(selector).first.is_visible(timeout=2000):
                return True
        except Exception:
            continue
    
    current_url = page.url
    detail_indicators = ["/explore/", "/discovery/item/", "/item/"]
    return any(indicator in current_url for indicator in detail_indicators)


def check_login_status(page) -> bool:
    """检查页面是否已登录。"""
    try:
        element = page.wait_for_selector(LOGIN_SELECTOR, timeout=5000)
        if element:
            text = element.inner_text()
            return text and len(text) > 0
    except PlaywrightError:
        pass
    return False


def wait_for_login(page, check_interval: float = 2.0) -> bool:
    """等待用户登录，持续检测登录状态直到成功或用户取消。
    
    Args:
        page: Playwright页面对象
        check_interval: 检测间隔（秒）
    
    Returns:
        bool: 是否成功登录
    """
    print("\n请在浏览器中扫码登录小红书...")
    print("登录成功后，系统会自动检测并继续...")
    print("提示：登录后可关闭二维码弹窗")
    print("-" * 40)
    
    while True:
        if check_login_status(page):
            return True
        time.sleep(check_interval)


def setup_browser_context(playwright_instance):
    """设置浏览器和上下文，包括登录状态管理。"""
    browser = playwright_instance.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--hide-scrollbars",
            "--mute-audio",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-sync",
            "--metrics-recording-only",
            "--disable-default-gesture",
            "--disable-popup-blocking",
            "--start-maximized",
        ]
    )

    context_options = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "geolocation": {"latitude": 31.2304, "longitude": 121.4737},
        "permissions": ["geolocation"],
        "extra_http_headers": {
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }

    if STORAGE_STATE_PATH.exists():
        print(f"发现保存的登录状态，正在加载...")
        try:
            context_options["storage_state"] = str(STORAGE_STATE_PATH)
        except Exception as e:
            print(f"加载登录状态失败: {e}")

    context = browser.new_context(**context_options)
    context.set_default_timeout(PAGE_LOAD_TIMEOUT)

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en']
        });
        window.chrome = { runtime: {} };
    """)

    return browser, context


def save_login_state(context):
    """保存登录状态到文件。"""
    try:
        context.storage_state(path=str(STORAGE_STATE_PATH))
        print(f"登录状态已保存到: {STORAGE_STATE_PATH}")
    except Exception as e:
        print(f"保存登录状态失败: {e}")


def wait_for_note_click(page, last_url: str) -> bool:
    """等待用户点击笔记，进入详情页。"""
    print("请在浏览器中搜索并点击某个笔记...")
    print("（点击后等待图片加载，系统会自动检测）")

    detail_selectors = [
        "#noteContainer",
        ".note-detail-page", 
        ".note-detail-container",
        ".note-images",
    ]
    
    max_wait_time = 300
    start_time = time.time()

    while time.time() - start_time < max_wait_time:
        for selector in detail_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=1000):
                    time.sleep(1)
                    print(f"[检测] 发现笔记详情页: {selector}")
                    return True
            except Exception:
                continue
        
        time.sleep(0.5)

    print("等待超时，未检测到笔记点击")
    return False


def main():
    """主流程：批量处理txt文件中的关键词，循环搜索并下载图片。"""
    ensure_download_directory(DOWNLOAD_DIR)

    # 加载已处理关键词记录（防止幻觉）
    processed_keywords = load_processed_keywords(PROCESSED_KEYWORDS_PATH)

    keyword_files = find_keyword_files(TXT_DIR, KEYWORD_FILE_PREFIX)
    
    if not keyword_files:
        print(f"未找到以'{KEYWORD_FILE_PREFIX}'开头的txt文件")
        print(f"请检查目录: {TXT_DIR}")
        return

    all_keywords_raw = []
    for file_path in keyword_files:
        keywords = extract_keywords_from_file(file_path)
        print(f"\n从文件 '{file_path.name}' 中提取到 {len(keywords)} 个关键词")
        all_keywords_raw.extend(keywords)

    # 去重：保持原有顺序，删除重复关键词
    seen = set()
    all_keywords = []
    for kw in all_keywords_raw:
        if kw not in seen:
            seen.add(kw)
            all_keywords.append(kw)

    if not all_keywords:
        print("未从任何文件中提取到关键词")
        return

    print(f"\n总计找到 {len(all_keywords)} 个关键词待处理（已自动去重）")
    if len(all_keywords_raw) != len(all_keywords):
        print(f"提示：原始提取 {len(all_keywords_raw)} 个，去重后剩余 {len(all_keywords)} 个")

    # 统计已记录的关键词
    already_recorded = sum(1 for kw in all_keywords if kw in processed_keywords)
    if already_recorded > 0:
        print(f"其中 {already_recorded} 个关键词已有记录，将自动跳过")

    print(f"=" * 50)
    print(f"小红书图片批量下载工具")
    print(f"关键词来源: {TXT_DIR}")
    print(f"下载目录: {DOWNLOAD_DIR}")
    print(f"记录文件：{PROCESSED_KEYWORDS_PATH}")
    print(f"=" * 50)

    processed_count = 0
    skipped_count = 0
    downloaded_count = 0

    with sync_playwright() as pw:
        try:
            browser, context = setup_browser_context(pw)
            page = context.new_page()

            print(f"\n正在打开小红书搜索页面...")
            
            start_index = 0
            for i, keyword in enumerate(all_keywords):
                if not is_keyword_processed(keyword, DOWNLOAD_DIR, processed_keywords):
                    start_index = i
                    break
            
            first_keyword = all_keywords[start_index]
            search_keyword(page, first_keyword)

            is_logged_in = check_login_status(page)
            if not is_logged_in:
                wait_for_login(page)
                save_login_state(context)
            else:
                print("\n✓ 已检测到登录状态")

            print("\n" + "=" * 50)
            print("批量处理模式启动！")
            print("=" * 50)
            print("\n处理流程：")
            print("1. 系统会自动搜索每个关键词")
            print("2. 请在浏览器中点击笔记详情")
            print("3. 弹窗询问是否下载，点击'是'下载")
            print("4. 搜索下一页继续处理下一个关键词")
            print("5. 手动关闭浏览器窗口可退出程序")
            print("-" * 50)

            for i, keyword in enumerate(all_keywords, 1):
                print(f"\n[{i}/{len(all_keywords)}] 正在处理关键词: {keyword}")

                if is_keyword_processed(keyword, DOWNLOAD_DIR, processed_keywords):
                    print(f"  → 图片已存在，跳过")
                    skipped_count += 1
                    continue

                print(f"  → 正在搜索...")
                search_keyword(page, keyword)

                if not wait_for_note_click(page, page.url):
                    print(f"  → 等待用户点击超时，继续下一个关键词")
                    continue

                print(f"  → 检测到笔记详情页")

                image_url = find_main_image(page)

                if not image_url:
                    print(f"  → 未检测到主图，跳过")
                    continue

                print(f"  → 检测到图片: {image_url[:50]}...")

                if show_download_confirmation(keyword, i, len(all_keywords)):
                    image_url = find_main_image(page)
                    if not image_url:
                        print(f"  → 确认时未检测到图片，跳过")
                        continue
                    
                    sanitized_name = sanitize_filename(keyword)
                    save_path = DOWNLOAD_DIR / f"{sanitized_name}.jpg"

                    if download_image(image_url, save_path):
                        print(f"  ✓ 图片已保存: {save_path}")
                        downloaded_count += 1
                        # 保存到记录文件
                        save_processed_keyword(PROCESSED_KEYWORDS_PATH, keyword)
                        # 添加到内存中的集合
                        processed_keywords.add(keyword)
                    else:
                        print(f"  ✗ 图片下载失败")
                else:
                    print(f"  → 用户取消下载")
                    processed_count += 1
                processed_count += 1

        except KeyboardInterrupt:
            print("\n\n程序被用户中断")

        except Exception as e:
            print(f"\n发生错误: {e}")

    print("\n" + "=" * 50)
    print("程序执行完成")
    print(f"总计处理: {processed_count} 个")
    print(f"跳过(已存在): {skipped_count} 个")
    print(f"成功下载: {downloaded_count} 个")
    print("=" * 50)


if __name__ == "__main__":
    main()
