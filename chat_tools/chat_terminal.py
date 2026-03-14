#!/usr/bin/env python3
"""
终端聊天程序 - 支持文本和图片粘贴
使用 Chat API 进行对话
"""

import sys
import json
import base64
import http.client
import subprocess
from typing import Optional

# 导入 colorama 用于终端颜色
from colorama import init, Fore, Style

# 初始化 colorama（Windows 支持）
init(autoreset=True)

# 颜色定义
USER_COLOR = Fore.LIGHTYELLOW_EX  # 用户消息 - 橙黄色
AI_COLOR = Fore.CYAN    # AI 回复 - 浅蓝色（明亮）
PROMPT_COLOR = Fore.LIGHTYELLOW_EX  # 输入提示符 - 橙黄色
ROLE_COLOR = Fore.LIGHTYELLOW_EX  # 角色标识（你）- 橙黄色
AI_ROLE_COLOR = Fore.LIGHTCYAN_EX  # 角色标识（AI）- 浅蓝色

# 模型选项
MODELS = {
    "1": "gemini-3.1-pro-preview-thinking",
    "2": "gemini-3.1-pro-preview-all",
    "3": "claude-opus-4-6-thinkin",
    "4": "claude-3-7-sonnet-thinking"
}

API_KEY = "sk-y5oo8iCyiqqVtY6QFqdzp5LWXFv358xYbWZQUdXKY5dRcLoP"
API_HOST = "one.api4gpt.com"

