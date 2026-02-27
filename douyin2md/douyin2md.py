#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Douyin2MD - 抖音视频转Markdown笔记工具
自动将视频转录并生成结构化笔记
"""

import os
import sys
import json
import gc
import shutil
import subprocess
import time
import signal
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from functools import wraps

# 设置HuggingFace镜像（国内加速）
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 设置Ollama并行线程数（优化CPU利用率）
os.environ['OLLAMA_NUM_PARALLEL'] = '4'

# ============================================================
#                      常量配置区
# ============================================================

# 路径配置
DEFAULT_SOURCE_DIR = r"E:\抖音知识库"
DEFAULT_OUTPUT_DIR = None  # None表示与视频同目录

# 视频配置
SUPPORTED_FORMATS = [".mp4", ".avi", ".mkv", ".mov"]

# Whisper配置
WHISPER_MODEL = "medium"  # large-v3 需要下载，先用medium测试
WHISPER_LANGUAGE = "zh"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "float32"  # float32更精确，用更多内存；int8省内存但CPU负载高
WHISPER_NUM_THREADS = 10  # CPU线程数
WHISPER_NUM_WORKERS = 2  # 并行worker数（增加内存使用，提升速度）

# 音频配置
KEEP_AUDIO = False  # 不保留转录的音频文件
AUDIO_OUTPUT_DIR = "audio_cache"  # 音频保存目录名（在源目录下）

# 百度语音识别配置
BAIDU_API_KEY = "7Jjwui11d8HT3upesb8VEr3K"
BAIDU_SECRET_KEY = "V1VZ2h7acx5j1cn7ze0pyDbLN55vPuwy"
BAIDU_ASR_URL = "https://vop.baidu.com/server_api"  # 语音识别API
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"  # 获取Token

# LLM配置 - 通义千问 API
QWEN_API_KEY = "sk-97c9189889234c25996d7e2d4f81e0e3"  # 你的 API Key
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 华北2(北京)
QWEN_MODEL = "qwen3.5-flash"  # 推荐: qwen3.5-flash, qwen-turbo, qwen-plus, qwen-max, qwen-long
QWEN_TIMEOUT = 300  # 秒（增大超时，因为需要处理长文本）
QWEN_MODELS_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/models"  # 模型列表API

# 运行时确定的模型（会在check_dependencies中更新）
CURRENT_MODEL = None

# LLM配置 - Ollama (已弃用，保留配置以备回退)
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_TIMEOUT = 600  # 秒
OLLAMA_NUM_THREAD = 10  # CPU线程数
OLLAMA_NUM_BATCH = 512  # 批处理大小（增加内存使用，提升速度）
OLLAMA_NUM_CTX = 4096  # 上下文窗口大小

# 处理配置
MAX_RETRY_TIMES = 3
RETRY_INTERVAL = 5  # 秒
SINGLE_VIDEO_TIMEOUT = 1800  # 30分钟
SINGLE_LLM_TIMEOUT = 600  # 10分钟
MEMORY_THRESHOLD = 0.95  # 95%内存阈值（提高内存利用率）

# 标签配置
TAG_CONFIG_FILENAME = "tags_config.json"
AUTO_APPROVE_THRESHOLD = 2  # 标签出现次数达到此值自动加入预设

# 关机配置
SHUTDOWN_DELAY = 100  # 秒

# 标签维度定义
TAG_DIMENSIONS = {
    "类型": {"预设": [], "同义词映射": {}},
    "作者": {"预设": [], "同义词映射": {}},
    "主题领域": {
        "预设": ["编程", "AI", "投资", "心理学", "健康", "职场", "生活", "教育", "科技", "财经", "情感", "家庭"],
        "同义词映射": {
            "编程": ["代码", "程序", "开发", "写代码", "编程语言"],
            "AI": ["人工智能", "机器学习", "深度学习", "大模型", "LLM"]
        }
    },
    "内容类型": {
        "预设": ["教程", "访谈", "科普", "vlog", "评测", "分享", "案例分析"],
        "同义词映射": {
            "教程": ["教学", "课程", "指南", "入门教程"],
            "分享": ["经验分享", "心得", "体会"]
        }
    },
    "难度级别": {
        "预设": ["入门", "进阶", "专业"],
        "同义词映射": {
            "入门": ["新手", "零基础", "小白", "初学者"],
            "进阶": ["中级", "提升", "进阶学习"]
        }
    },
    "质量评价": {
        "预设": ["精华", "一般", "水视频"],
        "同义词映射": {}
    }
}

# ============================================================
#                      依赖检测与安装
# ============================================================

def check_ffmpeg() -> bool:
    """检测ffmpeg是否安装"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10,
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_qwen_models() -> tuple:
    """检测通义千问可用模型

    Returns:
        (是否成功, 模型列表, 错误信息)
    """
    import requests
    api_key = os.environ.get("DASHSCOPE_API_KEY") or QWEN_API_KEY
    if not api_key:
        return False, [], "API Key 未配置"

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = requests.get(QWEN_MODELS_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            model_list = []
            # 过滤出通义千问相关模型
            qwen_keywords = ["qwen", "Qwen", "QWEN"]
            for m in models:
                model_id = m.get("id", "")
                # 只保留通义千问系列模型
                if any(kw in model_id for kw in qwen_keywords):
                    model_list.append(model_id)

            # 按名称排序，把 qwen3.5 放前面
            model_list.sort(key=lambda x: (
                0 if "3.5" in x else 1 if "3" in x else 2,
                x
            ))
            return True, model_list, None
        else:
            return False, [], f"API 错误: {response.status_code}"
    except Exception as e:
        return False, [], str(e)


def verify_qwen_model(model_name: str) -> tuple:
    """验证指定模型是否可用

    Returns:
        (是否可用, 建议的替代模型)
    """
    success, models, error = check_qwen_models()
    if not success:
        return False, None

    if model_name in models:
        return True, model_name

    # 尝试找到类似的模型
    suggestions = []
    for m in models:
        if model_name.replace("-", "").replace(".", "") in m.replace("-", "").replace(".", ""):
            suggestions.append(m)

    # 推荐最佳替代
    if suggestions:
        return False, suggestions[0]
    elif models:
        return False, models[0]
    else:
        return False, None


def install_python_packages():
    """安装Python依赖包"""
    packages = [
        "tqdm",
        "pyyaml",
        "psutil",
        "requests"
    ]

    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [安装] {package}...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package,
                "-q", "--disable-pip-version-check"
            ])
            print(f"  [OK] {package} 安装完成")


