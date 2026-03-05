"""
=============================================================
batch_txt2txt.py 使用说明（完全独立版本）
=============================================================

功能概述:
--------
批量并发调用API4文本生成API，通过交互方式让用户选择6篇旅游文章，
再输入1个机场话题，然后并发生成7篇文章。

特点:
------
- 完全独立运行，无需 common 文件夹
- 自动生成配置文件（如不存在）
- 内置 API4 文本生成功能

使用流程:
--------
1. 直接运行文件: python 1_lvyou_txt.py
2. 按提示选择6篇旅游文章（输入数字编号）
3. 输入机场话题
4. 程序自动并发调用API并保存结果（7篇）
"""

import os
import sys
import json
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# =============================================================================
# API4 文本生成配置（内联）
# =============================================================================
DEFAULT_API_KEY = "sk-UfZhScIleUAfu0zT6WdeRMVT76zAwc8H3eMhY3vw0badLTfS"
DEFAULT_BASE_URL = "https://one.api4gpt.com/v1"
DEFAULT_MODEL = "gemini-3-pro"

MAX_WORKERS = 7
OUTPUT_DIR = r"C:\Users\Administrator\Desktop\公众号文章\txt"
LVYOU_DIR = r"C:\Users\Administrator\Desktop\opsdeck2\gongzhonghao\lvyou"

PART1_PROMPT = """请根据提供的下方旅游部分的内容，撰写一篇兼具种草感与高端感的游记文章。
 Constraints & Tone
 语气风格 ：高端旅游介绍感 + 种草感，吸引人但不浮夸，洋溢着一种真心推荐的感觉。女性作家的细腻感。 严禁 使用网络烂梗。
 字数限制 ：总字数控制在1200字以内。
 季节适配 ：根据当前时间（设定为2月），侧重描写未来3个月内（春季）的景色特点。全篇提及季节词汇控制在2~3次，避免重复啰嗦。
 行程描述 ：严格依据附件中的游玩方式和时间，但 不要 出现"6天"、"7天"等具体行程天数的描述。
 内容纯净 ：直接输出正文，不要输出"为您生成..."等无关引导语，也不要大标题。
 Structure & Content
 文章需严格按照以下结构输出：
 开头（1段） ：
 必须极具吸引力，重点描写该行程能带来的独特体验。
 配图要求：段首放1张图片标签。标签内容在Formatting Rules会说明
 景点主体（5-6个部分） ：
 从附件中筛选知名度最高或当季最美的 5-6个景点 。
 每个景点作为一个独立部分，使用 Markdown ## 景点名  作为小标题。
 段落与配图 ：每个景点内容分为2~3个自然段。在每个自然段前各放1个标签（后面会提到标签格式）
 结尾（1段） ：
 小标题为 ## END 。
 内容为以上风景或者旅游感受的总结+引导话术
 引导话术：想参加此线路，可后台私信参加抽奖。
 配图要求：小标题后面放一个标签，标签内容在Formatting Rules会说明
 Brand Integration (关键)
 品牌名称 ：鲸念
 植入要求 ：全篇穿插 2-3次  品牌植入（如：鲸念会员抽奖免费参加、会员高分反馈、旅游群分享等），切勿出现频率过高。
 排版要求 ：所有涉及"鲸念会员"及品牌福利的内容，必须 加粗 显示。
 高光时刻 ：文中特别精彩的描写也可酌情加粗，但不要泛滥。
 Formatting Rules
 输出格式 ：Markdown代码格式。
 标签格式 ：统一为 【关键词】 。
 关键词说明 ：必须是适合在小红书搜索的词汇（例如： 【泸沽湖篝火晚会】 ），搜索的关键词一定要带上景点或者进去的名字。
 开头和结尾的标签内容 ：在开头和结尾中出现的风景关键词，具体到某个景点，不然搜不到。
 注意 ：严禁出现图片链接，只保留上述格式的关键词标签。
 注意 ：在每个标签后面，都要加一个换行
 Workflow
 根据以下信息，开始写作："""