class TerminalChat:
    def __init__(self, model: str):
        self.model = model
        self.messages = []
        self.image_data = None  # 存储粘贴的图片
        self.multiline_mode = False  # 多行输入模式

    def get_clipboard_text(self) -> str:
        """从剪贴板获取文本"""
        # 方法 1: 使用 win32clipboard (最可靠)
        try:
            import win32clipboard

            def get_clipboard_formats():
                """获取剪贴板中所有可用的文本格式"""
                formats = []
                win32clipboard.OpenClipboard()
                try:
                    fmt = win32clipboard.EnumClipboardFormats(0)
                    while fmt:
                        formats.append(fmt)
                        fmt = win32clipboard.EnumClipboardFormats(fmt)
                finally:
                    win32clipboard.CloseClipboard()
                return formats

            win32clipboard.OpenClipboard()
            try:
                # 尝试多种文本格式
                # CF_UNICODETEXT (13) - Unicode 文本
                if win32clipboard.IsClipboardFormatAvailable(13):
                    text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    if text and text.strip():
                        return text.strip()

                # CF_TEXT (1) - ANSI 文本
                if win32clipboard.IsClipboardFormatAvailable(1):
                    text = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
                    if text and text.strip():
                        return text.decode('utf-8', errors='ignore').strip()

                # CF_OEMTEXT (7) - OEM 文本
                if win32clipboard.IsClipboardFormatAvailable(7):
                    text = win32clipboard.GetClipboardData(win32clipboard.CF_OEMTEXT)
                    if text and text.strip():
                        return text.decode('utf-8', errors='ignore').strip()

            finally:
                win32clipboard.CloseClipboard()

        except Exception as e:
            print(f"[调试] win32clipboard 错误：{e}")
            pass

        # 方法 2: 使用 PowerShell
        try:
            result = subprocess.run(
                ['powershell', '-command', 'Get-Clipboard -Raw'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0 and result.stdout and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            print(f"[调试] PowerShell 错误：{e}")
            pass

        # 方法 3: 使用 tkinter (跨平台)
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # 隐藏窗口
            text = root.clipboard_get()
            root.destroy()
            if text and text.strip():
                return text.strip()
        except Exception as e:
            pass

        return ""

    def get_image_input(self) -> Optional[dict]:
        """尝试从剪贴板获取图片"""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img:
                import io
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                }
        except Exception as e:
            print(f"[调试] 获取图片失败：{e}")
        return None

    def send_message(self, content) -> str:
        """发送消息到 API 并获取回复"""
        # 增加超时时间，防止长文本请求被中断
        conn = http.client.HTTPSConnection(API_HOST, timeout=120)

        # 构建消息内容
        if isinstance(content, list):
            messages_content = content
        else:
            messages_content = [{"type": "text", "text": content}]

        # 添加当前消息到历史记录
        self.messages.append({
            "role": "user",
            "content": messages_content
        })

        # 配置：最大上下文，不受限制
        # 发送完整的 messages 历史记录，保持上下文连贯
        # 不设置 stop 序列，让模型自然完成回复
        payload = json.dumps({
            "model": self.model,
            "messages": self.messages,
            "stream": False,
            "max_tokens": 128000,  # 设置为模型支持的最大值
        }, ensure_ascii=False)

        # 将 payload 编码为 UTF-8 字节
        payload_bytes = payload.encode('utf-8')

        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json; charset=utf-8'
        }

        try:
            conn.request("POST", "/v1/chat/completions", payload_bytes, headers)
            res = conn.getresponse()
            data = res.read()

            if res.status != 200:
                return f"错误：API 返回状态码 {res.status}\n{data.decode('utf-8')}"

            response = json.loads(data.decode("utf-8"))

            # 解析响应
            if "choices" in response and len(response["choices"]) > 0:
                assistant_message = response["choices"][0]["message"]["content"]

                # 添加助手回复到历史记录
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message
                })

                return assistant_message
            else:
                return f"意外响应：{response}"

        except http.client.RemoteDisconnected:
            return f"请求错误：远程服务器关闭了连接（可能是超时或内容过长），请重试或换用其他模型"
        except http.client.IncompleteRead:
            return f"请求错误：响应不完整（可能是超时），请重试"
        except Exception as e:
            return f"请求错误：{str(e)}"
        finally:
            conn.close()

    def clear_image(self):
        """清除已存储的图片"""
        self.image_data = None
        print("[图片已清除]")

    def show_history(self):
        """显示聊天历史"""
        print("\n" + "="*50)
        print("聊天历史 (完整内容):")
        print("="*50)
        for i, msg in enumerate(self.messages, 1):
            role = "你" if msg["role"] == "user" else "AI"
            role_color = USER_COLOR if msg["role"] == "user" else AI_ROLE_COLOR
            msg_color = USER_COLOR if msg["role"] == "user" else AI_COLOR
            content = msg["content"]
            if isinstance(content, list):
                text_content = ""
                for item in content:
                    if item.get("type") == "text":
                        text_content += item.get("text", "")
                    elif item.get("type") == "image_url":
                        text_content += "\n[图片]\n"
                content = text_content
            print(f"\n{role_color}--- 第 {i} 条 ({role}) ---{Style.RESET_ALL}")
            print(f"{msg_color}{content}{Style.RESET_ALL}")
        print("\n" + "="*50)

    def read_multiline_input(self) -> str:
        """读取多行输入，支持粘贴"""
        print("请输入内容（多行模式）：")
        print("  - 粘贴内容后，输入单独一行的 '/' 表示结束")
        print("  - 或直接输入 '/' 后按回车结束")
        print("--- 开始输入 ---")

        lines = []
        while True:
            try:
                line = input()
                if line.strip() == '/':
                    break
                lines.append(line)
            except EOFError:
                break

        return '\n'.join(lines)

    def run(self):
        """主运行循环"""
        print("\n" + "="*60)
        print(f"终端聊天程序 - 使用模型：{self.model}")
        print("="*60)
        print("命令:")
        print("  /quit, /exit  - 退出程序")
        print("  /clear        - 清除聊天历史")
        print("  /history      - 显示聊天历史")
        print("  /image        - 从剪贴板加载图片")
        print("  /send         - 发送当前加载的图片")
        print("  /paste        - 从剪贴板粘贴长文本（支持多行代码/文章）")
        print("  /multi        - 进入多行输入模式（手动输入多行内容）")
        print("  直接输入消息进行对话")
        print("="*60 + "\n")

        while True:
            try:
                # 获取用户输入
                print(f"{PROMPT_COLOR}👤 你：{Style.RESET_ALL}", end="", flush=True)
                user_input = sys.stdin.readline().strip()

                if not user_input:
                    continue

                # 处理命令
                if user_input.lower() in ['/quit', '/exit']:
                    print("再见!")
                    break

                elif user_input.lower() == '/clear':
                    self.messages = []
                    self.image_data = None
                    print(f"{USER_COLOR}聊天历史已清除{Style.RESET_ALL}")
                    continue

                elif user_input.lower() == '/history':
                    self.show_history()
                    continue

                elif user_input.lower() == '/send':
                    if self.image_data:
                        content = [self.image_data, {"type": "text", "text": "请分析这张图片"}]
                        print(f"\n{AI_ROLE_COLOR}🤖 AI: {Style.RESET_ALL}", end="", flush=True)
                        response = self.send_message(content)
                        print(f"{AI_COLOR}{response}{Style.RESET_ALL}")
                        self.image_data = None
                    else:
                        print("[!] 没有已加载的图片，先用 /image 加载图片")
                    continue

                elif user_input.lower() == '/image':
                    # 尝试从剪贴板获取图片
                    try:
                        from PIL import ImageGrab
                        img = ImageGrab.grabclipboard()
                        if img:
                            import io
                            buffer = io.BytesIO()
                            img.save(buffer, format='PNG')
                            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                            self.image_data = {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                            print(f"{USER_COLOR}[✓] 图片已从剪贴板加载，使用 /send 发送，或输入文字一起发送{Style.RESET_ALL}")
                        else:
                            print("[!] 剪贴板中没有图片")
                    except ImportError:
                        print("[!] 需要安装 Pillow: pip install Pillow")
                    except Exception as e:
                        print(f"[!] 获取图片失败：{e}")
                    continue

                elif user_input.lower() == '/paste':
                    # 从剪贴板粘贴长文本
                    print("[调试] 正在读取剪贴板...")
                    clipboard_text = self.get_clipboard_text()

                    if clipboard_text:
                        print(f"{USER_COLOR}[✓] 已从剪贴板加载 {len(clipboard_text)} 个字符{Style.RESET_ALL}")
                        print(f"{USER_COLOR}[预览] 前 100 字符：{clipboard_text[:100]}...{Style.RESET_ALL}")
                        print("请输入你的问题（可选），或直接回车发送剪贴板内容：")
                        print(f"{PROMPT_COLOR}👤 你：{Style.RESET_ALL}", end="", flush=True)
                        question = sys.stdin.readline().strip()

                        if self.image_data:
                            content = [
                                self.image_data,
                                {"type": "text", "text": f"剪贴板内容:\n{clipboard_text}"}
                            ]
                            self.image_data = None
                            if question:
                                content.append({"type": "text", "text": f"\n问题：{question}"})
                        else:
                            content = clipboard_text
                            if question:
                                content = f"{clipboard_text}\n\n问题：{question}"

                        print(f"\n{AI_ROLE_COLOR}🤖 AI: {Style.RESET_ALL}", end="", flush=True)
                        response = self.send_message(content)
                        print(f"{AI_COLOR}{response}{Style.RESET_ALL}")
                        print()
                    else:
                        print("[!] 剪贴板为空或无法读取")
                        print("[提示] 请确认已复制文本内容（不是文件或其他格式）")
                    continue

                elif user_input.lower() == '/multi':
                    # 多行输入模式
                    text = self.read_multiline_input()
                    if text.strip():
                        user_input = text
                    else:
                        continue

                # 发送普通消息
                if self.image_data:
                    # 有图片时，组合图片和文字
                    content = [
                        self.image_data,
                        {"type": "text", "text": user_input}
                    ]
                    self.image_data = None  # 发送后清除
                else:
                    content = user_input

                print(f"\n{AI_ROLE_COLOR}🤖 AI: {Style.RESET_ALL}", end="", flush=True)
                response = self.send_message(content)
                print(f"{AI_COLOR}{response}{Style.RESET_ALL}")
                print()

            except KeyboardInterrupt:
                print("\n\n中断退出，再见!")
                break
            except EOFError:
                print("\n再见!")
                break


def select_model() -> str:
    """让用户选择模型"""
    print("\n可用模型:")
    print("  1: gemini-3.1-pro-preview-thinking")
    print("  2: gemini-3.1-pro-preview-all")
    print("  3: claude-opus-4-6-thinkin")
    print("  4: claude-3-7-sonnet-thinking")

    while True:
        choice = input("\n请选择模型 (1-4): ").strip()
        if choice in MODELS:
            return MODELS[choice]
        print("无效选择，请输入 1-4")


def main():
    # 选择模型
    model = select_model()

    # 创建聊天实例
    chat = TerminalChat(model)

    # 运行聊天
    chat.run()


if __name__ == "__main__":
    main()
