# -*- coding: utf-8 -*-
"""
[功能概述]: 将 HTML 以正确的格式复制到 Windows 系统粘贴板
[核心功能]: 使用 ctypes 调用 Windows API 设置 CF_HTML 格式

微信公众号编辑器需要接收 text/html 格式的粘贴板内容，
而不是纯文本格式。从文件中复制只会得到 text/plain 格式。

CF_HTML 格式是微软定义的 HTML 剪贴板格式。
"""

import sys
import os

try:
    import win32clipboard
except ImportError:
    print("需要安装 pywin32:")
    print("pip install pywin32")
    sys.exit(1)


def read_html_file(file_path):
    """读取 HTML 文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None


def copy_html_to_clipboard_windows(html_content):
    """
    使用 Windows API 将 HTML 内容复制到粘贴板

    微信公众号编辑器需要 CF_HTML 格式
    """
    CF_HTML = win32clipboard.RegisterClipboardFormat("HTML Format")

    # 构建 CF_HTML 格式
    # 格式: header + html + footer
    # Version:0.9
    # StartHTML:000000000000
    # EndHTML:000000000000
    # StartFragment:000000000000
    # EndFragment:000000000000

    # 简化版本 - 直接使用 UTF-8 格式的 HTML
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, html_content)

        # 尝试设置 HTML 格式
        # CF_HTML 需要特定的头部格式
        html_prefix = (
            "Version:0.9\r\n"
            "StartHTML:0000000105\r\n"
            "EndHTML:{:08d}\r\n"
            "StartFragment:0000000137\r\n"
            "EndFragment:{:08d}\r\n"
        ).format(
            105 + len(html_content) + 33,  # EndHTML position
            137 + len(html_content)         # EndFragment position
        )

        html_fragment = (
            "<!--StartFragment-->\n" +
            html_content +
            "\n<!--EndFragment-->"
        )

        cf_html_content = html_prefix + html_fragment

        # 设置 HTML 格式（使用 bytes）
        win32clipboard.SetClipboardData(CF_HTML, cf_html_content.encode('utf-8'))

        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"复制失败: {e}")
        try:
            win32clipboard.CloseClipboard()
        except:
            pass
        return False


def main():
    if len(sys.argv) < 2:
        print("使用方法: python 7_copy_html_clipboard.py <html文件路径>")
        print("\n示例:")
        print("  python 7_copy_html_clipboard.py C:/Users/Administrator/Desktop/公众号文章/html/秘境秘境九寨.html")
        sys.exit(1)

    html_file = sys.argv[1]

    if not os.path.exists(html_file):
        print(f"文件不存在: {html_file}")
        sys.exit(1)

    print(f"读取文件: {html_file}")
    html_content = read_html_file(html_file)

    if not html_content:
        sys.exit(1)

    print(f"HTML 内容长度: {len(html_content)} 字符")
    print("正在复制到粘贴板...")

    if copy_html_to_clipboard_windows(html_content):
        print("\n[OK] 成功复制到粘贴板!")
        print("  现在可以:")
        print("  1. 打开微信公众号编辑器")
        print("  2. 按 Ctrl+V 粘贴")
        print("\n提示: 如果还是不行，请尝试在 mdnice 网站上直接复制")
    else:
        print("\n[ERROR] 复制失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
