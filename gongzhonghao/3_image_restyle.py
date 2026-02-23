"""
=============================================================
3_image_restyle.py 图片风格重构工具（完全独立版本）
=============================================================

功能概述:
--------
图片风格重构工具（批量处理版）。通过AI分析图片生成改图提示词，然后调用Banana API
生成新的图片（保持背景元素、重构人物特征）。支持批量文件夹处理，多图并发执行。

特点:
------
- 完全独立运行，无需 common 文件夹
- 自动生成配置文件（如不存在）
- 内置 API4 图像分析功能
- 支持批量处理

使用流程:
--------
1. 直接运行文件: python 3_image_restyle.py
2. 输入文件夹路径
3. 等待API并发处理完成
4. 查看output目录下的生成结果
"""

import os
import sys
import requests
import base64
from io import BytesIO
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# =============================================================================
# API4 图像分析配置（内联）
# =============================================================================
DEFAULT_API_KEY = "sk-Jsqk6zfznVkeMsjLEqNLtv4eWFs3bvyLXfn3IzWhSsLg7wSK"
DEFAULT_BASE_URL = "https://one.api4gpt.com/v1"
DEFAULT_MODEL = "gemini-3-pro-preview"

# ========== Banana API 配置 ==========
BANANA_API_KEY = "sk-RM8xwiFSD9UlpNjPO9ZGxvWy530T9xpsRbS07s4RNfBhXzHg"
BANANA_API_URL = "https://one.api4gpt.com/v1/images/edits"
BANANA_MODEL = "nano-banana"

# ========== 并发配置 ==========
MAX_WORKERS = 10

# ========== 默认输入文件夹配置 ==========
DEFAULT_INPUT_FOLDER = r"C:\Users\Administrator\Desktop\公众号文章\img"

# ========== 输出文件夹配置 ==========
OUTPUT_FOLDER = r"C:\Users\Administrator\Desktop\公众号文章\imgoutput"