def check_baidu_asr() -> bool:
    """检测百度语音识别API是否可用"""
    import requests
    try:
        # 尝试获取token来验证API Key
        url = f"{BAIDU_TOKEN_URL}?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"
        response = requests.post(url, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if "access_token" in result:
                return True
            elif "error" in result:
                print(f"  [错误] 百度API: {result.get('error_description', result['error'])}")
        return False
    except Exception as e:
        print(f"  [错误] 百度API连接失败: {str(e)[:50]}")
        return False


def check_dependencies():
    """检查所有依赖"""
    global CURRENT_MODEL
    print("\n" + "=" * 50)
    print("检查依赖...")
    print("=" * 50)

    all_ok = True

    # 1. 检查ffmpeg
    print("\n[1/4] 检查 ffmpeg...")
    if check_ffmpeg():
        print("  [OK] ffmpeg 已安装")
    else:
        print("  [缺失] ffmpeg 未安装")
        print("  请手动安装: https://ffmpeg.org/download.html")
        print("  Windows可使用: winget install ffmpeg 或下载解压后添加到PATH")
        all_ok = False

    # 2. 检查Python包
    print("\n[2/4] 检查 Python 依赖包...")
    install_python_packages()

    # 3. 检查百度语音识别 API
    print("\n[3/4] 检查百度语音识别 API...")
    if check_baidu_asr():
        print("  [OK] 百度语音识别 API 可用")
    else:
        print("  [警告] 百度语音识别 API 不可用，请检查 API Key")
        all_ok = False

    # 4. 检查通义千问 API Key
    print("\n[4/4] 检查通义千问 API...")
    api_key = os.environ.get("DASHSCOPE_API_KEY") or QWEN_API_KEY
    if not api_key:
        print("  [错误] 通义千问 API Key 未配置")
        print("  请设置环境变量 DASHSCOPE_API_KEY 或修改代码中的 QWEN_API_KEY")
        all_ok = False
    else:
        print("  [OK] API Key 已配置")
        # 检测可用模型
        print("\n  正在检测可用模型...")
        success, models, error = check_qwen_models()
        if success and models:
            print(f"  可用模型 ({len(models)} 个):")
            # 显示前10个模型
            for i, m in enumerate(models[:10]):
                marker = " <- 当前选择" if m == QWEN_MODEL else ""
                print(f"    {i+1}. {m}{marker}")
            if len(models) > 10:
                print(f"    ... 还有 {len(models) - 10} 个模型")

            # 验证当前选择的模型
            available, suggestion = verify_qwen_model(QWEN_MODEL)
            if available:
                CURRENT_MODEL = QWEN_MODEL
                print(f"\n  [OK] 当前模型 '{QWEN_MODEL}' 可用")
            else:
                print(f"\n  [警告] 当前模型 '{QWEN_MODEL}' 不可用")
                if suggestion:
                    CURRENT_MODEL = suggestion
                    print(f"  [自动切换] 使用模型: {suggestion}")
                else:
                    CURRENT_MODEL = QWEN_MODEL  # 保留原设置，让API调用时报错
        else:
            print(f"  [警告] 无法获取模型列表: {error}")
            print("  将使用配置的模型继续尝试...")
            CURRENT_MODEL = QWEN_MODEL

    print("\n" + "=" * 50)
    if all_ok:
        print("所有依赖检查通过!")
    else:
        print("部分依赖缺失，请先安装后再运行。")
    print("=" * 50 + "\n")

    return all_ok

# ============================================================
#                      工具函数
# ============================================================

def retry(max_times: int = MAX_RETRY_TIMES, interval: float = RETRY_INTERVAL):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_times - 1:
                        print(f"    [重试] {attempt + 1}/{max_times}: {str(e)[:50]}")
                        time.sleep(interval)
            raise last_exception
        return wrapper
    return decorator


def timeout_handler(seconds: int):
    """超时装饰器（使用信号，仅Unix）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def _timeout_handler(signum, frame):
                raise TimeoutError(f"操作超时 ({seconds}秒)")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return result
        return wrapper
    return decorator


def check_memory() -> bool:
    """检查内存使用是否超过阈值"""
    import psutil
    memory = psutil.virtual_memory()
    return memory.percent / 100 < MEMORY_THRESHOLD


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}分{secs}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}时{minutes}分"


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             video_path],
            capture_output=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )
        return float(result.stdout.strip())
    except:
        return 0


def extract_info_from_filename(filename: str) -> Tuple[List[str], int]:
    """从文件名中提取#标签和收藏量

    Args:
        filename: 视频文件名（不含扩展名）

    Returns:
        (标签列表, 收藏量)
    """
    import re

    tags = []
    likes = 0

    # 1. 提取收藏量（文件名末尾的数字）
    # 匹配文件名末尾的纯数字（可能是收藏量）
    likes_pattern = r'(\d+)(?:\s*)?$'
    likes_match = re.search(likes_pattern, filename)
    if likes_match:
        likes = int(likes_match.group(1))

    # 2. 提取 #标签 格式
    # 匹配 #后面的内容，直到遇到空格、#、@、数字结尾等
    tag_pattern = r'#([^\s#@\d]+?)(?=\s|#|@|\d+$|$)'
    tag_matches = re.findall(tag_pattern, filename)
    for tag in tag_matches:
        # 清理标签
        tag = tag.strip('_-:：')
        if tag and len(tag) > 0:
            tags.append(tag)

    return tags, likes

# ============================================================
#                      标签配置管理
# ============================================================

class TagManager:
    """智能标签管理器"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_or_create_config()

    def _load_or_create_config(self) -> dict:
        """加载或创建配置文件"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # 兼容旧配置
            if "博主" in config.get("tag_groups", {}):
                config["tag_groups"]["作者"] = config["tag_groups"].pop("博主")
                self._save_config(config)
            if "分类" in config.get("tag_groups", {}) and "类型" not in config.get("tag_groups", {}):
                config["tag_groups"]["类型"] = config["tag_groups"].pop("分类")
                self._save_config(config)
            return config
        else:
            config = {
                "version": "1.0",
                "tag_groups": TAG_DIMENSIONS.copy(),
                "pending_tags": {}
            }
            self._save_config(config)
            return config

    def _save_config(self, config: dict = None):
        """保存配置文件"""
        if config is None:
            config = self.config
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_type_tag(self, folder_name: str) -> str:
        """获取类型标签（再上级文件夹名）"""
        # 确保"类型"维度存在
        if "类型" not in self.config["tag_groups"]:
            self.config["tag_groups"]["类型"] = {"预设": [], "同义词映射": {}}
        # 类型标签直接使用文件夹名，加入预设
        if folder_name not in self.config["tag_groups"]["类型"]["预设"]:
            self.config["tag_groups"]["类型"]["预设"].append(folder_name)
            self._save_config()
        return folder_name

    def get_author_tag(self, folder_name: str) -> str:
        """获取作者标签（上级文件夹名）"""
        # 确保"作者"维度存在
        if "作者" not in self.config["tag_groups"]:
            self.config["tag_groups"]["作者"] = {"预设": [], "同义词映射": {}}
        # 作者标签直接使用文件夹名，加入预设
        if folder_name not in self.config["tag_groups"]["作者"]["预设"]:
            self.config["tag_groups"]["作者"]["预设"].append(folder_name)
            self._save_config()
        return folder_name

    def process_tags(self, raw_tags: Dict[str, List[str]], type_name: str, author_name: str, filename_tags: List[str] = None) -> Dict[str, List[str]]:
        """处理原始标签，返回最终标签

        Args:
            raw_tags: LLM生成的标签字典
            type_name: 类型名（再上级文件夹名）
            author_name: 作者名（上级文件夹名）
            filename_tags: 从文件名提取的标签列表
        """
        result = {"类型": [type_name], "作者": [author_name]}

        # 添加文件名标签
        if filename_tags:
            result["文件名标签"] = filename_tags

        for dimension, tags in raw_tags.items():
            if dimension not in self.config["tag_groups"]:
                continue

            result[dimension] = []
            presets = self.config["tag_groups"][dimension]["预设"]
            synonyms = self.config["tag_groups"][dimension]["同义词映射"]

            for tag in tags:
                # 1. 检查是否匹配预设
                matched = False
                for preset in presets:
                    if tag == preset:
                        result[dimension].append(preset)
                        matched = True
                        break

                # 2. 检查同义词映射
                if not matched:
                    for preset, syn_list in synonyms.items():
                        if tag in syn_list or tag == preset:
                            result[dimension].append(preset)
                            matched = True
                            break

                # 3. 新标签处理
                if not matched:
                    tag_key = f"{dimension}:{tag}"

                    if tag_key in self.config["pending_tags"]:
                        self.config["pending_tags"][tag_key]["count"] += 1
                        # 达到阈值自动加入预设
                        if self.config["pending_tags"][tag_key]["count"] >= AUTO_APPROVE_THRESHOLD:
                            self.config["tag_groups"][dimension]["预设"].append(tag)
                            del self.config["pending_tags"][tag_key]
                            result[dimension].append(tag)
                        else:
                            result[dimension].append(tag)  # 暂时使用
                    else:
                        self.config["pending_tags"][tag_key] = {
                            "count": 1,
                            "dimension": dimension,
                            "first_seen": datetime.now().strftime("%Y-%m-%d")
                        }
                        result[dimension].append(tag)  # 暂时使用

        self._save_config()
        return result

    def get_all_tags_flat(self, processed_tags: Dict[str, List[str]]) -> List[str]:
        """获取扁平化的标签列表（用于YAML）"""
        all_tags = []
        for tags in processed_tags.values():
            all_tags.extend(tags)
        return list(set(all_tags))

# ============================================================
#                      音频提取
# ============================================================

class AudioExtractor:
    """音频提取器"""

    def __init__(self, temp_dir: str = None, save_dir: str = None):
        self.temp_dir = temp_dir or os.path.join(os.getcwd(), "temp_audio")
        self.save_dir = save_dir  # 音频保存目录
        os.makedirs(self.temp_dir, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的特殊字符"""
        import re
        cleaned = re.sub(r'[#%&{}\\<>*?/$!\'":@+`|=]', '_', filename)
        if not cleaned or cleaned.strip('_') == '':
            cleaned = str(uuid.uuid4())[:8]
        return cleaned

    @retry()
    def extract(self, video_path: str, video_title: str = None) -> str:
        """从视频提取音频

        Args:
            video_path: 视频文件路径
            video_title: 视频标题（用于保存音频文件名）

        Returns:
            音频文件路径
        """
        # 使用uuid确保唯一临时文件名
        audio_filename = f"{uuid.uuid4().hex}.wav"
        audio_path = os.path.join(self.temp_dir, audio_filename)

        # 使用ffmpeg提取音频
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,
            encoding='utf-8',
            errors='ignore'
        )

        # 检查音频文件是否成功生成
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            # 如果需要保存音频
            if KEEP_AUDIO and self.save_dir and video_title:
                os.makedirs(self.save_dir, exist_ok=True)
                safe_title = self._sanitize_filename(video_title)
                save_path = os.path.join(self.save_dir, f"{safe_title}.wav")
                shutil.copy2(audio_path, save_path)
            return audio_path
        else:
            error_msg = result.stderr[-500:] if result.stderr and len(result.stderr) > 500 else (result.stderr or '未知错误')
            raise Exception(f"音频提取失败: {error_msg}")

    def cleanup(self, audio_path: str = None):
        """清理临时音频文件"""
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

