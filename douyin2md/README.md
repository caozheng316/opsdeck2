# Douyin2MD - 抖音视频转Markdown笔记工具

自动将本地视频转录并生成结构化Markdown笔记，支持智能标签系统。

## 功能特性

- **视频转录**: 使用 Whisper large-v3 模型进行语音识别
- **智能笔记**: 使用 Qwen2.5-14B 生成结构化笔记
- **智能标签**: 自动生成多维度标签，支持预设+自由补充
- **断点续传**: 自动检测已处理视频，支持中断后继续
- **无人值守**: 支持完成后自动关机

## 系统要求

- Python 3.8+
- 至少 16GB 内存（推荐 32GB+）
- 足够的磁盘空间存储模型

## 依赖安装

### 1. 外部依赖

**ffmpeg** (音频提取)
```bash
# Windows (使用 winget)
winget install ffmpeg

# 或下载解压后添加到 PATH
# https://ffmpeg.org/download.html
```

**Ollama** (LLM服务)
```bash
# 下载安装
# https://ollama.ai

# 拉取模型
ollama pull qwen2.5:14b
```

### 2. Python依赖

```bash
pip install -r requirements.txt
```

或直接运行程序，会自动检测并安装。

## 使用方法

### 主程序

```bash
python douyin2md.py
```

运行后按提示操作：
1. 输入视频目录（回车使用默认路径）
2. 选择是否自动关机
3. 确认开始处理

### 标签管理

```bash
python tag_manager.py
```

功能：
- 查看预设标签和待审核标签
- 批准/删除待审核标签
- 添加同义词映射
- 手动添加预设标签

## 配置说明

编辑 `douyin2md.py` 顶部的常量配置区：

```python
# 路径配置
DEFAULT_SOURCE_DIR = r"E:\抖音知识库"  # 默认源目录

# Whisper配置
WHISPER_MODEL = "large-v3"    # 模型大小: tiny/base/small/medium/large
WHISPER_LANGUAGE = "zh"        # 语言

# LLM配置
OLLAMA_MODEL = "qwen2.5:14b"  # Ollama模型名称
OLLAMA_TIMEOUT = 600           # 超时时间(秒)

# 处理配置
MAX_RETRY_TIMES = 3           # 最大重试次数
SINGLE_VIDEO_TIMEOUT = 1800   # 单视频最长处理时间(秒)

# 标签配置
AUTO_APPROVE_THRESHOLD = 2    # 标签自动通过阈值(出现次数)
```

## 输出示例

生成的 Markdown 文件：

```markdown
---
title: "Python数据可视化教程"
duration: "5分32秒"
source: "E:/抖音知识库/AI教程/video.mp4"
processed: "2026-02-25 20:30"
blogger: "AI教程"
tags: ["编程", "Python", "教程", "AI教程"]
---

# Python数据可视化教程

## 一句话摘要

讲解如何使用Python进行数据可视化的三个核心技巧。

## 核心要点

1. matplotlib的基础绘图流程
2. 如何自定义图表样式
3. 数据预处理的注意事项

## 详细笔记

### 一、基础绘图流程

导入库和创建画布的基本方法...

### 二、样式自定义

图表颜色、字体、标签的设置...

## 原文转录

**[00:00]** 大家好，今天我们来学习...

**[00:15]** 首先导入matplotlib...

## 金句

> "数据可视化不是画图，而是讲故事。"

## 基础信息

- **时长**: 5分32秒
- **来源**: E:/抖音知识库/AI教程/video.mp4
- **博主**: AI教程
- **处理时间**: 2026-02-25 20:30

## 标签

**博主**: `#AI教程`

**主题领域**: `#编程` `#Python`

**内容类型**: `#教程`

**难度级别**: `#入门`

---
*由 Douyin2MD 自动生成*
```

## 标签系统

标签分为五个维度：

| 维度 | 说明 | 示例 |
|------|------|------|
| 博主 | 视频来源（文件夹名） | AI教程、科技达人 |
| 主题领域 | 内容主题 | 编程、AI、投资 |
| 内容类型 | 视频形式 | 教程、访谈、科普 |
| 难度级别 | 学习难度 | 入门、进阶、专业 |
| 质量评价 | 内容价值 | 精华、一般、水视频 |

标签处理规则：
- 预设标签：自动匹配
- 同义词：自动映射到预设
- 新标签：首次暂存，第二次出现自动加入预设

## 目录结构

```
E:\抖音知识库\
├── 博主A\
│   ├── 视频1.mp4
│   ├── 视频1.md          # 生成的笔记
│   └── 视频2.mp4
├── 博主B\
│   └── ...
└── tags_config.json      # 标签配置文件
```

## 常见问题

**Q: 处理速度慢怎么办？**
A: 可以将 WHISPER_MODEL 改为 "medium" 或 "small"，速度更快但精度略低。

**Q: 内存不足？**
A: 降低 Whisper 模型大小，或使用量化版本。

**Q: 标签不准确？**
A: 使用 tag_manager.py 手动审核和调整标签。

## License

MIT