# ========== 改图提示词模板 ==========
RESTYLE_PROMPT_TEMPLATE = """  1. 核心定位
      你是一名精通"即梦"与"Banana/Stable Diffusion"平台的提示词架构师。你专注于通过提示词实现"背景元素锁定重绘"，即在保
    持原图背景元素、结构、物体种类完全不变的前提下，仅对人物特征、镜头角度、天气细节进行精准替换
      。注意：背景应随镜头角度变化而呈现相应的视角改变。
      2. 任务目标

  分析用户上传的参考图，生成一段高度结构化的中文提示词。目标是：锁定背景所有元素（除云彩造型外），保持原图的主体人物
    位置与比例，但执行主体人物形象的彻底重构（脸、发型、配饰）以及环境细节的特定修改（去水印、换云彩造
      型、调整视角）。云彩改造时必须严格保持原图的天气状况（晴天/阴天/傍晚等），仅替换云彩的形态造型。
      3. 核心行为准则
      🔒 锁定与保持 (STRICT BACKGROUND ELEMENT LOCK)
      1.
  背景元素锁定：必须详细描述并强调原图的背景元素（如：特定的圆圈、窗户、家具、街道布局），确保新图背景中的物体和结
    构与原图一致。同时，背景的视角必须跟随镜头调整指令（如low angle、pan
      left）呈现相应的透视变化。即：锁定风景样式不变，但视角可随镜头调整而变化。
      2. 构图与位移对齐：主体人物必须保持在原图中的同一坐标、同一大小、同一比例。
      3. 景别一致：严格遵循原图取景（特写/半身/全身），禁止改变景深。
      4. 光影继承：继承原图的核心光源方向和色温。
      ⚠️ 人物识别边界规则 (PERSON IDENTIFICATION BOUNDARY)
      1. 主体人物判定标准：仅将占据画面较大比例、处于视觉焦点位置、呈现清晰可辨的人体特征（包括但不限于：特写、半身像、
  全身像、坐姿、躺姿等各种构图形式）的真实人类识别为"主体人物"，并对其执行以下"变量重塑"规则。注意：半身像、大头照、局部
  特写等非全身构图同样属于主体人物，只要该人物处于视觉焦点且具有可辨识的面部或身体特征。
      2. 类人静物排除规则：严禁将以下对象识别为"人物"或"主体人物"，这些必须归类为"背景元素"并保持不变：
        ○ 佛像、菩萨像、神像、宗教塑像（无论材质：铜像、石雕、木雕、泥塑等）
        ○ 雕塑、雕像、人形艺术品（如博物馆展品、城市雕塑、石膏像）
        ○ 人体模型、模特人偶、服装展示架
        ○ 玩偶、手办、人形玩具
        ○ 壁画、画像、海报中的人物形象
        ○ 阴影中的人形轮廓（非水面倒影）
        ○ 任何非真实、非三维存在的类人形态
      3. 非主体小人物排除规则：以下人物必须视为"背景元素"，严禁执行任何"变量重塑"操作，仅保持原样：
        ○ 占画面比例极小（小于画面高度的1/5）的远处人物
        ○ 背景中的路人、群演、模糊人影
        ○ 不处于视觉焦点位置的次要人物
        ○ 仅露出局部（如背影、侧影、四肢）且不构成完整形象的人物
        ○ 画面中数量超过3人的群体中的非主要人物
      4.
  处理原则：当画面中存在上述"类人静物"或"非主体小人物"时，提示词中必须明确表述"保持原图中的[具体描述]不变，作为背景
    元素处理"，严禁对其应用任何人物重塑指令。
      5. 倒影同步规则：水面倒影、镜面反射中的人物影像不属于"类人静物"，而是主体人物的附属影像。处理规则如下：
        ○
  若倒影/镜中像对应的是"主体人物"，则该倒影/镜中像必须与主体人物同步变化（面孔、发型、服饰等重塑效果同步反映在倒影中）
        ○ 若倒影/镜中像对应的是"非主体小人物"，则该倒影/镜中像作为背景元素保持原样
        ○ 提示词中需明确表述："水面倒影/镜面反射同步呈现重塑后的人物形象"
      🔄 变量重塑 (VARIABLE CHANGE)
      【以下规则仅适用于经上述"人物识别边界规则"判定为"主体人物"的对象】
      1. 面孔彻底重塑：生成一张全新的、高颜值的中国面孔，严禁保留原图五官特征
      2. 发型完全改变：根据原图长度进行逻辑反转（例：长发变短发/盘发；直发变卷发）。
      3. 眼镜逻辑反转：
        ○ 原图有眼镜 → 提示词明确要求"不戴眼镜，露出完整双眼"。
        ○ 原图无眼镜 → 提示词必须增加"佩戴精致的[具体材质]眼镜"。
      4. 服饰同风替换：更换衣服颜色或材质细节，但必须保持穿搭风格（如：同为西装但换颜色）。
      5. 云彩造型置换（天气锁定）：
        ○
  若原图有云，必须描述一种造型截然不同的云（如：鱼鳞云→棉花糖云、层云→卷云、絮状云→条状云），但必须保持原图的天气
    状况和光线氛围（晴天仍是晴天、阴天仍是阴天、正午仍是正午，严禁将晴天改为夕阳/晚霞等不同天气
      时段）。
        ○ 若原图无云则不添加。
        ○ 核心原则：只改云的形态造型，不改天气状况和整体光线氛围。
      📐 视角与环境修正 (SPECIFIC MODS)
      1. 镜头微调指令：在提示词中必须显式包含 pan camera slightly left (镜头向左微调) 和 low angle
    (低角度拍摄)。背景元素应随此视角变化呈现相应的透视改变，但背景元素的种类、样式、布局保持与原图一致。
      2. 无水印指令：提示词中严禁出现任何关于水印的描述，确保画面纯净，不包含原图水印。
      4. 视觉分析与工作流 (SOP)
      ● Step 1 视觉解码：分析背景中的固定元素（如圆圈、建筑、植物位置）、主体人物姿势、眼镜状态、云彩形态、天气状况、水
  面/镜面倒影情况。
      ● Step 1.5
  人物识别判定：执行"人物识别边界规则"，区分"主体人物"与"类人静物/非主体小人物"。若画面中存在佛像、雕塑等类
    人静物，明确标记为背景元素；若存在非主体小人物，标记为背景路人并保持原样；若存在主体人物的水面/镜面倒影，标记为"同步
  处理对象"。
      ● Step 2
  逻辑执行：仅对"主体人物"执行"发型、面孔、服饰、眼镜、云彩造型"的差异化方案，同时锁定天气状况。类人静物与非
    主体小人物跳过此步骤。主体人物的倒影/镜中像同步执行重塑效果。
      ● Step 3
  提示词封装：将锁定部分与改变部分融合，明确指出背景样式锁定（包含类人静物和非主体小人物）、视角随新镜头变化
    、天气状况锁定、倒影同步变化。
      5. 输出格式规范
        请直接输出一段完整的中文提示词：
        [画质与视角描述: 8k, low angle, pan camera slightly left] + [背景元素锁定描述:
    复刻原图背景中的xx圆圈/xx环境元素/xx类人静物（如有），样式保持不变，视角随镜头调整而呈现新透视] + [人物定位:
    保持原图主体人物位置与比例] +
      [全新的中国面孔] + [新的发型] + [眼镜反转状态] + [新的服饰描述] + [原图姿势描述] +
    [云彩造型差异化描述（保持原天气状况）] + [倒影同步描述（如有水面/镜面倒影）] + [无水印声明]
      6. 示例
        用户输入：(一张背景有个发光圆环，半身女性，黑长直，没戴眼镜，有白云，晴天，左下角有水印)
        你的回复：
        8k分辨率，超高清，大师级摄影。low angle，pan camera slightly

  left。背景保留原图的发光圆环装饰及墙面纹理等元素，样式与原图完全一致，视角随低角度和左移镜头呈现新的透视感。主体人物
    位置与构图与原图完全一致。一位年轻漂亮的中国女性，全新的精致面孔。复古波浪卷发（替换直发）。佩

  戴时尚的金丝边眼镜（反转无眼镜状态）。身穿浅灰色商务西装（替换原色）。姿势保持双手自然下垂，站姿。保持晴天氛围，将原
    白云替换为轻盈的絮状卷云（仅改云彩造型，天气不变）。画面纯净，无水印。
        用户输入：(一张寺庙场景，前景有一位女性游客，背景有一尊金色佛像，远处有几位小游客)
        你的回复：
        8k分辨率，超高清，大师级摄影。low angle，pan camera slightly

 left。背景保留原图的寺庙建筑、金色佛像（作为背景元素保持原样，不做人物处理）及远处的小游客（作为背景路人保持原样），

  样式与原图完全一致，视角随低角度和左移镜头呈现新的透视感。主体人物（前景女性游客）位置与构图与原图完全一致。一位年轻漂

  亮的中国女性，全新的精致面孔。卷发造型（替换直发）。不戴眼镜，露出完整双眼。身穿淡蓝色休闲外套。姿势保持原样。保持原图
    天气氛围。画面纯净，无水印。
        用户输入：(一张湖边场景，一位女性站在湖边，湖面有清晰的人物倒影，晴天)
        你的回复：
        8k分辨率，超高清，大师级摄影。low angle，pan camera slightly
      left。背景保留原图的湖面、远处山景等环境元素，样式与原图完全一致，视角随低角度和左移镜头呈现新的透视感。主体人物位
    置与构图与原图完全一致。一位年轻漂亮的中国女性，全新的精致面孔。波浪卷发造型（替换直发）。佩戴时尚的银丝边眼镜（反转无
    眼镜状态）。身穿米白色风衣。姿势保持原样。保持晴天氛围。湖面倒影同步呈现重塑后的人物形象（面孔、发型、服饰与主体人物一
    致）。画面纯净，无水印。
      7. 交互限制
      ● 只输出中文提示词，不解释过程。
      ● 必须确保"背景元素锁定"的描述权重极高，明确指代背景中的核心视觉物，同时保证视角可随镜头调整而变化。
      ● 背景不是静态复制，应随镜头角度变化而呈现不同的透视效果，但背景元素的样式必须与原图保持一致。
      ● 云彩改造时，严禁改变原图的天气状况和光线氛围，只允许修改云彩的造型形态。
      ● 严禁将佛像、雕塑等类人静物当作人物处理，必须将其锁定为背景元素。
      ● 严禁对非主体小人物执行人物重塑操作，必须将其作为背景元素保持原样。
      ● 水面倒影、镜面反射中的人物影像必须与主体人物同步变化，严禁倒影与人物不一致。"""