# ============================================================
#                      百度语音识别
# ============================================================

class Transcriber:
    """百度语音识别器"""

    def __init__(self):
        self.access_token = None
        self.token_expire_time = 0
        self.temp_dir = os.path.join(os.getcwd(), "temp_audio")
        os.makedirs(self.temp_dir, exist_ok=True)

    def _get_access_token(self) -> str:
        """获取百度 access_token"""
        import requests
        import time

        # 如果 token 未过期，直接返回
        if self.access_token and time.time() < self.token_expire_time:
            return self.access_token

        print("    获取百度语音识别 Token...")
        url = f"{BAIDU_TOKEN_URL}?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"

        response = requests.post(url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"获取百度Token失败: {response.status_code}")

        result = response.json()
        if "error" in result:
            raise Exception(f"百度Token错误: {result.get('error_description', result['error'])}")

        self.access_token = result.get("access_token")
        # 提前5分钟过期
        self.token_expire_time = time.time() + result.get("expires_in", 86400) - 300

        return self.access_token

    def _split_audio(self, audio_path: str, chunk_duration: int = 55) -> List[str]:
        """
        将音频分割成多个片段（百度短语音限制60秒）

        Args:
            audio_path: 音频文件路径
            chunk_duration: 每段最大时长（秒），默认55秒（留5秒余量）

        Returns:
            分片音频路径列表
        """
        # 获取音频时长
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             audio_path],
            capture_output=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )
        duration = float(result.stdout.strip())
        print(f"    音频时长: {format_duration(duration)}")

        # 如果时长小于限制，直接返回原文件
        if duration <= chunk_duration:
            return [audio_path]

        # 分割音频
        chunks = []
        chunk_paths = []

        # 计算分片数量
        num_chunks = int(duration // chunk_duration) + (1 if duration % chunk_duration > 0 else 0)
        print(f"    音频较长，分割为 {num_chunks} 段处理...")

        for i in range(num_chunks):
            start_time = i * chunk_duration
            chunk_path = os.path.join(self.temp_dir, f"chunk_{i}_{uuid.uuid4().hex[:8]}.wav")

            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(start_time),
                "-t", str(chunk_duration),
                "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                chunk_path
            ]

            subprocess.run(cmd, capture_output=True, timeout=60)
            if os.path.exists(chunk_path):
                chunk_paths.append(chunk_path)

        return chunk_paths if chunk_paths else [audio_path]

    @retry()
    def _recognize_chunk(self, audio_path: str) -> str:
        """识别单个音频片段"""
        import requests

        token = self._get_access_token()

        # 读取音频文件
        with open(audio_path, 'rb') as f:
            audio_data = f.read()

        # 调用百度语音识别API
        url = f"{BAIDU_ASR_URL}?cuid=douyin2md&token={token}&dev_pid=1537&format=wav&rate=16000"

        headers = {
            "Content-Type": "audio/wav; rate=16000"
        }

        response = requests.post(url, headers=headers, data=audio_data, timeout=60)

        if response.status_code != 200:
            raise Exception(f"百度语音识别请求失败: {response.status_code}")

        result = response.json()

        # 检查错误
        if "err_no" in result and result["err_no"] != 0:
            err_msg = result.get("err_msg", "未知错误")
            # 如果是token过期，清除token重试
            if result["err_no"] == 3302 or "token" in err_msg.lower():
                self.access_token = None
                raise Exception(f"Token过期，将重试: {err_msg}")
            raise Exception(f"百度语音识别错误: {err_msg}")

        # 提取结果
        if "result" in result and result["result"]:
            return result["result"][0]  # 返回第一个结果

        return ""

    @retry()
    def transcribe(self, audio_path: str) -> Tuple[str, List[dict]]:
        """
        转录音频
        返回: (完整文本, 分段列表)
        """
        # 分割音频
        chunk_paths = self._split_audio(audio_path)

        # 识别每个片段
        full_text_parts = []
        segment_list = []
        current_time = 0.0

        for i, chunk_path in enumerate(chunk_paths):
            print(f"    识别第 {i+1}/{len(chunk_paths)} 段...")
            try:
                text = self._recognize_chunk(chunk_path)
                if text:
                    full_text_parts.append(text)
                    # 创建分段信息（百度不返回时间戳，使用估算）
                    segment_list.append({
                        "start": current_time,
                        "end": current_time + 55,  # 估算
                        "text": text
                    })
                current_time += 55  # 每段约55秒
            except Exception as e:
                print(f"    警告: 第 {i+1} 段识别失败: {str(e)[:50]}")
            finally:
                # 清理分片文件（如果不是原始文件）
                if chunk_path != audio_path and os.path.exists(chunk_path):
                    os.remove(chunk_path)

        full_text = " ".join(full_text_parts)

        if not full_text:
            raise Exception("语音识别失败：未获取到任何文本")

        return full_text, segment_list

    def format_transcript(self, segments: List[dict], include_timestamps: bool = True) -> str:
        """格式化转录文本"""
        lines = []
        for seg in segments:
            if include_timestamps:
                timestamp = self._format_timestamp(seg["start"])
                lines.append(f"[{timestamp}] {seg['text']}")
            else:
                lines.append(seg["text"])
        return "\n".join(lines)

    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

