import os
import re
import requests
import numpy as np
# from cv2 import cv2 # 如果你是老版本opencv
import cv2
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# === 新增：导入 pyzbar ===
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


# === 修改重点：使用 pyzbar 替代 OpenCV 识别 ===
def decode_qr_from_bytes(image_bytes):
    """从图片字节流中识别二维码链接 (使用 pyzbar)"""
    try:
        # 直接使用 PIL 读取字节流，pyzbar 可以直接处理 PIL 图片
        # 这样比转成 numpy 数组再转 cv2 更快且兼容性更好
        img = Image.open(BytesIO(image_bytes))

        # 预处理：如果图片不是 RGB，转换一下（虽然 pyzbar 很强，但转成 RGB 或 L 灰度更稳）
        if img.mode not in ('L', 'RGB'):
            img = img.convert('RGB')

        # 解码
        decoded_objects = decode(img)

        if decoded_objects:
            # 取第一个识别到的二维码数据
            # data 是 bytes 类型，需要解码成 string
            return decoded_objects[0].data.decode('utf-8')

    except Exception as e:
        print(f"⚠️ 二维码解码过程中出错: {e}")

    return None


def main():
    if not os.path.exists(BASE_SAVE_PATH):
        os.makedirs(BASE_SAVE_PATH)

    with sync_playwright() as p:
        print("正在启动浏览器引擎...")
        browser = p.chromium.launch(headless=True)  # 可以改为 False 方便调试
        viewport_config = {'width': 1920, 'height': 1080}

        while True:
            print("\n" + "=" * 50)
            user_input = input("请输入 网址 或 图片链接 (直接回车退出): ").strip()

            if not user_input:
                print("程序退出。")
                break

            poster_image_bytes = None
            final_target_url = user_input
            is_poster_mode = False

            clean_url = get_clean_image_url(user_input)
            path_check = urlparse(clean_url).path.lower()

            # 判断是否为图片
            if path_check.endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp')) or "img.xiumi.us" in user_input:
                print(f"检测到图片链接，正在处理: {clean_url}")
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    # 注意：有时候直接下载 clean_url (去掉后缀) 可能导致 403 或者拿到原图过大
                    # 但针对 xiumi，去掉 x-oss-process 是对的，能拿到原图。
                    resp = requests.get(clean_url, headers=headers)
                    resp.raise_for_status()
                    poster_image_bytes = resp.content

                    print("正在解码二维码(pyzbar)...")
                    decoded_url = decode_qr_from_bytes(poster_image_bytes)

                    if decoded_url:
                        print(f"✅ 二维码识别成功，目标网址: {decoded_url}")
                        final_target_url = decoded_url
                        is_poster_mode = True
                    else:
                        print("❌ 无法识别二维码。可能图片太模糊或包含复杂背景。")
                        continue

                except Exception as e:
                    print(f"❌ 下载或处理图片失败: {e}")
                    continue

            # Playwright 截图部分
            context = browser.new_context(
                viewport=viewport_config,
                device_scale_factor=1
            )
            page = context.new_page()

            try:
                print(f"正在访问: {final_target_url}")
                page.goto(final_target_url)

                page_title = page.title()
                print(f"网页标题: {page_title}")
                folder_name = clean_filename(page_title)
                save_dir = os.path.join(BASE_SAVE_PATH, folder_name)

                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                print("正在寻找目标内容...")
                try:
                    page.wait_for_selector(TARGET_SELECTOR, timeout=15000)
                    page.wait_for_timeout(2000)
                except:
                    print("⚠️ 超时未找到特定元素，尝试继续...")

                screenshot_path = os.path.join(save_dir, "完整详情页.png")

                # 尝试截图，如果元素不存在则截全屏作为保底（可选）
                try:
                    page.locator(TARGET_SELECTOR).screenshot(path=screenshot_path)
                    print(f"✅ 详情页截图已保存: {screenshot_path}")
                except Exception as e:
                    print(f"❌ 截图失败 (未找到元素): {e}")

                if is_poster_mode and poster_image_bytes:
                    poster_save_path = os.path.join(save_dir, "海报.png")
                    try:
                        image_obj = Image.open(BytesIO(poster_image_bytes))
                        image_obj.save(poster_save_path, "PNG")
                        print(f"✅ 海报原图已保存(转PNG): {poster_save_path}")
                    except Exception as e:
                        print(f"⚠️ 保存海报图片时出错: {e}")

            except Exception as e:
                print(f"❌ 页面处理过程中发生错误: {e}")
            finally:
                context.close()

        browser.close()


if __name__ == "__main__":
    main()