# 支持的图片扩展名
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', 'webp')
DEFAULT_RETRY_TIMES = 3


# =============================================================================
# API4 图像分析函数（内联）
# =============================================================================

def chat_with_ai_api(image_path, prompt, api_key=DEFAULT_API_KEY, base_url=DEFAULT_BASE_URL, model=DEFAULT_MODEL):
    """
    与聊天AI API交互（支持图片）
    """
    # 检查输入有效性
    if not api_key or not isinstance(api_key, str):
        raise ValueError("API密钥不能为空且必须是字符串类型")
    if not base_url or not isinstance(base_url, str):
        raise ValueError("API基础URL不能为空且必须是字符串类型")
    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词不能为空且必须是字符串类型")

    def _encode_image_to_base64(image_path):
        """将图片文件编码为base64格式"""
        try:
            with open(image_path, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_string
        except FileNotFoundError:
            raise FileNotFoundError(f"图片文件未找到: {image_path}")
        except Exception as e:
            raise Exception(f"读取图片文件失败: {str(e)}")

    def _send_chat_request(api_key, url, payload):
        """发送聊天API请求"""
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


# =============================================================================
# 主程序函数
# =============================================================================

def retry_on_failure(max_retries: int = DEFAULT_RETRY_TIMES, delay: float = 1.0):
    """API调用重试装饰器"""
    import time
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"第 {attempt + 1} 次尝试失败: {str(e)}，{delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        print(f"第 {attempt + 1} 次尝试失败，已达最大重试次数")
            raise last_exception

        return wrapper

    return decorator


def get_folder_path() -> str:
    """获取文件夹路径"""
    print("\n========== 图片风格重构工具（批量处理）==========")
    print(f"支持的图片格式: {', '.join(SUPPORTED_EXTENSIONS)}")
    print(f"默认文件夹: {DEFAULT_INPUT_FOLDER}")
    print("（直接回车使用默认文件夹）")
    print("==============================================\n")

    while True:
        try:
            user_input = input("请输入文件夹路径: ").strip()

            if user_input.startswith('"') and user_input.endswith('"'):
                user_input = user_input[1:-1]
            if user_input.startswith("'") and user_input.endswith("'"):
                user_input = user_input[1:-1]

            if not user_input:
                folder_path = DEFAULT_INPUT_FOLDER
                print(f"\n使用默认文件夹: {folder_path}\n")
            else:
                folder_path = user_input

            if not os.path.isdir(folder_path):
                print(f"文件夹不存在: {folder_path}，请重新输入！\n")
                continue

            print(f"\n已选择文件夹: {folder_path}\n")
            return folder_path

        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit(0)


def collect_images_from_folder(folder_path: str) -> list:
    """收集文件夹中的图片"""
    image_paths = []
    for filename in os.listdir(folder_path):
        _, ext = os.path.splitext(filename)
        if ext.lower() in SUPPORTED_EXTENSIONS:
            full_path = os.path.join(folder_path, filename)
            if os.path.isfile(full_path):
                image_paths.append(full_path)
    return sorted(image_paths)


def filter_unprocessed_images(image_paths: list) -> list:
    """过滤已处理的图片"""
    unprocessed_paths = []
    skipped_count = 0

    for image_path in image_paths:
        original_filename = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = OUTPUT_FOLDER
        output_file = os.path.join(output_dir, f"{original_filename}.jpg")

        if os.path.exists(output_file):
            skipped_count += 1
            print(f"跳过已处理: {os.path.basename(image_path)}")
        else:
            unprocessed_paths.append(image_path)

    if skipped_count > 0:
        print(f"\n共跳过 {skipped_count} 张已处理的图片\n")

    return unprocessed_paths


def process_single_image(image_path: str, index: int, total: int) -> dict:
    """处理单张图片完整流程"""
    result = {
        'success': False,
        'image_path': image_path,
        'output_path': None,
        'error': None
    }

    filename = os.path.basename(image_path)
    print(f"[{index}/{total}] 正在处理: {filename}")

    try:
        prompt = get_restyle_prompt(image_path)
        print(f"[{index}/{total}] 提示词生成完成: {filename}")

        image_url = call_banana_api(image_path, prompt)
        print(f"[{index}/{total}] API调用完成: {filename}")

        output_path = download_and_save_image(image_url, image_path)
        print(f"[{index}/{total}] 保存完成: {filename}")

        result['success'] = True
        result['output_path'] = output_path

    except Exception as e:
        result['error'] = str(e)
        print(f"[{index}/{total}] 处理失败 ({filename}): {str(e)}")

    return result


def get_restyle_prompt(image_path: str) -> str:
    """获取改图提示词"""
    print("正在分析图片，生成改图提示词...")

    @retry_on_failure(max_retries=DEFAULT_RETRY_TIMES)
    def call_api():
        result = chat_with_ai_api(
            image_path=image_path,
            prompt=RESTYLE_PROMPT_TEMPLATE
        )
        return result

    try:
        result = call_api()
        print("改图提示词生成成功！\n")
        return result
    except Exception as e:
        raise Exception(f"生成改图提示词失败: {str(e)}")


def call_banana_api(image_path: str, prompt: str) -> str:
    """调用Banana API处理图片"""
    print("正在调用Banana API处理图片...")

    headers = {
        'Authorization': f'Bearer {BANANA_API_KEY}'
    }

    @retry_on_failure(max_retries=DEFAULT_RETRY_TIMES)
    def call_api():
        filename = os.path.basename(image_path)
        with open(image_path, 'rb') as f:
            files = {
                'image': (filename, f, 'image/jpeg')
            }
            data = {
                'prompt': prompt,
                'n': '1',
                'model': BANANA_MODEL
            }

            response = requests.post(
                BANANA_API_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()

            if 'data' in result and len(result['data']) > 0:
                image_url = result['data'][0]['url']
                print("Banana API处理完成！\n")
                return image_url
            else:
                raise Exception(f"API返回格式异常: {result}")

    try:
        return call_api()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Banana API请求失败: {str(e)}")


def download_and_save_image(image_url: str, original_path: str) -> str:
    """下载并保存图片"""
    print("正在下载并保存图片...")

    # 创建output目录
    output_dir = OUTPUT_FOLDER
    os.makedirs(output_dir, exist_ok=True)

    # 获取原文件名（不含扩展名）
    original_filename = os.path.splitext(os.path.basename(original_path))[0]

    # 输出文件路径（jpg格式）
    output_path = os.path.join(output_dir, f"{original_filename}.jpg")

    try:
        # 下载图片
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()

        # 使用PIL打开图片并转换为JPG
        img = Image.open(BytesIO(response.content))

        # 如果是RGBA模式，转换为RGB（JPG不支持透明通道）
        if img.mode == 'RGBA':
            # 创建白色背景
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # 使用alpha通道作为mask
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 保存为JPG
        img.save(output_path, 'JPEG', quality=95)

        print(f"图片已保存到: {output_path}\n")
        return output_path

    except Exception as e:
        raise Exception(f"保存图片失败: {str(e)}")


def main():
    """主流程"""
    print("===== 图片风格重构工具（批量处理）=====\n")

    try:
        folder_path = get_folder_path()
        image_paths = collect_images_from_folder(folder_path)

        if not image_paths:
            print(f"文件夹中未找到支持的图片文件！")
            print(f"支持的格式: {', '.join(SUPPORTED_EXTENSIONS)}")
            sys.exit(1)

        image_paths = filter_unprocessed_images(image_paths)

        if not image_paths:
            print("所有图片已处理完成，无需重复处理！")
            sys.exit(0)

        total = len(image_paths)
        print(f"剩余 {total} 张图片待处理")
        print(f"并发数: {MAX_WORKERS}")
        print("=" * 50 + "\n")

        results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_image = {
                executor.submit(process_single_image, path, idx + 1, total): path
                for idx, path in enumerate(image_paths)
            }

            for future in as_completed(future_to_image):
                result = future.result()
                results.append(result)

        success_count = sum(1 for r in results if r['success'])
        fail_count = total - success_count

        print("\n" + "=" * 50)
        print("处理完成！汇总报告")
        print(f"总计: {total} 张")
        print(f"成功: {success_count} 张")
        print(f"失败: {fail_count} 张")

        if fail_count > 0:
            print("\n失败列表:")
            for r in results:
                if not r['success']:
                    print(f"  - {os.path.basename(r['image_path'])}: {r['error']}")

        print("=" * 50)

    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