# ============================================================
#                      LLM笔记生成
# ============================================================

class NoteGenerator:
    """LLM笔记生成器 - 支持通义千问 API"""

    def __init__(self, use_qwen: bool = True):
        """初始化

        Args:
            use_qwen: True 使用通义千问 API，False 使用本地 Ollama
        """
        self.use_qwen = use_qwen
        if use_qwen:
            self.api_url = f"{QWEN_BASE_URL}/chat/completions"
            # 优先使用环境变量，其次使用配置文件
            self.api_key = os.environ.get("DASHSCOPE_API_KEY") or QWEN_API_KEY
            if not self.api_key:
                raise ValueError(
                    "请设置通义千问 API Key！\n"
                    "方式1: 设置环境变量 DASHSCOPE_API_KEY\n"
                    "方式2: 在代码中修改 QWEN_API_KEY = '你的key'\n"
                    "获取API Key: https://dashscope.console.aliyun.com/"
                )
        else:
            self.api_url = f"{OLLAMA_HOST}/api/generate"

    def _build_messages(self, transcript: str, video_title: str, category: str) -> list:
        """构建消息列表（通义千问格式）"""
        system_prompt = """你是一个专业的视频内容整理助手。你的任务是根据视频转录文本生成结构化的笔记。

【重要规则】
1. 必须使用简体中文输出，禁止使用繁体中文
2. 严格按照JSON格式输出，不要输出任何其他内容
3. JSON必须完整、格式正确"""

        user_prompt = f"""请根据以下视频转录文本，生成结构化的笔记。

视频标题：{video_title}
分类：{category}

转录文本：
{transcript}

请严格按照以下JSON格式输出（不要输出其他任何内容，只输出JSON）：
{{
    "title": "视频标题（可优化，简体中文）",
    "summary": "一句话摘要（不超过50字，简体中文）",
    "content_summary": {{
        "main_idea": "用一两句话总结视频的核心观点或主题（30字以内）",
        "points": [
            "第一点：具体内容...",
            "第二点：具体内容...",
            "第三点：具体内容..."
        ]
    }},
    "quotes": ["金句1", "金句2"],
    "transcript_written": "这是转录文本的书面语言版本。请将口语化的转录文本转成书面语言：加标点符号、正确分段、润色表达、删除口语废话（如"那个"、"嗯"、"然后呢"等）、保持原意不变。按自然段落分段，每个段落要完整。",
    "tags": {{
        "主题领域": ["标签1", "标签2"],
        "内容类型": ["标签"],
        "难度级别": ["标签"],
        "质量评价": ["标签"]
    }}
}}

要求：
1. content_summary.main_idea 要用一两句话概括核心观点，简洁有力
2. content_summary.points 要用有序列表梳理内容要点，3-6条，每条50字以内，格式如"第一点：xxx"、"第二点：xxx"
3. quotes 提取2-3句有价值的金句，如无则留空数组
4. transcript_written 是最重要的部分：
   - 必须将口语转成书面语
   - 加上正确的标点符号
   - 按语义自然分段
   - 删除口语废话和重复内容
   - 保持原意，不要添加原文没有的内容
5. tags 中每个维度选择1-3个标签"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _build_prompt(self, transcript: str, video_title: str, category: str) -> str:
        """构建提示词（Ollama格式）"""
        return f"""你是一个专业的视频内容整理助手。请根据以下视频转录文本，生成结构化的笔记。