AIRPORT_PART1_PROMPT = """Core Goals
用户将发送一个【机场/民航话题】（如：升舱、安检、睡眠、休息室），你需要直接生成一篇符合微信公众号排版美学的深度文章。

🚫 Iron Laws (绝对禁令 - 违反即任务失败)
1. 严禁列表体：正文中绝对禁止使用 1. 2. 3. 或 - • 等符号进行罗列。必须使用流畅的自然段落，通过起承转合的连接词（但不要用"首先/其次"）来推进逻辑。
2. 严禁僵硬连接：禁止使用"综上所述"、"总而言之"、"第一点是"等教科书式表达。
3. 严禁配图遗漏：每一个自然段的最开头，必须包含一个文生图指令。

🎨 Tone & Style (语调动态适配)
根据用户输入的话题，微调语调，但保持"鲸念"的品牌调性和知识分享的调性。

🧬 Brand Integration (品牌植入：鲸念)
全篇必须自然植入"鲸念"品牌 2-3 次，植入方式参考：
1. 理念植入：引用"鲸念"倡导的从容出行价值观。
2. 社群背书："记得之前在鲸念社群里，有位飞友提到……"
3. 资源推荐："这份清单我已整理在鲸念的后台……"

🖼️ Visual Directives (配图指令规范)
● 位置：每一段落（包括开头结尾）的第一句。
● 格式：`[画面描述]`
● 一致性：全篇配图风格必须统一

✍️ Writing Workflow (标准作业程序)
Step 1: 开篇 (痛点共鸣，无小标题)
● 配图：设定全篇的视觉基调。
● 内容：描述该话题下的典型糟糕场景（如排长队、睡不好、花冤枉钱），然后引出"鲸念"的解决思路——不仅仅是技巧，更是心态。

Step 2: 正文核心 (黄金三段式，每一段都有小标题)
● 将话题拆解为三个自然流动的板块。
● 板块一（物理/装备/硬技巧）：介绍具体的工具或硬核操作。
● 板块二（策略/空间/软技巧）：介绍如何利用规则、空间或信息差。
● 板块三（心理/内调/升华）：从身心舒适度角度进行升华。
● 注意：在每一段开头插入配图指令，并在行文中加粗 2-3 个关键信息点。

Step 3: 结尾 (行动呼吁，有小标题)
● 配图：一张情绪释放、充满希望的画面（如落地、日出、微笑）。
● 内容：总结核心价值，邀请读者关注"鲸念"，在评论区分享他们的独家体验。



✍️ 特别注意
1、不要出现类似"Step 1"之列的东西，
2、除开篇以外，每个自然段前都要有适合内容的小标题，每个小标题10字以内，小标题前面加上"## "
3、只输出正文、小标题和文生图提示词，不要输出不相关的内容。
4、文生图提示词里的人物要求中文面孔，输出中文提示词。注意在提示词最后加上"5:4尺寸输出"

"""


# =============================================================================
# API4 文本生成函数（内联）
# =============================================================================

def call_txt2txt_api(
    prompt: str,
    model: str = DEFAULT_MODEL,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL
) -> str:
    """
    调用API4GPT文本生成API
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


# =============================================================================
# 主程序函数
# =============================================================================

def list_lvyou_files(lvyou_dir: str) -> List[str]:
    """获取lvyou目录下所有txt文件"""
    txt_files = [f for f in os.listdir(lvyou_dir) if f.endswith('.txt')]
    txt_files.sort()
    return txt_files


def display_file_list(files: List[str]) -> None:
    """显示文件列表供用户选择"""
    print("\n========== 可选择的旅游目的地 ==========")
    for idx, fname in enumerate(files, 1):
        city_name = fname.replace('.txt', '')
        print(f"  {idx}. {city_name}")
    print("==========================================\n")


def get_user_selections(files: List[str], count: int = 6) -> List[str]:
    """获取用户选择的文件"""
    display_file_list(files)

    while True:
        try:
            user_input = input(f"请输入 {count} 个数字（用空格或逗号分隔）, 例如: 1 3 5 7 9 11: ").strip()
            if not user_input:
                print("输入不能为空，请重新输入！\n")
                continue

            user_input = user_input.replace(',', ' ').replace('，', ' ')
            numbers = user_input.split()

            selected_indices = []
            for num_str in numbers:
                try:
                    num = int(num_str)
                    if num < 1 or num > len(files):
                        print(f"数字 {num} 超出范围 (1-{len(files)})，请重新输入！\n")
                        raise ValueError()
                    selected_indices.append(num - 1)
                except ValueError:
                    print(f"无效输入 '{num_str}'，请输入有效的数字！\n")
                    raise

            if len(selected_indices) != count:
                print(f"选择了 {len(selected_indices)} 个，需要 {count} 个，请重新输入！\n")
                continue

            if len(set(selected_indices)) != len(selected_indices):
                print("不能选择重复的选项，请重新输入！\n")
                continue

            selected_files = [files[i] for i in selected_indices]
            print(f"\n已选择 {count} 篇文章:")
            for fname in selected_files:
                print(f"  - {fname.replace('.txt', '')}")
            print()
            break

        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit(0)

    return selected_files


def get_airport_topic() -> str:
    """获取机场话题"""
    print("\n========== 机场小妙招话题 ==========")
    print("请输入一个机场/民航话题（如：升舱、安检、睡眠、休息室等）")
    print("====================================\n")

    while True:
        try:
            topic = input("请输入机场话题: ").strip()
            if not topic:
                print("输入不能为空，请重新输入！\n")
                continue
            print(f"\n已选择话题: {topic}\n")
            break
        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit(0)

    return topic


def read_lvyou_content(file_path: str) -> str:
    """读取旅游文件内容"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_prompts(selected_files: List[str], lvyou_dir: str, airport_topic: str) -> List[dict]:
    """根据用户选择生成所有提示词"""
    prompts = []

    for fname in selected_files:
        file_path = os.path.join(lvyou_dir, fname)
        city_name = fname.replace('.txt', '')
        content = read_lvyou_content(file_path)
        full_prompt = PART1_PROMPT + "\n\n" + content
        prompts.append({
            "prompt": full_prompt,
            "city_name": city_name,
            "file_name": fname,
            "article_type": "lvyou"
        })

    airport_prompt = AIRPORT_PART1_PROMPT + "\n\n机场话题：" + airport_topic
    prompts.append({
        "prompt": airport_prompt,
        "city_name": "机场小妙招",
        "file_name": "机场小妙招.txt",
        "article_type": "airport"
    })

    return prompts


