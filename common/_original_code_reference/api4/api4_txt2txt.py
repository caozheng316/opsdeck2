"""
=============================================================
api4_txt2txt.py 使用说明
=============================================================

功能概述:
--------
该模块提供了一个与API4GPT文本生成API交互的功能，支持发送文本提示词
并返回AI生成的文本回复。主要用于文本生成场景。

输入要求:
--------
- prompt (str, 外部接入): 提示词内容
- model (str, 可选，外部接入): 模型名称，默认为 "gemini-3-pro"
- api_key (str，已配置): API密钥，用于认证
- base_url (str，已配置): API基础URL地址
输出内容:
--------
- response_content (str): AI生成的文本回复内容

外部模块调用:
------------
- requests: 用于发送HTTP请求
- json: 用于处理JSON数据
- typing: 用于类型注解
- xbot.app.logging.trace 或 xbot.print (可选): 自定义日志打印函数

使用流程:
--------
外部调用方式:
1. 导入模块: from opsdeck.common.api4.api4_txt2txt import main
2. 直接调用: main(loop_configs=[{"prompt": "你好", "model": "gemini-3-pro"}])
3. 或使用字典调用: main(external_config_file=r"C:\path\to\config.json")

测试模式（直接运行文件）:
- 自动使用默认提示词
- 只发起一次API请求
- 用于验证模块功能是否正常

注意事项:
--------
- 确保已安装 requests 库
- API密钥和URL需要有效
- 网络连接正常
- 函数包含错误处理机制，会抛出相应的异常信息
- 支持自定义模型名称和提示词

=============================================================
"""

import requests
import json

from typing import *

DEFAULT_API_KEY = "sk-UfZhScIleUAfu0zT6WdeRMVT76zAwc8H3eMhY3vw0badLTfS"
DEFAULT_BASE_URL = "https://one.api4gpt.com/v1"
DEFAULT_MODEL = "gemini-3-pro"

EXTERNAL_CONFIG_FILE = None

DEFAULT_LOOP_CONFIGS = [
    {
        "prompt": "你好，请介绍一下你自己",
        "model": DEFAULT_MODEL
    }
]

try:
    from xbot.app.logging import trace as print
except ImportError:
    try:
        from xbot import print
    except ImportError:
        pass


def call_txt2txt_api(
    prompt: str,
    model: str = DEFAULT_MODEL,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL
) -> str:
    """
    title: 调用API4GPT文本生成API
    description: 通过API与API4GPT进行文本交互，发送提示词并返回AI生成的文本内容。使用 % api_key % 认证，向 % base_url % 发送请求。
    inputs:
        - prompt (str): 提示词内容，eg: "你好，请介绍一下你自己"
        - model (str): 使用的AI模型名称，eg: "gemini-3-pro"
        - api_key (str): API密钥，eg: "sk-xxxxxxxxxxxx"
        - base_url (str): API基础URL，eg: "https://one.api4gpt.com/v1"
    outputs:
        - response_content (str): AI生成的文本内容，eg: "你好！我是..."
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API密钥不能为空且必须是字符串类型")

    if not base_url or not isinstance(base_url, str):
        raise ValueError("API基础URL不能为空且必须是字符串类型")

    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词不能为空且必须是字符串类型")

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    chat_url = f"{base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(chat_url, headers=headers, json=payload, timeout=160)
        response.raise_for_status()
        response_data = response.json()

        response_content = response_data['choices'][0]['message']['content']
        return response_content
    except requests.exceptions.RequestException as e:
        raise Exception(f"API请求失败: {str(e)}")
    except (KeyError, IndexError) as e:
        raise Exception(f"解析API响应失败: {str(e)}, 响应内容: {response_data}")


def load_external_config(config_file: str) -> dict:
    """
    title: 从外部JSON文件加载配置
    description: 读取外部JSON配置文件，返回包含loop_configs的配置字典。
    inputs:
        - config_file (str): 外部配置文件路径，eg: "C:\\config.json"
    outputs:
        - config (dict): 解析后的配置字典
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件未找到: {config_file}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON格式错误: {str(e)}")


def main(
    account_index: Optional[int] = None,
    loop_configs: Optional[List[dict]] = None,
    external_config_file: Optional[str] = None
) -> List[str]:
    """
    title: API4文本生成主函数
    description: 支持直接调用和字典调用两种方式，调用API4GPT文本生成API并返回结果列表。
    inputs:
        - account_index (int): 账号索引（暂未使用，保留参数）
        - loop_configs (list): 任务配置列表，每个配置包含prompt和model
        - external_config_file (str): 外部配置文件路径
    outputs:
        - results (list): AI生成的文本内容列表
    """
    config_file = external_config_file if external_config_file else EXTERNAL_CONFIG_FILE

    if config_file and loop_configs is None:
        config = load_external_config(config_file)
        loop_configs = config.get('loop_configs', [])

    if loop_configs is None:
        loop_configs = DEFAULT_LOOP_CONFIGS

    results = []

    for idx, config_item in enumerate(loop_configs):
        prompt = config_item.get('prompt', '')
        model = config_item.get('model', DEFAULT_MODEL)

        if not prompt:
            print(f"警告: 第{idx + 1}条配置的提示词为空，跳过")
            continue

        try:
            result = call_txt2txt_api(
                prompt=prompt,
                model=model,
                api_key=DEFAULT_API_KEY,
                base_url=DEFAULT_BASE_URL
            )
            results.append(result)
            print(f"第{idx + 1}条任务完成: {prompt[:20]}... -> {result[:50]}...")
        except Exception as e:
            print(f"第{idx + 1}条任务失败: {str(e)}")
            results.append("")

    return results


if __name__ == "__main__":
    print("测试模式：使用默认配置")

    test_results = main()

    print("\n===== 测试结果 =====")
    for i, result in enumerate(test_results):
        print(f"结果 {i + 1}: {result}")