【重要】必须使用简体中文输出，禁止使用繁体中文！

视频标题：{video_title}
分类：{category}

转录文本：
{transcript}

请严格按照以下JSON格式输出（不要输出其他任何内容，只输出JSON）：
{{
    "title": "视频标题（可优化，简体中文）",
    "summary": "一句话摘要（不超过50字，简体中文）",
    "content_summary": "内容梳理：这个视频主要讲了什么内容，按照逻辑顺序梳理（200-400字）",
    "quotes": ["金句1", "金句2"],
    "transcript_written": "这是转录文本的书面语言版本。请将口语化的转录文本转成书面语言：加标点符号、正确分段、润色表达、删除口语废话。按自然段落分段，每个段落要完整。",
    "tags": {{
        "主题领域": ["标签1", "标签2"],
        "内容类型": ["标签"],
        "难度级别": ["标签"],
        "质量评价": ["标签"]
    }}
}}

要求：
1. content_summary 要用简洁的语言梳理视频的主要内容脉络
2. quotes 提取2-3句有价值的金句，如无则留空数组
3. transcript_written 是最重要的部分：
   - 必须将口语转成书面语
   - 加上正确的标点符号
   - 按语义自然分段
   - 删除口语废话和重复内容
   - 保持原意，不要添加原文没有的内容
