# -*- coding: utf-8 -*-
"""
=============================================================
2_poster_background_extractor.py使用说明
=============================================================

重构说明:
--------
该脚本已针对新的目录结构进行了重构，调整了模块导入路径。
- API模块路径: ../common/api4/api4_image2prompt_engine.py
- ACH模块路径: ../common/ach/ach.py
- 配置文件路径: savexiumi_config.json (位于当前目录)

功能概述:
--------
该脚本旨在批量处理图片，通过调用AI API为每张图片生成提示词，
并执行相关任务以去除海报水印并获取海报背景原图。

输入要求:
--------
- 图片目录路径：用户需提供包含待处理图片的目录路径。
  脚本会递归查找该目录及其子目录中的所有名为 "*HB.jpg" 的文件。
- 运行参数（可选）：
  - 浏览器模式（无头/有头）
  - 模型选择（1 或 2）
  - 等待时间（秒）
  - 输出文件夹路径
  - 提示词（默认使用上次使用的提示词或通过API生成）

输出内容:
--------
- 处理后的图片：根据生成的提示词和配置，输出去除水印后的海报背景原图。
- 配置文件：生成或更新 savexiumi_config.json 文件，记录每次处理任务的参数和状态。
- 日志信息：实时输出处理进度、错误信息和操作结果。

外部模块调用:
------------
- API_TXT_正方形旅游海报.chat_with_ai_api：用于调用AI API生成图片提示词。
- ach.main：执行具体的图像处理任务，如去除水印和生成背景原图。

使用流程:
--------
1. 启动脚本后，系统会提示输入图片目录路径。
2. 选择执行模式（清空所有配置重新开始 或 跳过已处理项目仅处理新项目）。
3. 设置运行参数（可选）。
4. 脚本开始遍历目录中的图片，为每张图片生成提示词并保存配置。
5. 执行 ach.py 完成图像处理任务。
6. 查看输出结果和日志信息。

注意事项:
--------
- 确保 api4_image2prompt_engine.py 和 ach.py 文件位于同一目录下。
- 输入目录必须存在且包含至少一张名为 "*HB.jpg" 的图片文件。
- 脚本支持断点续传，可通过选择相应模式跳过已处理的项目。

=============================================================
原始功能描述:
批量处理图片生成提示词并执行任务
功能：遍历指定目录下的所有图片文件，通过API生成提示词，更新配置文件并执行任务
=============================================================
"""


import os
import json
import glob
import re
from pathlib import Path
import sys
import time

# 导入自定义模块
try:
    # 从common/api4目录导入API模块
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'common', 'api4'))
    from api4_image2prompt_engine import chat_with_ai_api
    
    # 从common/ach目录导入ach模块
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'common', 'ach'))
    from ach import main as ach_main
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 api4_image2prompt_engine.py 和 ach.py 文件存在于正确的位置")
    sys.exit(1)

# 配置常量
CONFIG_FILENAME = os.path.join(os.path.dirname(__file__), '..', 'common', 'ach', 'ach_config.json')
DEFAULT_PROMPT = "pan camera slightly left, low angle"
DEFAULT_MODEL = "2"
DEFAULT_WAIT_TIME = "180"
SUPPORTED_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png']


def log_message(msg):
    """
    统一日志记录
    """
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def get_output_folder_path(input_folder_path):
    """
    获取输出文件夹路径（与输入目录相同）
    """
    return input_folder_path


def load_previous_config():
    """
    读取上次使用的配置信息
    Returns:
        tuple: (last_input_folder, last_prompt)
    """
    config_file_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
    last_folder = ""
    last_prompt = DEFAULT_PROMPT
    
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    last_folder = data.get('last_input_folder', "")
                    last_prompt = data.get('banana_prompt', DEFAULT_PROMPT)
        except Exception as e:
            log_message(f"读取旧配置失败: {e}")
    
    return last_folder, last_prompt


