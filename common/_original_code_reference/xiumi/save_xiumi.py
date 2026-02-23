import os
import re
import requests
import time
from io import BytesIO
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# === 图像处理库 ===
from PIL import Image, ImageGrab  # 新增 ImageGrab 用于读取剪贴板
from pyzbar.pyzbar import decode

# === 配置区域 ===
BASE_SAVE_PATH = r"C:\Users\Administrator\Desktop\工具文件夹\下载"
TARGET_SELECTOR = "body > div.tn-reader-paper.container.ng-scope > div.tn-board-body.ready > div.row.tn-article-body.tn-opera-house.display-system-page-margins > article.tn-cube-box.paper.dock-loader.atom-data-binding.ng-scope.tn-from-house-reader_paper-cp.tn-comp-anim-pin.tn-comp-inst.tn-cube-box-inst.tn-comp.tn-in-cell-state-active"


def clean_filename(text):
    """清理文件名中的非法字符"""
    clean = re.sub(r'[\\/:*?"<>|]', '', text).strip()
    return clean if clean else "无标题页面"


def get_clean_image_url(url):
    """去除图片链接中的参数"""
    return url.split('?')[0]


def decode_qr_from_bytes(image_bytes):
    """从图片字节流中识别二维码链接"""
    try:
        img = Image.open(BytesIO(image_bytes))
        if img.mode not in ('L', 'RGB'):
            img = img.convert('RGB')
        decoded_objects = decode(img)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        print(f"⚠️ 二维码解码出错: {e}")
    return None