4. tags 中每个维度选择1-3个标签"""

    @retry()
    def generate(self, transcript: str, video_title: str, blogger: str) -> dict:
        """生成笔记"""
        import requests

        if self.use_qwen:
            return self._generate_qwen(transcript, video_title, blogger)
        else:
            return self._generate_ollama(transcript, video_title, blogger)

    def _generate_qwen(self, transcript: str, video_title: str, blogger: str) -> dict:
        """使用通义千问 API 生成笔记"""
        import requests

        messages = self._build_messages(transcript, video_title, blogger)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 使用检测到的可用模型
        model = CURRENT_MODEL or QWEN_MODEL
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,  # 降低温度，提高输出稳定性
            "max_tokens": 8192  # 增大输出token限制，支持长文本书面化
        }

        print(f"      调用模型: {model}")

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=QWEN_TIMEOUT
        )

        if response.status_code != 200:
            error_detail = response.text[:200] if response.text else "未知错误"
            raise Exception(f"通义千问 API 请求失败 ({response.status_code}): {error_detail}")

        result = response.json()

        # 检查是否有错误
        if "error" in result:
            raise Exception(f"API 错误: {result['error']}")

        # 提取内容
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise Exception("API 返回内容为空")

        # 打印 token 使用情况
        usage = result.get("usage", {})
        if usage:
            print(f"      Token 用量 - 输入: {usage.get('prompt_tokens', 0)}, 输出: {usage.get('completion_tokens', 0)}")

        return self._parse_response(content)

    def _generate_ollama(self, transcript: str, video_title: str, blogger: str) -> dict:
        """使用本地 Ollama 生成笔记"""
        import requests

        prompt = self._build_prompt(transcript, video_title, blogger)

        response = requests.post(
            self.api_url,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 4096,
                    "num_thread": OLLAMA_NUM_THREAD,
                    "num_batch": OLLAMA_NUM_BATCH,
                    "num_ctx": OLLAMA_NUM_CTX
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        if response.status_code != 200:
            raise Exception(f"Ollama请求失败: {response.status_code}")

        result = response.json()
        content = result.get("response", "")

        return self._parse_response(content)

        # 解析JSON
        return self._parse_response(content)

    def _parse_response(self, content: str) -> dict:
        """解析LLM响应"""
        import re

        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                # 验证必要字段是否存在
                if "title" in result and "summary" in result:
                    return result
                else:
                    raise Exception("LLM返回JSON缺少必要字段")
            except json.JSONDecodeError as e:
                raise Exception(f"LLM返回JSON解析失败: {str(e)[:50]}")

        raise Exception("LLM返回内容格式错误，未找到有效JSON")

# ============================================================
#                      Markdown生成
# ============================================================

class MarkdownWriter:
    """Markdown文件生成器"""

    def write(self, output_path: str, video_path: str, video_title: str,
              duration: float, category: str, author: str, likes: int,
              transcript: str, segments: List[dict], note: dict,
              tags: Dict[str, List[str]], all_tags: List[str],
              filename_tags: List[str] = None):
        """生成Markdown文件"""

        # YAML Front Matter
        yaml_tags = ", ".join([f'"{t}"' for t in all_tags])

        content = f"""---
title: "{note.get('title', video_title)}"
duration: "{format_duration(duration)}"
likes: {likes}
source: "{video_path}"
processed: "{datetime.now().strftime('%Y-%m-%d %H:%M')}"
category: "{category}"
author: "{author}"
filename_tags: {json.dumps(filename_tags or [], ensure_ascii=False)}
tags: [{yaml_tags}]
---

# {note.get('title', video_title)}

## 一句话摘要

{note.get('summary', '无')}

## 内容梳理