def get_image_files(directory):
    """
    获取目录下所有图片文件
    Args:
        directory (str): 目录路径
    Returns:
        list: 图片文件路径列表
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"目录不存在: {directory}")
    
    # 递归查找所有子文件夹中的"*HB.jpg"文件
    poster_files = glob.glob(os.path.join(directory, "**", "*HB.jpg"), recursive=True)
    
    # 去重 (基于绝对路径)
    unique_image_paths = set()
    deduplicated_image_list = []
    for img_path in poster_files:
        abs_path = os.path.abspath(img_path)
        if abs_path not in unique_image_paths:
            unique_image_paths.add(abs_path)
            deduplicated_image_list.append(img_path)
    
    # 排序
    deduplicated_image_list = sorted(deduplicated_image_list)
    
    log_message(f"在目录 '{directory}' 及其子目录中找到 {len(deduplicated_image_list)} 个*HB.jpg文件")
    return deduplicated_image_list


def generate_prompt_for_image(image_path):
    """
    为单张图片生成提示词（带重试机制）
    Args:
        image_path (str): 图片文件路径
    Returns:
        str or None: 生成的提示词，失败时返回None
    """
    # API配置信息
    api_key = "sk-Jsqk6zfznVkeMsjLEqNLtv4eWFs3bvyLXfn3IzWhSsLg7wSK"
    base_url = "https://one.api4gpt.com/v1"
    
    # 提示词模板
    prompt_template = """# Role: 视觉重构导演 (Visual Reconstruction Director)

 1. 核心任务
你的任务是接收用户上传的任意尺寸、带有复杂商业设计的海报（参考图），从中**提取核心视觉主体**，并编写一段中文自然语言提示词（Prompt）。这段提示词将用于指导AI模型生成一张**全新的、正方形（1:1）、纯净无杂质**的图片。

 2. 必须遵守的铁律 (Iron Laws)

1.  **正方形强制重构 (Square Re-composition)**
    *   **重绘逻辑**：不要描述原图的长宽比。必须在脑海中将画面主体“剪切”下来，放置在一个正方形的画布中央。
    *   **填充与裁剪**：如果原图是长图（竖构图），提示词需描述主体为“半身特写”或“增加左右背景延伸”以填满正方形；如果原图是宽图，提示词需描述“聚焦主体”以去除多余边缘。
    *   **关键词植入**：输出中必须包含“正方形构图”、“居中构图”等词汇。

2.  **彻底去商业化 (De-Commercialization)**
    *   **去文字**：视所有文字、标题、LOGO、水印、二维码为“隐形”，**绝对不要在提示词中提及它们**。
    *   **去设计感**：视所有渐变色背景、透明遮罩、磨砂玻璃效果、光晕装饰为“杂质”，不予描述。
    *   **还原本质**：如果原图人物脚下有渐变阴影，你要描述为“清晰的地面”；如果背景是虚化颜色的色块，你要描述为“干净的纯色背景”或“真实的物理环境”。

3.  **自然语言指令化 (Natural Language Directing)**
    *   输出的不是“图片描述”，而是“生成指令”。
    *   使用高质量的形容词（如：高清、细腻、光影自然、大师级摄影）。
4.  **不允许出现任何其他内容**
    *   不允许出现思考过程、寒暄、任何没被允许的其他文字。


 3. 思考路径 (Thinking Process)

在输出前，请按以下步骤思考（不要输出思考过程）：
1.  **锁定主体**：图里最重要的是什么？（是一个人？一双鞋？还是一盘菜？）
2.  **剥离干扰**：把主体从带有文字和特效的图层中剥离出来。
3.  **重设场景**：在这个主体周围想象一个适合正方形构图的背景。
4.  **生成指令**：用中文写下这个全新的画面。

 4. 输出模版

请直接输出以下内容，方便用户复制：

 
(一段流畅的中文自然语言。必须包含：正方形构图描述 + 主体细节 + 纯净背景描述 + 材质光影描述。**请在开头直接写明：一张正方形构图的...**)

 5. 效果示例 (Few-Shot Examples)