def save_result_to_file(content: str, file_path: str) -> None:
    """保存文本内容到文件"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def process_single_request(idx: int, prompt: str, output_dir: str, article_info: dict, max_retries: int = 1) -> dict:
    """处理单个API请求"""
    article_type = article_info.get("article_type", "lvyou")
    city_name = article_info.get("city_name", "")
    type_label = "机场小妙招" if article_type == "airport" else city_name

    result = {"index": idx, "prompt": prompt, "status": "failed", "content": "", "city_name": city_name}

    for attempt in range(max_retries + 1):
        try:
            content = call_txt2txt_api(prompt=prompt)
            result["content"] = content
            result["status"] = "success"

            if article_type == "airport":
                file_name = "机场小妙招.txt"
            else:
                file_name = f"秘境{city_name}.txt"

            file_path = os.path.join(output_dir, file_name)
            save_result_to_file(content, file_path)

            if attempt > 0:
                print(f"第{idx}个请求完成 [{type_label}] (第{attempt + 1}次尝试成功) -> 已保存到 {file_name}")
            else:
                print(f"第{idx}个请求完成 [{type_label}] -> 已保存到 {file_name}")
            return result

        except Exception as e:
            if attempt < max_retries:
                print(f"第{idx}个请求失败 [{type_label}] -> 错误: {str(e)}，准备重试...")
            else:
                result["error"] = str(e)
                print(f"第{idx}个请求失败 [{type_label}] -> 错误: {str(e)}（已重试{max_retries}次，仍失败）")

    return result


def main(
    output_dir: str = OUTPUT_DIR,
    max_workers: int = MAX_WORKERS,
    lvyou_dir: str = LVYOU_DIR,
    selected_files: List[str] = None,
    airport_topic: str = None
) -> List[dict]:
    """批量并发调用API并保存结果"""
    if selected_files is None:
        files = list_lvyou_files(lvyou_dir)
        if not files:
            raise FileNotFoundError(f"在目录 {lvyou_dir} 中未找到任何 txt 文件")
        selected_files = get_user_selections(files, count=6)

    if airport_topic is None:
        airport_topic = get_airport_topic()

    prompt_data = generate_prompts(selected_files, lvyou_dir, airport_topic)
    prompts = [p["prompt"] for p in prompt_data]
    article_infos = [{"city_name": p["city_name"], "article_type": p["article_type"]} for p in prompt_data]

    os.makedirs(output_dir, exist_ok=True)
    print(f"\n开始并发调用API，共 {len(prompts)} 个请求 (6篇旅游 + 1篇机场)...")
    print(f"输出目录: {output_dir}")
    print()

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(process_single_request, idx + 1, prompt, output_dir, article_infos[idx]): idx + 1
            for idx, prompt in enumerate(prompts)
        }

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"第{idx}个请求异常: {str(e)}")
                results.append({"index": idx, "status": "error", "error": str(e)})

    print(f"\n===== 执行完成 =====")
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"成功: {success_count}/{len(results)}")
    if success_count > 0:
        print(f"生成的文件已保存到: {output_dir}")

    return results


if __name__ == "__main__":
    print("===== 批量并发调用 API4 文本生成 =====\n")
    print("流程: 选择6篇旅游文章 -> 输入机场话题 -> 并发生成7篇文章")
    results = main()