"""

        # 处理 content_summary（总分结构）
        content_summary = note.get('content_summary', {})
        if isinstance(content_summary, dict):
            # 总：核心观点
            main_idea = content_summary.get('main_idea', '')
            if main_idea:
                content += f"{main_idea}\n\n"

            # 分：有序列表
            points = content_summary.get('points', [])
            if points:
                for point in points:
                    content += f"{point}\n"
                content += "\n"
        else:
            # 兼容旧格式（纯文本）
            content += f"{content_summary}\n\n"

        content += f"""## 原文转录

{note.get('transcript_written', '')}
"""

        # 金句
        quotes = note.get('quotes', [])
        if quotes:
            content += "\n## 金句\n\n"
            for quote in quotes:
                if quote:
                    content += f"> {quote}\n\n"

        # 基础信息
        content += f"""## 基础信息

- **时长**: {format_duration(duration)}
- **收藏量**: {likes if likes > 0 else '未知'}
- **来源**: {video_path}
- **分类**: {category}
- **作者**: {author if author else '未知'}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 标签

"""
        # 标签（按维度）
        for dimension, tag_list in tags.items():
            if tag_list:
                tag_str = " ".join([f"`#{t}`" for t in tag_list])
                content += f"**{dimension}**: {tag_str}\n\n"

        content += "---\n*由 Douyin2MD 自动生成*\n"

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

# ============================================================
#                      视频扫描器
# ============================================================

class VideoScanner:
    """视频文件扫描器"""

    def __init__(self, source_dir: str):
        self.source_dir = source_dir

    def scan(self) -> List[Tuple[str, str, str]]:
        """
        扫描所有未处理的视频
        返回: [(视频路径, 作者, 类型), ...]
        - 作者 = 上级目录名
        - 类型 = 再上一级目录名
        """
        videos = []
        source_path = Path(self.source_dir)

        if not source_path.exists():
            raise Exception(f"源目录不存在: {self.source_dir}")

        for video_file in source_path.rglob("*"):
            if video_file.suffix.lower() in SUPPORTED_FORMATS:
                # 检查是否已处理（同名md存在）
                md_file = video_file.with_suffix('.md')
                if not md_file.exists():
                    # 获取目录结构
                    parent = video_file.parent  # 上级目录 = 作者
                    grandparent = parent.parent  # 再上级目录 = 类型

                    author = parent.name if parent != source_path else "未知作者"
                    category = grandparent.name if grandparent != source_path else "未知分类"

                    videos.append((str(video_file), author, category))

        return videos

# ============================================================
#                      主处理器
# ============================================================

class VideoProcessor:
    """视频处理器（主逻辑）"""

    def __init__(self, source_dir: str, auto_shutdown: bool = False, use_qwen: bool = True):
        self.source_dir = source_dir
        self.auto_shutdown = auto_shutdown
        self.use_qwen = use_qwen

        # 初始化组件
        self.scanner = VideoScanner(source_dir)
        self.audio_extractor = AudioExtractor(
            save_dir=os.path.join(source_dir, AUDIO_OUTPUT_DIR) if KEEP_AUDIO else None
        )
        self.transcriber = Transcriber()
        self.note_generator = NoteGenerator(use_qwen=use_qwen)
        self.md_writer = MarkdownWriter()
        self.tag_manager = TagManager(
            os.path.join(source_dir, TAG_CONFIG_FILENAME)
        )

        # 统计
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": [],
            "start_time": None
        }

    def process_all(self):
        """处理所有视频"""
        print("\n" + "=" * 60)
        print(f"扫描目录: {self.source_dir}")
        print("=" * 60)

        videos = self.scanner.scan()
        self.stats["total"] = len(videos)
        self.stats["start_time"] = datetime.now()

        if not videos:
            print("\n没有发现需要处理的视频。")
            return

        print(f"\n发现 {len(videos)} 个待处理视频\n")

        for i, (video_path, author, category) in enumerate(videos, 1):
            video_name = Path(video_path).name
            print(f"\n{'='*60}")
            print(f"[{i}/{len(videos)}] {video_name}")
            print('='*60)

            success = self._process_single(video_path, author, category, i, len(videos))

            if success:
                self.stats["success"] += 1
            else:
                self.stats["failed"].append(video_path)

            # 内存检查和垃圾回收
            gc.collect()
            if not check_memory():
                print("\n警告: 内存使用过高，暂停处理...")
                time.sleep(30)
                gc.collect()

        # 输出统计
        self._print_stats()

        # 自动关机
        if self.auto_shutdown:
            self._shutdown()

    def _process_single(self, video_path: str, author: str, category: str, current: int = 0, total: int = 0) -> bool:
        """处理单个视频

        Args:
            video_path: 视频文件路径
            author: 作者（上级目录名）
            category: 类型（再上级目录名）
            current: 当前序号
            total: 总数
        """
        video_name = Path(video_path).stem
        start_time = time.time()

        try:
            print(f"    类型: {category}")
            print(f"    作者: {author}")

            # 从文件名提取标签和收藏量
            filename_tags, likes = extract_info_from_filename(video_name)
            if filename_tags:
                print(f"    文件名标签: {', '.join(filename_tags)}")
            if likes > 0:
                print(f"    收藏量: {likes}")

            # 1. 获取视频时长
            print("    [1/5] 获取视频信息...")
            duration = get_video_duration(video_path)
            print(f"          时长: {format_duration(duration)}")

            # 2. 提取音频
            print("    [2/5] 提取音频...")
            audio_path = self.audio_extractor.extract(video_path, video_name)

            # 3. 转录
            print("    [3/5] 转录中（这可能需要较长时间）...")
            transcribe_start = time.time()
            transcript, segments = self.transcriber.transcribe(audio_path)
            transcribe_time = time.time() - transcribe_start
            print(f"          转录耗时: {format_duration(transcribe_time)}")

            # 4. 生成笔记
            print("    [4/5] 生成笔记...")
            note_start = time.time()
            note = self.note_generator.generate(transcript, video_name, author)
            note_time = time.time() - note_start
            print(f"          笔记耗时: {format_duration(note_time)}")

            # 5. 处理标签
            print("    [5/5] 处理标签...")
            type_tag = self.tag_manager.get_type_tag(category)
            author_tag = self.tag_manager.get_author_tag(author)
            processed_tags = self.tag_manager.process_tags(
                note.get('tags', {}), type_tag, author_tag, filename_tags
            )
            all_tags = self.tag_manager.get_all_tags_flat(processed_tags)

            # 生成Markdown
            output_path = str(Path(video_path).with_suffix('.md'))
            self.md_writer.write(
                output_path=output_path,
                video_path=video_path,
                video_title=video_name,
                duration=duration,
                category=category,
                author=author,
                transcript=transcript,
                segments=segments,
                note=note,
                tags=processed_tags,
                all_tags=all_tags,
                filename_tags=filename_tags,
                likes=likes
            )

            # 清理临时文件（如果不需要保存）
            if not KEEP_AUDIO:
                self.audio_extractor.cleanup(audio_path)

            elapsed = time.time() - start_time
            print(f"    完成! 耗时: {format_duration(elapsed)}")
            return True

        except Exception as e:
            print(f"    错误: {str(e)[:100]}")
            # 清理
            self.audio_extractor.cleanup()
            return False

    def _print_stats(self):
        """输出统计信息"""
        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()

        print("\n" + "=" * 60)
        print("处理完成!")
        print("=" * 60)
        print(f"总视频数: {self.stats['total']}")
        print(f"成功处理: {self.stats['success']}")
        print(f"失败数量: {len(self.stats['failed'])}")
        print(f"总耗时: {format_duration(elapsed)}")

        if self.stats["failed"]:
            print("\n失败列表:")
            for video in self.stats["failed"]:
                print(f"  - {video}")

    def _shutdown(self):
        """自动关机"""
        print(f"\n将在 {SHUTDOWN_DELAY} 秒后自动关机...")
        print("按 Ctrl+C 取消")

        try:
            for i in range(SHUTDOWN_DELAY, 0, -1):
                print(f"\r倒计时: {i} 秒  ", end="", flush=True)
                time.sleep(1)
            print("\n正在关机...")
            if sys.platform == "win32":
                os.system("shutdown /s /t 0")
            else:
                os.system("shutdown -h now")
        except KeyboardInterrupt:
            print("\n已取消关机")

# ============================================================
#                      主程序
# ============================================================

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  Douyin2MD - 抖音视频转Markdown笔记工具")
    print("  (百度语音识别 + 通义千问 API)")
    print("=" * 60)

    # 显示当前配置
    print(f"\n默认配置:")
    print(f"  语音识别: 百度短语音API")
    print(f"  LLM模型: {QWEN_MODEL} (通义千问)")
    print(f"  源目录: {DEFAULT_SOURCE_DIR}")

    # 1. 检查依赖（会自动检测可用模型并更新 CURRENT_MODEL）
    if not check_dependencies():
        print("\n请先安装缺失的依赖，然后重新运行。")
        input("\n按回车键退出...")
        return

    # 显示最终使用的模型
    model_to_use = CURRENT_MODEL or QWEN_MODEL
    print(f"\n将使用模型: {model_to_use}")

    # 2. 选择模式
    print("\n" + "-" * 40)
    print("请选择运行模式：")
    print("  直接回车 = 默认模式（使用默认设置）")
    print("  输入 1   = 自定义模式（自定义配置）")
    print("-" * 40)
    mode = input("请选择: ").strip()

    if mode == "1":
        # 自定义模式
        print("\n自定义模式开发中，敬请期待...")
        print("当前使用默认模式运行")
        source_dir = DEFAULT_SOURCE_DIR
        auto_shutdown = False
    else:
        # 默认模式
        source_dir = DEFAULT_SOURCE_DIR

    if not os.path.exists(source_dir):
        print(f"错误: 目录不存在 - {source_dir}")
        input("\n按回车键退出...")
        return

    # 3. 询问自动关机
    print("\n" + "-" * 40)
    choice = input("完成后是否自动关机? (y/n，默认n): ").strip().lower()
    auto_shutdown = choice == 'y'

    # 4. 开始处理
    model_to_use = CURRENT_MODEL or QWEN_MODEL
    print("\n" + "=" * 60)
    print("准备开始处理...")
    print(f"源目录: {source_dir}")
    print(f"使用模型: {model_to_use} (通义千问)")
    print(f"自动关机: {'是' if auto_shutdown else '否'}")
    print("=" * 60)

    # 5. 执行处理
    processor = VideoProcessor(source_dir, auto_shutdown, use_qwen=True)
    processor.process_all()

    input("\n按回车键退出...")


if __name__ == "__main__":
    main()