**User Input:**
(一张竖长的手机海报，顶部写着"双11特惠"，中间是一个模特穿着红色羽绒服，下半部分被红色的半透明渐变遮挡以显示促销文字)

**Assistant Output:**


一张正方形构图的时尚人像摄影。画面正中央是一位身穿红色羽绒服的模特，面容清晰精致，羽绒服材质蓬松且具有真实的光泽感。采用半身特写构图，确保人物主体在正方形画幅中完整且突出。背景处理为纯净、柔和的浅灰色影棚背景，光影立体自然，去除了一切商业海报的装饰效果，画质清晰锐利，呈现出高端杂志大片的质感。

---

**User Input:**
(一张横幅Banner，左边是产品——一瓶面霜，右边全是文字介绍，背景有很多光点特效)

**Assistant Output:**

 
一张正方形构图的产品静物摄影。画面中心放置着一瓶高质感的面霜，瓶身材质通透，标签清晰。构图聚焦于产品本身，移除了周围多余的空间。背景是干净整洁的大理石台面，光线柔和明亮，没有任何人工合成的光点特效或文字干扰，呈现出纯粹、极简的护肤品展示效果，4k超高清分辨率。
"""
    
    max_retries = 2  # 最大重试次数
    
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                log_message(f"正在处理图片: {os.path.basename(image_path)}")
            else:
                log_message(f"重试处理图片 ({attempt + 1}/{max_retries}): {os.path.basename(image_path)}")
                time.sleep(2)  # 重试前等待2秒
            
            result = chat_with_ai_api(
                api_key=api_key,
                base_url=base_url,
                image_path=image_path,
                prompt=prompt_template
            )
            log_message("提示词生成成功")
            return result.strip()
            
        except Exception as e:
            log_message(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt == max_retries - 1:
                log_message(f"所有重试都失败，跳过此图片: {os.path.basename(image_path)}")
                return None  # 返回None表示跳过
    
    return None  # 理论上不会到达这里


def create_config_item(image_path, prompt, output_dir, model, wait_time):
    """
    创建单个配置项
    Args:
        image_path (str): 图片路径
        prompt (str): 提示词
        output_dir (str): 输出目录
        model (str): 模型选择
        wait_time (str): 等待时间
    Returns:
        dict: 配置项
    """
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    
    return {
        "banana_prompt": prompt,
        "banana_ref_img1": image_path,
        "banana_ref_img2":"" ,
        "banana_model": model,
        "banana_wait_time": wait_time,
        "banana_link_or_right": "",
        "banana_img_dir": output_dir,
        "banana_save_name": image_name
    }


def clean_prompt_text(prompt):
    """
    清理提示词文本，删除英文字符和逗号句号之外的符号
    Args:
        prompt (str): 原始提示词
    Returns:
        str: 清理后的提示词
    """
    import re
    # 保留中文字符、数字、逗号、句号和空格，删除其他所有字符
    cleaned = re.sub(r'[a-zA-Z]', '', prompt)  # 删除英文字母
    cleaned = re.sub(r'[^一-龥、。，．0-9\\s]', '', cleaned)  # 保留中文、逗号、句号、数字和空格
    return cleaned.strip()


def rename_processed_files(directory):
    """
    重命名已处理的文件
    将文件名末尾为"HB_1.jpg"或"HB_2.jpg"的文件重命名为"ST.jpg"
    Args:
        directory (str): 要处理的目录路径
    """
    if not os.path.exists(directory):
        log_message(f"目录不存在: {directory}")
        return
    
    renamed_count = 0
    
    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        # 只处理文件，不处理目录
        if not os.path.isfile(file_path):
            continue
        
        # 检查文件名是否以HB_1.jpg或HB_2.jpg结尾
        if filename.endswith('HB_1.jpg'):
            # 将HB_1.jpg替换为ST.jpg
            new_filename = filename.replace('HB_1.jpg', 'ST.jpg')
            new_file_path = os.path.join(directory, new_filename)
        elif filename.endswith('HB_2.jpg'):
            # 将HB_2.jpg替换为ST.jpg
            new_filename = filename.replace('HB_2.jpg', 'ST.jpg')
            new_file_path = os.path.join(directory, new_filename)
        else:
            continue
        
        # 检查新文件名是否已存在
        if os.path.exists(new_file_path):
            log_message(f"警告: 文件已存在，跳过重命名: {new_filename}")
            continue
        
        try:
            os.rename(file_path, new_file_path)
            log_message(f"重命名成功: {filename} -> {new_filename}")
            renamed_count += 1
        except Exception as e:
            log_message(f"重命名失败: {filename} -> {e}")
    
    log_message(f"重命名完成，共处理 {renamed_count} 个文件")


def clean_config_prompts(config_path):
    """
    清理配置文件中所有banana_prompt的值
    Args:
        config_path (str): 配置文件路径
    """
    try:
        # 读取配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 清理主提示词
        if 'banana_prompt' in config_data:
            original_prompt = config_data['banana_prompt']
            config_data['banana_prompt'] = clean_prompt_text(original_prompt)
            log_message(f"已清理主提示词")
        
        # 清理configs数组中的提示词
        if 'configs' in config_data and isinstance(config_data['configs'], list):
            cleaned_count = 0
            for item in config_data['configs']:
                if 'banana_prompt' in item:
                    original = item['banana_prompt']
                    item['banana_prompt'] = clean_prompt_text(original)
                    cleaned_count += 1
            log_message(f"已清理 {cleaned_count} 个配置项的提示词")
        
        # 保存修改后的配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        log_message("配置文件提示词清理完成")
        
    except Exception as e:
        log_message(f"清理配置文件提示词时出错: {e}")


def load_existing_configs(config_path):
    """
    加载现有的配置文件
    Args:
        config_path (str): 配置文件路径
    Returns:
        dict: 现有的配置数据
    """
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"读取配置文件失败: {e}")
            return {}
    return {}


def clean_old_config_items(config_path, processed_directories):
    """
    清理配置文件中已处理项目的旧条目
    Args:
        config_path (str): 配置文件路径
        processed_directories (set): 已处理的目录集合
    """
    try:
        # 加载现有配置
        config_data = load_existing_configs(config_path)
        
        if 'configs' not in config_data or not isinstance(config_data['configs'], list):
            return
        
        # 过滤掉已处理目录的配置项
        original_count = len(config_data['configs'])
        filtered_configs = []
        
        for item in config_data['configs']:
            img_path = item.get('banana_ref_img1', '')
            if img_path:
                img_dir = os.path.dirname(img_path)
                # 如果该目录不在已处理目录中，则保留
                if img_dir not in processed_directories:
                    filtered_configs.append(item)
        
        # 更新配置
        config_data['configs'] = filtered_configs
        removed_count = original_count - len(filtered_configs)
        
        # 保存修改后的配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        if removed_count > 0:
            log_message(f"已从配置文件中清理 {removed_count} 个旧项目条目")
        
    except Exception as e:
        log_message(f"清理配置文件旧项目时出错: {e}")


def save_config_item(image_path, prompt, config_path, input_directory, headless, model, wait_time):
    """
    保存单个配置项到配置文件
    Args:
        image_path (str): 图片路径
        prompt (str): 提示词
        config_path (str): 配置文件路径
        input_directory (str): 输入目录路径
        headless (bool): 浏览器模式
        model (str): 模型选择
        wait_time (str): 等待时间
    """
    # 加载现有配置
    config_data = load_existing_configs(config_path)
    
    # 如果是第一次保存，初始化配置结构
    if not config_data:
        config_data = {
            "headless": headless,
            "last_input_folder": input_directory,
            "banana_prompt": prompt,
            "configs": []
        }
    
    # 获取图片所在目录作为输出目录
    output_dir = os.path.dirname(image_path)
    
    # 创建新的配置项
    new_item = create_config_item(image_path, prompt, output_dir, model, wait_time)
    
    # 检查是否已存在相同的配置项（避免重复）
    existing_paths = [item.get('banana_ref_img1', '') for item in config_data.get('configs', [])]
    if image_path not in existing_paths:
        config_data['configs'].append(new_item)
        
        # 保存配置文件
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            log_message(f"已保存配置项: {os.path.basename(image_path)} (总计 {len(config_data['configs'])} 个任务)")
        except Exception as e:
            log_message(f"保存配置文件失败: {e}")
    else:
        log_message(f"配置项已存在，跳过: {os.path.basename(image_path)}")


def get_user_parameters(folder_path, last_prompt):
    """
    交互式获取用户参数
    Args:
        folder_path (str): 当前选定的输入文件夹
        last_prompt (str): 上次使用的提示词
    Returns:
        tuple: (headless, model, wait_time, output_folder, prompt)
    """
    print("\n默认模式参数:")
    print("- 浏览器模式: 无头模式 (headless)")
    print(f"- 模型选择: {DEFAULT_MODEL}")
    print(f"- 等待时间: {DEFAULT_WAIT_TIME}秒")
    print(f"- 输出文件夹: {get_output_folder_path(folder_path)}")
    print(f"- 提示词: {last_prompt}")
    print()
    
    mode_choice = input("请选择模式：1-默认模式，2-自定义模式: ").strip()
    
    # 默认值初始化
    headless = True
    model = DEFAULT_MODEL
    wait_time = DEFAULT_WAIT_TIME
    output_folder = get_output_folder_path(folder_path)
    prompt = last_prompt
    
    if mode_choice == "2":
        # 自定义模式逻辑
        print(">>> 进入自定义模式")
        
        # 浏览器模式 (0=无头, 1=有头)
        while True:
            h_input = input("请选择浏览器模式 (0-无头, 1-有头): ").strip()
            if h_input in ["0", "1"]:
                # 0 -> True (无头), 1 -> False (有头)
                headless = not bool(int(h_input))
                break
            print("输入无效，请输入 0 或 1")
        
        # 模型选择
        while True:
            m_input = input("请选择模型 (1 或 2): ").strip()
            if m_input in ["1", "2"]:
                model = m_input
                break
            print("输入无效，请输入 1 或 2")
        
        # 等待时间
        while True:
            w_input = input("请输入等待时间 (秒): ").strip()
            if w_input.isdigit():
                wait_time = w_input
                break
            print("输入无效，请输入数字")
        
        # 输出文件夹
        o_input = input(f"请输入输出文件夹路径 (回车默认: {output_folder}): ").strip()
        if o_input:
            output_folder = o_input
            os.makedirs(output_folder, exist_ok=True)
        
        # 获取文件夹中的第一张图片，通过API获取提示词作为默认值
        first_image_path = None
        for ext in SUPPORTED_EXTENSIONS:
            image_list = glob.glob(os.path.join(folder_path, ext), recursive=False)
            if image_list:
                first_image_path = image_list[0]
                break
        
        if first_image_path:
            # 通过API获取建议的提示词
            log_message(f"正在分析图片: {first_image_path}")
            suggested_prompt = generate_prompt_for_image(first_image_path)
            log_message(f"API返回的提示词: {suggested_prompt[:50]}...")
            # 提示词输入，使用API生成的提示词作为默认值
            p_input = input(f"请输入提示词 (回车默认: {suggested_prompt}): ").strip()
            if p_input:
                prompt = p_input
            else:
                prompt = suggested_prompt
        else:
            # 如果没有找到图片，使用上次的提示词
            p_input = input(f"请输入提示词 (回车默认: {prompt}): ").strip()
            if p_input:
                prompt = p_input
        
        log_message(f"自定义配置: {'无头' if headless else '有头'} | 模型{model} | 等待{wait_time}s")
    else:
        log_message("使用默认配置")
    
    return headless, model, wait_time, output_folder, prompt


def batch_process_images():
    """
    主函数：批量处理图片
    """
    print("=" * 50)
    print("批量图片处理工具")
    print("=" * 50)
    
    # 1. 加载历史配置
    last_folder, last_prompt = load_previous_config()
    
    # 2. 获取输入目录
    default_folder = last_folder if last_folder else ""
    prompt_text = f"请输入要处理的图片目录路径 (留空使用上次: {default_folder}): " if default_folder else "请输入要处理的图片目录路径: "
    # 尝试从剪贴板获取路径
    clipboard_path = None
    try:
        import pyperclip
        clipboard_content = pyperclip.paste().strip()
        if clipboard_content and os.path.isdir(clipboard_content):
            clipboard_path = clipboard_content
            print(f"[检测到剪贴板中的路径: {clipboard_path}]")
    except:
        pass

    input_directory = input(prompt_text).strip()

    # 如果用户没有输入且剪贴板中有有效路径，使用剪贴板路径
    if not input_directory and clipboard_path:
        input_directory = clipboard_path
        log_message(f"使用剪贴板中的路径: {input_directory}")
    
    if not input_directory:
        input_directory = default_folder
    
    if not input_directory:
        log_message("错误: 目录路径不能为空")
        return
    
    try:
        # 3. 校验路径
        if not os.path.isdir(input_directory):
            log_message(f"错误: 路径 '{input_directory}' 无效或不存在")
            return
        
        log_message(f"当前工作目录: {input_directory}")
        
        # 4. 选择执行模式
        print("\n执行模式选择:")
        print("1. 清空所有配置，重新开始处理")
        print("2. 跳过已处理项目，仅处理新项目")
        
        while True:
            mode_choice = input("请选择执行模式 (1 或 2): ").strip()
            if mode_choice in ["1", "2"]:
                execution_mode = int(mode_choice)
                break
            print("输入无效，请输入 1 或 2")
        
        # 5. 获取运行参数 (交互式)
        headless, model, wait_time, output_folder, prompt = get_user_parameters(input_directory, last_prompt)
        
        # 6. 根据模式获取待处理图片文件
        image_files = []
        
        if execution_mode == 1:
            # 模式1: 清空所有配置，重新开始处理
            # 清空ach配置文件
            config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
            if os.path.exists(config_path):
                os.remove(config_path)
                log_message("已清空ach配置文件")
            
            # 遍历获取所有图片文件
            image_files = get_image_files(input_directory)
            
        elif execution_mode == 2:
            # 模式2: 跳过已处理项目，仅处理新项目
            # 1. 清除ach目录下的ach_config文件内容
            config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
            if os.path.exists(config_path):
                os.remove(config_path)
                log_message("已清空ach配置文件")
            
            # 2. 读取savexiumi_config.json文件
            savexiumi_config_path = os.path.join(input_directory, "savexiumi_config.json")
            if not os.path.exists(savexiumi_config_path):
                log_message(f"错误: 找不到savexiumi_config.json文件: {savexiumi_config_path}")
                return
            
            try:
                with open(savexiumi_config_path, 'r', encoding='utf-8') as f:
                    savexiumi_config = json.load(f)
            except Exception as e:
                log_message(f"读取savexiumi_config.json失败: {e}")
                return
            
            items = savexiumi_config.get("items", [])
            if not items:
                log_message("savexiumi_config.json中没有items数据")
                return
            
            log_message(f"从savexiumi_config.json读取到 {len(items)} 个items")
            
            # 3. 遍历items，检查首图路径对应的ST.jpg是否存在
            skipped_count = 0
            error_count = 0
            
            for item in items:
                try:
                    # 获取首图路径
                    first_image_relative = item.get("首图路径", "")
                    poster_relative = item.get("海报路径", "")
                    
                    if not first_image_relative or not poster_relative:
                        log_message(f"跳过item: 首图路径或海报路径为空")
                        skipped_count += 1
                        continue
                    
                    # 构建完整路径
                    first_image_path = os.path.join(input_directory, first_image_relative)
                    poster_path = os.path.join(input_directory, poster_relative)
                    
                    # 检查ST.jpg是否存在
                    if os.path.exists(first_image_path):
                        # ST.jpg存在，说明已处理过，跳过
                        log_message(f"跳过已处理项目: {os.path.basename(first_image_relative)}")
                        skipped_count += 1
                    else:
                        # ST.jpg不存在，需要处理，获取对应的HB.jpg
                        if os.path.exists(poster_path):
                            image_files.append(poster_path)
                            log_message(f"待处理: {os.path.basename(poster_path)}")
                        else:
                            log_message(f"错误: 海报文件不存在: {poster_relative}")
                            error_count += 1
                            
                except Exception as e:
                    # 4. 遇到错误，打印出来，继续处理下一个item
                    log_message(f"处理item时出错: {e}")
                    error_count += 1
                    continue
            
            log_message(f"过滤完成: 跳过 {skipped_count} 个已处理项目，找到 {len(image_files)} 个待处理项目，错误 {error_count} 个")
        
        if not image_files:
            log_message("没有需要处理的项目")
            return
        
        log_message(f"开始处理 {len(image_files)} 张图片...")
        
        # 7. 为每张图片生成提示词并实时保存配置
        config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)
        processed_count = 0  # 记录成功处理的图片数量
        
        for i, image_path in enumerate(image_files, 1):
            log_message(f"正在处理第 {i}/{len(image_files)} 张图片...")
            prompt_text = generate_prompt_for_image(image_path)
            
            if prompt_text is not None:  # 只有成功生成提示词才保存配置
                save_config_item(image_path, prompt_text, config_path, input_directory, headless, model, wait_time)
                processed_count += 1
                log_message(f"提示词: {prompt_text[:50]}...")
                print("-" * 30)
            else:
                log_message(f"跳过图片: {os.path.basename(image_path)}")
                print("-" * 30)
        
        # 检查是否有成功处理的图片
        if processed_count == 0:
            log_message("没有成功处理任何图片，程序结束")
            return
        
        log_message(f"总共成功处理 {processed_count} 张图片")
        log_message("配置文件已实时更新完成!")
        print("=" * 50)
        
        # 初始化已处理目录集合
        processed_directories = set()
        
        # 如果是模式2，清理配置文件中的旧项目
        if execution_mode == 2 and processed_directories:
            log_message("正在清理配置文件中的旧项目条目...")
            clean_old_config_items(config_path, processed_directories)
        
        # 6.5 清理配置文件中的提示词（删除英文和特殊符号）
        clean_config_prompts(config_path)
        
        # 7. 执行 ach.py，使用ach目录下的配置文件
        log_message("开始执行 ach.py...")
        try:
            # 使用统一的配置文件路径
            ach_main(config_path=CONFIG_FILENAME)
            log_message("所有任务执行完成!")
        except Exception as e:
            log_message(f"执行 ach.py 时出错: {e}")
            return
        
        # 8. 重命名处理后的文件
        log_message("开始重命名处理后的文件...")
        try:
            rename_processed_files(input_directory)
            log_message("文件重命名完成!")
        except Exception as e:
            log_message(f"文件重命名时出错: {e}")
            
    except Exception as e:
        log_message(f"程序执行出错: {e}")


if __name__ == "__main__":
    try:
        batch_process_images()
    except KeyboardInterrupt:
        log_message("用户中断操作")
    except Exception as e:
        log_message(f"未预期的错误: {e}")
    finally:
        input("按 Enter 键退出...")