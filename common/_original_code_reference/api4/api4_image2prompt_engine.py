"""
=============================================================
api4_image2prompt_engine.py 使用说明
=============================================================

功能概述:
--------
该模块提供了一个与AI聊天API交互的功能，支持发送图片和文本提示词，
并返回AI生成的回复内容。主要用于图像处理场景，能够根据图片生成
相应的中文自然语言提示词。

输入要求:
--------
- image_path (file，外部接入): 本地图片文件路径
- prompt (str, 可选，外部接入): 提示词内容，默认使用内置的DEFAULT_PROMPT_TEMPLATE
- model (str, 已配置): 使用的AI模型名称，默认为 "gemini-3-pro-preview"
- api_key (str，已配置): API密钥，用于认证
- base_url (str，已配置): API基础URL地址
输出内容:
--------
- response_content (str): AI生成的回复内容，通常是根据图片和提示词生成的中文描述

外部模块调用:
------------
- requests: 用于发送HTTP请求
- base64: 用于图片编码
- json: 用于处理JSON数据
- typing: 用于类型注解
- xbot.app.logging.trace 或 xbot.print (可选): 自定义日志打印函数

使用流程:
--------
外部调用方式:
1. 导入模块: from ai_image_prompt_engine import chat_with_ai_api
2. 准备必要参数: API密钥、基础URL、图片路径、自定义提示词
3. 调用函数: 
   result = chat_with_ai_api(
       api_key="your_api_key",
       base_url="https://api.example.com/v1",
       image_path="/path/to/image.jpg",
       prompt="你的自定义提示词"
   )
4. 处理返回结果

测试模式（直接运行文件）:
- 自动使用默认提示词模板
- 只发起一次API请求
- 用于验证模块功能是否正常

注意事项:
--------
- 确保已安装 requests 库
- 图片文件必须存在且可访问
- API密钥和URL需要有效
- 网络连接正常
- 可以使用默认提示词模板或自定义提示词
- 函数包含错误处理机制，会抛出相应的异常信息

=============================================================
"""
# 使用此指令前，请确保安装必要的Python库，例如使用以下命令安装：
# pip install requests

import requests
import base64
import json

from typing import *

# 默认配置参数
DEFAULT_API_KEY = "sk-Jsqk6zfznVkeMsjLEqNLtv4eWFs3bvyLXfn3IzWhSsLg7wSK"
DEFAULT_BASE_URL = "https://one.api4gpt.com/v1"
DEFAULT_MODEL = "gemini-3-pro-preview"

# 默认提示词模板
DEFAULT_PROMPT_TEMPLATE = """请扮演"视觉重构导演"。我将上传一张参考图，请你提取画面的核心视觉主体，并编写一段中文自然语言提示词（Prompt），用于指导AI生成一张全新的、纯净无杂质的图片。
请严格遵守以下重构规则：
1. 【提取核心视觉主体】：只保留参考图中最核心的视觉主体，如人物、动物、建筑、自然景观等，去掉所有非主体元素，如背景、其他人物、装饰品、文字、LOGO等。
2. 【彻底去商业化】：视所有文字、LOGO、水印、二维码、促销贴纸、渐变遮罩、磨砂特效为"不可见"。必须将其剥离，只保留真实的主体和物理环境（或纯净背景）。
3. 【高质感描述】：使用"高清、细腻、光影自然、大师级摄影"等词汇，将画面描述为真实的摄影大片而非海报设计图。
请直接输出生成指令，不要包含思考过程"""

# 导入自定义打印函数，如果xbot模块不存在则使用标准print
try:
    from xbot.app.logging import trace as print
except ImportError:
    try:
        from xbot import print
    except ImportError:
        # 如果xbot模块不存在，使用内置print函数
        pass  # 不做任何操作，使用默认的print


def chat_with_ai_api(image_path, prompt, api_key=DEFAULT_API_KEY, base_url=DEFAULT_BASE_URL, model=DEFAULT_MODEL):
    """
    title: 与聊天AI API交互
    description: 通过API与聊天AI进行交互，支持发送图片和文本提示词，返回AI的回复内容。使用 % api_key % 认证，向 % base_url % 发送请求，包含 % image_path % 图片和 % prompt % 提示词。
    inputs:
        - api_key (str): API密钥，eg: "sk-xxxxxxxxxxxx"
        - base_url (str): API基础URL，eg: "https://one.api4gpt.com/v1"
        - image_path (file): 本地图片文件路径，eg: "C:/images/photo.jpg"
        - prompt (str): 提示词内容，默认使用DEFAULT_PROMPT_TEMPLATE
        - model (str): 使用的AI模型名称，eg: "gemini-3-pro-preview"
    outputs:
        - response_content (str): AI的回复内容，eg: "这是一张美丽的风景照片"
    """

    # 检查输入有效性
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API密钥不能为空且必须是字符串类型")

    if not base_url or not isinstance(base_url, str):
        raise ValueError("API基础URL不能为空且必须是字符串类型")

    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词不能为空且必须是字符串类型")

    def _encode_image_to_base64(image_path):
        """
        将图片文件编码为base64格式
        """
        try:
            with open(image_path, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except FileNotFoundError:
            raise FileNotFoundError(f"图片文件未找到: {image_path}")
        except Exception as e:
            raise Exception(f"读取图片文件失败: {str(e)}")

    def _send_chat_request(api_key, url, payload):
        """
        发送聊天API请求
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=160)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")

    # 编码图片为base64
    base64_image = _encode_image_to_base64(image_path)

    # 构建API请求URL
    chat_url = f"{base_url.rstrip('/')}/chat/completions"

    # 构建请求payload
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.7
    }

    # 发送请求并获取响应
    response_data = _send_chat_request(api_key, chat_url, payload)

    # 提取AI回复内容
    try:
        response_content = response_data['choices'][0]['message']['content']
        return response_content
    except (KeyError, IndexError) as e:
        raise Exception(f"解析API响应失败: {str(e)}, 响应内容: {response_data}")


# 以下是一个使用示例
if __name__ == "__main__":
    # 示例：如何使用这个函数（测试模式 - 使用默认提示词）
    # 注意：你需要替换下面的实际值为你的有效信息
    
    # 图片路径 - 本地图片文件的路径
    my_image_path = r"C:\Users\Administrator\Desktop\下载\2026年桃花节8天7晚之旅\原始海报.png"  # 替换为你的图片文件路径
    
    # 测试模式：使用默认提示词模板和模块配置
    try:
        result = chat_with_ai_api(
            image_path=my_image_path,
            prompt=DEFAULT_PROMPT_TEMPLATE,
            api_key=DEFAULT_API_KEY,
            base_url=DEFAULT_BASE_URL
        )
        print("测试结果 - 使用默认配置:", result)
    except Exception as e:
        print(f"测试发生错误: {e}")