def get_image_data_from_input(user_input):
    """
    统一处理输入源：
    1. 如果输入 'p'，读取剪贴板
    2. 如果是本地文件路径，读取文件
    3. 如果是 URL，下载图片
    返回: (image_bytes, is_image_source)
    """
    image_bytes = None

    # === 模式1: 剪贴板读取 ===
    if user_input.lower() == 'p':
        print("正在读取剪贴板...")
        content = ImageGrab.grabclipboard()

        if isinstance(content, Image.Image):
            # 剪贴板里直接是图片像素（如截图、网页右键复制图片）
            bio = BytesIO()
            content.save(bio, format="PNG")
            image_bytes = bio.getvalue()
            print("✅ 已获取剪贴板中的图片数据")

        elif isinstance(content, list):
            # 剪贴板里是文件列表（在资源管理器复制了文件）
            if len(content) > 0 and os.path.isfile(content[0]):
                print(f"✅ 检测到剪贴板中的文件: {content[0]}")
                try:
                    with open(content[0], "rb") as f:
                        image_bytes = f.read()
                except Exception as e:
                    print(f"❌ 读取文件失败: {e}")
        else:
            print("❌ 剪贴板中没有图片或支持的文件。")

        return image_bytes, True

    # === 模式2: 本地文件路径 (拖拽进来的路径通常带引号，需去除) ===
    clean_input = user_input.strip('"').strip("'")
    if os.path.exists(clean_input) and os.path.isfile(clean_input):
        print(f"正在读取本地文件: {clean_input}")
        try:
            with open(clean_input, "rb") as f:
                image_bytes = f.read()
            return image_bytes, True
        except Exception as e:
            print(f"❌ 读取本地文件失败: {e}")
            return None, False

    # === 模式3: 网络 URL ===
    clean_url = get_clean_image_url(user_input)
    path_check = urlparse(clean_url).path.lower()

    # 简单的图片URL判断
    if path_check.endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')) or "img.xiumi.us" in user_input:
        print(f"检测到网络图片链接: {clean_url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(clean_url, headers=headers)
            resp.raise_for_status()
            return resp.content, True
        except Exception as e:
            print(f"❌ 下载图片失败: {e}")
            return None, False

    # 不是图片，直接返回原文本作为网页链接
    return None, False


def main():
    if not os.path.exists(BASE_SAVE_PATH):
        os.makedirs(BASE_SAVE_PATH)

    with sync_playwright() as p:
        print("正在启动浏览器引擎...")
        browser = p.chromium.launch(headless=True)
        viewport_config = {'width': 1920, 'height': 1080}

        print("\n" + "=" * 50)
        print("【使用说明】支持三种输入方式：")
        print("1. 输入 p 并回车 -> 自动识别剪贴板里的图片（推荐！直接复制图片后按p）")
        print("2. 拖拽本地图片文件进黑框 -> 自动读取路径")
        print("3. 输入网址/图片链接")
        print("=" * 50)

        while True:
            print("\n请输入 (p/路径/网址): ", end="")
            user_input = input().strip()

            if not user_input:
                continue

            poster_image_bytes = None
            final_target_url = user_input
            is_poster_mode = False

            # === 核心改动：统一获取图片数据 ===
            img_bytes, is_img = get_image_data_from_input(user_input)

            if is_img:
                if img_bytes:
                    poster_image_bytes = img_bytes
                    print("正在识别二维码...")
                    decoded_url = decode_qr_from_bytes(poster_image_bytes)

                    if decoded_url:
                        print(f"✅ 二维码识别成功，目标: {decoded_url}")
                        final_target_url = decoded_url
                        is_poster_mode = True
                    else:
                        print("❌ 图片中未发现二维码，请检查图片清晰度。")
                        continue
                else:
                    # 识别为图片模式但没拿到数据（如下载失败）
                    continue

            # 如果不是图片模式，且不是有效URL，简单校验一下
            if not is_poster_mode and not final_target_url.startswith(('http://', 'https://')):
                print("⚠️ 输入似乎不是有效的网址或图片。")
                continue

            # === Playwright 截图流程 (保持不变) ===
            context = browser.new_context(viewport=viewport_config, device_scale_factor=1)
            page = context.new_page()

            try:
                print(f"正在访问: {final_target_url}")
                page.goto(final_target_url)

                # 等待加载和可能的跳转
                try:
                    # 等待初始页面加载
                    page.wait_for_load_state("networkidle", timeout=5000)
                    
                    # 等待可能的重定向/跳转完成
                    # 监控URL变化，最多等待10秒
                    start_time = time.time()
                    initial_url = page.url
                    print(f"初始URL: {initial_url}")
                    
                    while time.time() - start_time < 10:
                        current_url = page.url
                        if current_url != initial_url:
                            print(f"检测到跳转，当前URL: {current_url}")
                            # URL发生变化，等待新页面加载完成
                            try:
                                page.wait_for_load_state("networkidle", timeout=5000)
                            except:
                                pass
                            break
                        time.sleep(0.5)  # 每500ms检查一次
                    
                    # 再额外等待2秒确保页面完全加载
                    page.wait_for_timeout(2000)
                    
                except Exception as e:
                    print(f"⚠️ 页面加载等待出错: {e}")
                    # 即使出错也继续执行
                    pass

                page_title = page.title()
                print(f"网页标题: {page_title}")
                folder_name = clean_filename(page_title)
                save_dir = os.path.join(BASE_SAVE_PATH, folder_name)

                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                print("正在寻找目标内容...")
                target_found = False
                final_selector = TARGET_SELECTOR
                
                # 尝试使用nth选择器
                try:
                    # 检查是否有足够的section元素
                    section_count = page.locator("section").count()
                    print(f"页面中共有 {section_count} 个section元素")
                    
                    if section_count > 4:  # 确保第5个section存在
                        page.wait_for_selector(TARGET_SELECTOR, timeout=15000)
                        print("✅ 找到第5个section元素")
                        target_found = True
                        final_selector = TARGET_SELECTOR
                        page.wait_for_timeout(2000)
                    else:
                        print(f"⚠️ 页面中只有 {section_count} 个section元素，少于所需的5个")
                        
                except Exception as e:
                    print(f"⚠️ 查找section元素时出错: {e}")
                    
                # 如果nth选择器失败，尝试其他备选方案
                if not target_found:
                    print("⚠️ nth选择器未找到目标，尝试其他选择器...")
                    alternative_selectors = [
                        "article",  # 通用文章选择器
                        ".article-content",
                        ".post-content",
                        "[class*='content']",
                        "[class*='article']",
                        "body > div.tn-reader-paper.container.ng-scope > div.tn-board-body.ready > div.row.tn-article-body.tn-opera-house.display-system-page-margins > article.tn-cube-box.paper.dock-loader.atom-data-binding.ng-scope.tn-from-house-reader_paper-cp.tn-comp-anim-pin.tn-comp-inst.tn-cube-box-inst.tn-comp.tn-in-cell-state-active"
                    ]
                    
                    for selector in alternative_selectors:
                        try:
                            if page.locator(selector).count() > 0:
                                final_selector = selector
                                print(f"✅ 找到替代元素: {selector}")
                                target_found = True
                                page.wait_for_timeout(2000)
                                break
                        except:
                            continue
                    
                    if not target_found:
                        print("⚠️ 未找到合适的内容元素，将截取整个页面")

                screenshot_path = os.path.join(save_dir, "完整详情页.png")

                # 尝试截图目标元素，如果失败则截图整个页面
                try:
                    page.locator(TARGET_SELECTOR).screenshot(path=screenshot_path)
                    print(f"✅ 目标内容截图已保存: {screenshot_path}")
                except Exception as e:
                    print(f"⚠️ 目标元素截图失败: {e}，正在截取整个页面...")
                    # 截取整个页面，使用最高分辨率
                    full_screenshot_path = os.path.join(save_dir, "完整详情页.png")
                    try:
                        page.screenshot(path=full_screenshot_path, full_page=True)
                        print(f"✅ 完整页面截图已保存: {full_screenshot_path}")
                    except Exception as e2:
                        print(f"❌ 完整页面截图也失败: {e2}")
                        # 最后的备选方案：视口截图
                        try:
                            viewport_screenshot_path = os.path.join(save_dir, "视口截图.png")
                            page.screenshot(path=viewport_screenshot_path)
                            print(f"✅ 视口截图已保存: {viewport_screenshot_path}")
                        except Exception as e3:
                            print(f"❌ 所有截图方式都失败: {e3}")

                # 如果是通过识别二维码进来的，保存原始海报
                if is_poster_mode and poster_image_bytes:
                    poster_save_path = os.path.join(save_dir, "原始海报.png")
                    try:
                        image_obj = Image.open(BytesIO(poster_image_bytes))
                        image_obj.save(poster_save_path, "PNG")
                        print(f"✅ 海报原图已保存: {poster_save_path}")
                    except Exception as e:
                        print(f"⚠️ 保存海报图片时出错: {e}")

            except Exception as e:
                print(f"❌ 页面处理错误: {e}")
            finally:
                context.close()

        browser.close()


if __name__ == "__main__":
    main()
