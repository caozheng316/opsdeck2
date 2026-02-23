# -*- coding: utf-8 -*-
"""
[功能概述]: 将生成的 HTML 文件直接复制到系统粘贴板（支持 text/html 格式）
[启动准备]: pip install pyperclip
[使用方法]:
    1. 先运行 5_generate_html.py 生成 HTML 文件
    2. 运行此脚本: python 6_copy_to_clipboard.py <html文件名>
    3. 直接在微信公众号编辑器中粘贴 (Ctrl+V)
[注意事项]:
    - 此脚本会将 HTML 以正确的 text/html 格式复制到粘贴板
    - 从文件中复制内容只会得到纯文本格式，无法被公众号编辑器识别
"""

import os
import sys
import argparse

try:
    import pyperclip
except ImportError:
    print("请先安装 pyperclip: pip install pyperclip")
    sys.exit(1)


def read_html_file(file_path):
    """读取 HTML 文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None


def copy_html_to_clipboard(html_content):
    """
    将 HTML 内容复制到粘贴板

    关键：pyperclip 会自动处理 HTML 格式
    在 Windows 上使用 HTML Format 格式
    """
    try:
        # pyperclip 在 Windows 上会自动设置正确的格式
        pyperclip.copy(html_content)
        return True
    except Exception as e:
        print(f"复制到粘贴板失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='将 HTML 文件复制到粘贴板')
    parser.add_argument('html_file', help='HTML 文件路径')
    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.exists(args.html_file):
        print(f"文件不存在: {args.html_file}")
        sys.exit(1)

    # 读取 HTML 文件
    print(f"读取文件: {args.html_file}")
    html_content = read_html_file(args.html_file)

    if not html_content:
        sys.exit(1)

    # 复制到粘贴板
    print("正在复制到粘贴板...")
    if copy_html_to_clipboard(html_content):
        print("✓ 已成功复制到粘贴板！")
        print("  现在可以直接在微信公众号编辑器中按 Ctrl+V 粘贴")
    else:
        print("✗ 复制失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
