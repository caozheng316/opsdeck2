#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标签管理工具 v3.0 - 管理和整理视频笔记标签
基于六大动作的流水线处理：
1. 过滤 (Filter) - 黑名单/脏数据拦截
2. 合并 (Merge) - 字面完全一致的去重
3. 融入 (Assimilate) - 语义相近的同义词映射
4. 归类 (Categorize) - 归入现有一级标签，新建二级
5. 创立 (Create) - 高频标签新建一级标签
6. 暂存 (Suspend) - 低频标签放入待分类
"""

import os
import sys
import json
import re
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Set

# ============================================================
#                      配置区
# ============================================================

# 默认源目录
DEFAULT_SOURCE_DIR = r"E:\抖音知识库"

# 标签配置文件名
TAG_CONFIG_FILENAME = "tags_config.json"

# 规则配置文件名
RULES_CONFIG_FILENAME = "rules.yaml"

# 通义千问 API 配置
QWEN_API_KEY = "sk-97c9189889234c25996d7e2d4f81e0e3"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen3.5-flash"
QWEN_TIMEOUT = 120

# 阈值配置
CREATE_PRIMARY_THRESHOLD = 8  # 频次>=8，触发创立动作
CLASSIFY_THRESHOLD = 4       # 频次>=4，尝试LLM分析

# 黑名单（过滤阶段使用）
DEFAULT_BLACKLIST = [
    "测试", "test", "null", "None", "TODO", "FIXME",
    "xxx", "yyy", "张三", "李四", "王五",
    "乱码", "无标题", "未命名"
]

# 纯标点正则
PURE_PUNCT_PATTERN = re.compile(r'^[\s\-_=+\[\]{}|\\:;"\'<>,.?/~`!@#$%^&*()（）【】｛｝：；""''《》〈〉、。！？…—]+$')

# ============================================================
#                      规则配置管理
# ============================================================

class RulesConfig:
    """强制规则配置管理"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_or_create()

    def _load_or_create(self) -> dict:
        """加载或创建规则配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                try:
                    return yaml.safe_load(f) or {}
                except:
                    return self._create_default_config()
        else:
            return self._create_default_config()

    def _create_default_config(self) -> dict:
        """创建默认规则配置"""
        default = {
            "not_assimilate": {},      # 拦截融入规则：标签 -> [不允许融入的二级标签列表]
            "force_assimilate": {},    # 强制融入规则：标签 -> 目标二级标签
            "force_categorize": {},    # 强制归类规则：标签 -> 目标一级标签
            "blacklist": []            # 额外黑名单
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default, f, allow_unicode=True, default_flow_style=False)
        return default

    def save(self):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

    def get_blacklist(self) -> Set[str]:
        """获取完整黑名单"""
        blacklist = set(DEFAULT_BLACKLIST)
        blacklist.update(self.config.get("blacklist", []))
        return blacklist

    def can_assimilate_to(self, tag: str, target: str) -> bool:
        """检查标签是否允许融入某个二级标签"""
        not_assimilate = self.config.get("not_assimilate", {})
        if tag in not_assimilate:
            blocked = not_assimilate[tag]
            if isinstance(blocked, list) and target in blocked:
                return False
        return True

    def get_force_assimilate(self, tag: str) -> Optional[str]:
        """获取强制融入目标"""
        return self.config.get("force_assimilate", {}).get(tag)

    def get_force_categorize(self, tag: str) -> Optional[str]:
        """获取强制归类目标"""
        return self.config.get("force_categorize", {}).get(tag)

# ============================================================
#                      标签配置管理
# ============================================================

class TagConfig:
    """标签配置管理"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_or_create()

    def _load_or_create(self) -> dict:
        """加载或创建配置文件"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if "primary_tags" not in config:
                return self._create_default_config()
            return config
        else:
            return self._create_default_config()

    def _create_default_config(self) -> dict:
        """创建默认配置"""
        return {
            "version": "3.0",
            "primary_tags": {
                "类别": {
                    "二级": [],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                },
                "作者": {
                    "二级": [],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                },
                "待分类": {
                    "二级": [],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            },
            "synonyms": {},
            "history": []
        }

    def save(self):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def add_history(self, action: str, details: dict):
        """添加操作历史"""
        self.config["history"].append({
            "action": action,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "details": details
        })
        if len(self.config["history"]) > 1000:
            self.config["history"] = self.config["history"][-500:]

    # ==================== 查询方法 ====================

    def get_all_primary_tags(self) -> List[str]:
        """获取所有一级标签"""
        return list(self.config["primary_tags"].keys())

    def get_secondary_tags(self, primary: str) -> List[str]:
        """获取指定一级标签下的所有二级标签"""
        if primary in self.config["primary_tags"]:
            return self.config["primary_tags"][primary].get("二级", [])
        return []

    def get_all_secondary_tags(self) -> Dict[str, str]:
        """获取所有二级标签及其所属一级标签 {二级标签: 一级标签}"""
        result = {}
        for primary, data in self.config["primary_tags"].items():
            for secondary in data.get("二级", []):
                result[secondary] = primary
        return result

    def find_exact_secondary_tag(self, tag: str) -> Optional[Tuple[str, str]]:
        """查找完全匹配的二级标签，返回 (一级标签, 二级标签) 或 None"""
        for primary, data in self.config["primary_tags"].items():
            if tag in data.get("二级", []):
                return (primary, tag)
        return None

    def find_synonym_tag(self, tag: str) -> Optional[Tuple[str, str, str]]:
        """查找同义词标签，返回 (一级标签, 标准二级标签, 输入标签) 或 None"""
        for standard_tag, synonyms in self.config.get("synonyms", {}).items():
            if tag in synonyms or tag == standard_tag:
                for primary, data in self.config["primary_tags"].items():
                    if standard_tag in data.get("二级", []):
                        return (primary, standard_tag, tag)
        return None

    # ==================== 修改方法 ====================

    def add_secondary_tag(self, primary: str, secondary: str, is_new_primary: bool = False):
        """添加二级标签（归类动作）"""
        if primary not in self.config["primary_tags"]:
            self.config["primary_tags"][primary] = {
                "二级": [],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

        # 检查命名冲突：二级标签不能和一级标签同名
        if secondary == primary:
            # 自动添加后缀
            secondary = f"{primary}_相关"

        # 检查全局唯一性
        all_secondary = self.get_all_secondary_tags()
        if secondary in all_secondary and all_secondary[secondary] != primary:
            # 二级标签已存在于其他一级标签下
            existing_primary = all_secondary[secondary]
            print(f"    [警告] 二级标签 '{secondary}' 已存在于 '{existing_primary}' 下，跳过")
            return

        if secondary not in self.config["primary_tags"][primary]["二级"]:
            self.config["primary_tags"][primary]["二级"].append(secondary)
            self.add_history("归类" if not is_new_primary else "创立", {
                "primary": primary,
                "secondary": secondary,
                "is_new_primary": is_new_primary
            })
            self.save()

    def add_synonym(self, primary: str, standard_tag: str, synonym: str):
        """添加同义词（融入动作）"""
        if standard_tag not in self.config["synonyms"]:
            self.config["synonyms"][standard_tag] = []

        if synonym not in self.config["synonyms"][standard_tag] and synonym != standard_tag:
            self.config["synonyms"][standard_tag].append(synonym)
            self.add_history("融入", {
                "primary": primary,
                "standard": standard_tag,
                "synonym": synonym
            })
            self.save()

    def suspend_tag(self, tag: str):
        """暂存标签（放入待分类）"""
        self.add_secondary_tag("待分类", tag)

# ============================================================
#                      LLM 辅助
# ============================================================

class LLMAssistant:
    """LLM辅助标签处理"""

    def __init__(self, tag_config: TagConfig):
        self.api_url = f"{QWEN_BASE_URL}/chat/completions"
        self.api_key = QWEN_API_KEY
        self.tag_config = tag_config

    def _call_api(self, messages: list, max_tokens: int = 2000, retries: int = 3) -> str:
        """调用通义千问API（带重试机制）"""
        import requests
        import time

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": QWEN_MODEL,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        last_error = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=QWEN_TIMEOUT
                )

                if response.status_code != 200:
                    raise Exception(f"API请求失败: {response.status_code}")

                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")

            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"\n    [警告] LLM调用失败({attempt + 1}/{retries}): {str(e)[:50]}")
                    print(f"    等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        raise Exception(f"LLM调用失败(重试{retries}次后): {str(last_error)}")

    def _build_tag_tree_prompt(self) -> str:
        """构建标签树提示词"""
        lines = ["当前标签库结构："]
        for primary, data in self.tag_config.config["primary_tags"].items():
            secondaries = data.get("二级", [])
            lines.append(f"- 一级标签【{primary}】")
            for sec in secondaries[:20]:  # 限制数量
                lines.append(f"  - {sec}")
            if len(secondaries) > 20:
                lines.append(f"  - ... (共{len(secondaries)}个)")
        return "\n".join(lines)

    def analyze_assimilate(self, tags: List[str], rules_config: RulesConfig) -> List[dict]:
        """分析融入建议（步骤2.1）

        要求LLM判断标签是否可以融入现有二级标签。
        返回结果必须从现有二级标签中选取。
        """
        all_secondary_map = self.tag_config.get_all_secondary_tags()
        if not all_secondary_map:
            return []

        # 构建禁止项提示
        not_assimilate = rules_config.config.get("not_assimilate", {})
        forbidden_hints = []
        for tag, blocked in not_assimilate.items():
            if isinstance(blocked, list):
                forbidden_hints.append(f"- '{tag}' 不允许融入 {blocked}")

        system_prompt = f"""你是一个标签分析专家。分析给定的标签是否能融入（作为同义词）到现有二级标签。

规则：
1. 只能从现有二级标签列表中选取目标，不能创造新标签
2. 如果标签是某个二级标签的同义词或语义相近，返回融入建议
3. 如果没有合适的融入目标，返回 null
4. 置信度低于0.7不要返回

{self._build_tag_tree_prompt()}

禁止规则：
{chr(10).join(forbidden_hints) if forbidden_hints else '无'}

返回JSON数组格式：
[
    {{"tag": "投资理财", "assimilate_to": "投资", "confidence": 0.95, "reason": "语义相同"}},
    {{"tag": "单车", "assimilate_to": "自行车", "confidence": 0.9, "reason": "同义词"}}
]

如果没有合适的融入建议，返回空数组 []"""

        user_prompt = f"待分析标签: {json.dumps(tags, ensure_ascii=False)}"

        content = self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], max_tokens=2000)

        # 解析并验证结果
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            suggestions = json.loads(json_match.group())
            # 过滤：只保留有效建议（目标二级标签存在，且未被禁止）
            valid = []
            for s in suggestions:
                tag = s.get("tag")
                target = s.get("assimilate_to")
                if tag in tags and target in all_secondary_map:
                    # 检查禁止规则
                    if rules_config.can_assimilate_to(tag, target):
                        s["target_primary"] = all_secondary_map[target]
                        valid.append(s)
            return valid
        return []

    def analyze_categorize(self, tags: List[str]) -> List[dict]:
        """分析归类建议（步骤2.2）

        要求LLM判断标签应该归到哪个现有的一级标签。
        返回结果必须从现有的一级标签中选取。
        """
        primary_tags = [p for p in self.tag_config.get_all_primary_tags()
                       if p not in ["类别", "作者", "待分类"]]

        if not primary_tags:
            return []

        system_prompt = f"""你是一个标签分类专家。分析给定的标签应该归到哪个现有的一级分类。

规则：
1. 只能从现有的一级标签中选取，不能创造新的一级标签
2. 如果没有合适的一级标签，返回 null（不强行归类）
3. 置信度低于0.7不要返回

现有的一级标签：
{json.dumps(primary_tags, ensure_ascii=False)}

返回JSON数组格式：
[
    {{"tag": "销售技巧", "categorize_to": "职场商业", "confidence": 0.9, "reason": "销售属于职场技能"}},
    {{"tag": "时间管理", "categorize_to": "个人成长", "confidence": 0.85, "reason": "时间管理是成长技能"}}
]

如果没有合适的归类建议，返回空数组 []"""

        user_prompt = f"待分析标签: {json.dumps(tags, ensure_ascii=False)}"

        content = self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], max_tokens=2000)

        # 解析并验证结果
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            suggestions = json.loads(json_match.group())
            # 过滤：只保留有效建议
            valid = []
            for s in suggestions:
                tag = s.get("tag")
                target = s.get("categorize_to")
                if tag in tags and target in primary_tags:
                    valid.append(s)
            return valid
        return []

    def suggest_new_primary(self, tags: List[str]) -> List[dict]:
        """建议新建一级标签（步骤2.3.1）

        用于频次>=8的标签，建议是否需要新建一级标签。
        """
        system_prompt = """你是一个分类专家。分析给定的标签，判断是否需要新建一级标签。

规则：
1. 只有当标签具有独立分类价值时才建议新建一级标签
2. 一级标签名称应该简洁通用（2-4个汉字）
3. 一级标签名称不能是"类别"、"作者"、"待分类"
4. 多个相关标签可以建议同一个新一级标签
5. 如果标签可以归入现有分类，不要建议新建

返回JSON数组格式：
[
    {"tag": "健身", "suggested_primary": "健康运动", "reason": "健身相关内容需要独立分类"},
    {"tag": "瑜伽", "suggested_primary": "健康运动", "reason": "与健身同属运动健康领域"}
]

如果不需要新建一级标签，返回空数组 []"""

        user_prompt = f"待分析标签: {json.dumps(tags, ensure_ascii=False)}"

        content = self._call_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], max_tokens=2000)

        # 解析结果
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            suggestions = json.loads(json_match.group())
            # 过滤：排除保留名称
            valid = []
            for s in suggestions:
                tag = s.get("tag")
                suggested = s.get("suggested_primary")
                if tag in tags and suggested not in ["类别", "作者", "待分类"]:
                    valid.append(s)
            return valid
        return []

# ============================================================
#                      标签处理流水线
# ============================================================

class TagPipeline:
    """标签处理流水线 - 按照六大动作顺序处理"""

    def __init__(self, tag_config: TagConfig, rules_config: RulesConfig, llm: LLMAssistant):
        self.tag_config = tag_config
        self.rules_config = rules_config
        self.llm = llm

        # 统计信息
        self.stats = {
            "filtered": 0,      # 过滤数量
            "merged": 0,        # 合并数量
            "assimilated": 0,   # 融入数量
            "categorized": 0,   # 归类数量
            "created": 0,       # 创立数量
            "suspended": 0      # 暂存数量
        }

    def process(self, work_labels: List[str], category: str = "", author: str = "", existing_finish_tags: List[str] = None) -> List[str]:
        """处理标签流水线

        Args:
            work_labels: 待处理的原始标签列表（来自tags和filename_tags）
            category: MD文件的category字段值
            author: MD文件的author字段值
            existing_finish_tags: 已有的完成标签（用于增量处理，避免重复）

        Returns:
            处理后的标签列表（一级/二级格式），写入finish_tags
        """
        result_tags = []
        self.stats = {k: 0 for k in self.stats}

        # 如果有已有的完成标签，先加入结果（保留之前的处理结果）
        if existing_finish_tags:
            for tag in existing_finish_tags:
                if tag and "/" in tag:  # 只保留有效的完成标签格式
                    result_tags.append(tag)

        # ================== 阶段0：准备与清洗 ==================
        print("\n【阶段0：准备与清洗】")

        # 0.1 文本归一化
        work_labels = [self._normalize_label(tag) for tag in work_labels]
        work_labels = [tag for tag in work_labels if tag]  # 移除空标签
        print(f"  0.1 归一化后: {len(work_labels)} 个标签")

        # 0.2 同源去重（优先保留category/author）
        work_labels = self._deduplicate_sources(work_labels, category, author)
        print(f"  0.2 同源去重后: {len(work_labels)} 个标签")

        # 0.3 黑名单过滤【过滤】
        work_labels, filtered = self._filter_blacklist(work_labels)
        self.stats["filtered"] = len(filtered)
        print(f"  0.3 黑名单过滤: 移除 {len(filtered)} 个标签")
        if filtered:
            print(f"      过滤掉: {filtered[:10]}{'...' if len(filtered) > 10 else ''}")

        # ================== 阶段1：确定性匹配 ==================
        print("\n【阶段1：确定性匹配】")

        # 1.1 结构化字段识别（category→类别，author→作者）
        if category:
            self.tag_config.add_secondary_tag("类别", category)
            result_tags.append(f"类别/{category}")
            print(f"  1.1 结构化: 类别/{category}")
        if author:
            self.tag_config.add_secondary_tag("作者", author)
            result_tags.append(f"作者/{author}")
            print(f"  1.1 结构化: 作者/{author}")

        # 1.2 强制规则拦截
        work_labels, forced = self._apply_force_rules(work_labels, result_tags)
        if forced:
            print(f"  1.2 强制规则: 处理 {len(forced)} 个标签")
            for tag, action, target in forced:
                print(f"      {tag} → {action} → {target}")

        # 1.3 字面量比对【合并】
        work_labels, merged = self._exact_match(work_labels, result_tags)
        self.stats["merged"] = len(merged)
        print(f"  1.3 字面量合并: {len(merged)} 个标签")
        if merged:
            print(f"      合并: {merged[:10]}{'...' if len(merged) > 10 else ''}")

        # ================== 阶段2：AI语义匹配 ==================
        if not work_labels:
            print("\n【阶段2：AI语义匹配】跳过（无待处理标签）")
            return list(set(result_tags))

        print(f"\n【阶段2：AI语义匹配】待处理: {len(work_labels)} 个标签")

        # 2.1 语义融入【融入】
        print("  2.1 分析融入建议...")
        assimilate_result = self.llm.analyze_assimilate(work_labels, self.rules_config)
        assimilated_tags = set()

        for sug in assimilate_result:
            if sug.get("confidence", 0) >= 0.7:
                tag = sug["tag"]
                target = sug["assimilate_to"]
                primary = sug["target_primary"]
                self.tag_config.add_synonym(primary, target, tag)
                result_tags.append(f"{primary}/{target}")
                assimilated_tags.add(tag)
                self.stats["assimilated"] += 1
                print(f"      融入: {tag} → {primary}/{target}")

        work_labels = [t for t in work_labels if t not in assimilated_tags]

        # 2.2 树枝归类【归类】
        if work_labels:
            print("  2.2 分析归类建议...")
            categorize_result = self.llm.analyze_categorize(work_labels)
            categorized_tags = set()

            for sug in categorize_result:
                if sug.get("confidence", 0) >= 0.7:
                    tag = sug["tag"]
                    primary = sug["categorize_to"]
                    self.tag_config.add_secondary_tag(primary, tag)
                    result_tags.append(f"{primary}/{tag}")
                    categorized_tags.add(tag)
                    self.stats["categorized"] += 1
                    print(f"      归类: {tag} → {primary}/{tag}")

            work_labels = [t for t in work_labels if t not in categorized_tags]

        # 2.3 频次判定与最终收容
        if not work_labels:
            print("  2.3 所有标签已处理完成")
            return list(set(result_tags))

        print(f"  2.3 频次判定: 剩余 {len(work_labels)} 个标签")

        # 统计频次（这里简化处理，实际应从unclassified获取）
        # 高频标签>=8: 创立
        # 低频标签<8: 暂存

        # 暂时：全部暂存
        # TODO: 需要结合unclassified的频次统计
        for tag in work_labels:
            self.tag_config.suspend_tag(tag)
            result_tags.append(f"待分类/{tag}")
            self.stats["suspended"] += 1
            print(f"      暂存: {tag} → 待分类/{tag}")

        return list(set(result_tags))

    # ================== 辅助方法 ==================

    def _normalize_label(self, tag: str) -> Optional[str]:
        """0.1 文本归一化"""
        if not tag:
            return None
        tag = str(tag).strip().lower()
        if not tag:
            return None
        return tag

    def _deduplicate_sources(self, tags: List[str], category: str, author: str) -> List[str]:
        """0.2 同源去重"""
        # 如果标签与category或author重复，优先保留category/author
        result = []
        category_lower = category.lower() if category else ""
        author_lower = author.lower() if author else ""

        for tag in tags:
            if tag == category_lower or tag == author_lower:
                continue  # 跳过，因为已经单独处理
            result.append(tag)

        return result

    def _filter_blacklist(self, tags: List[str]) -> Tuple[List[str], List[str]]:
        """0.3 黑名单过滤【过滤】"""
        blacklist = self.rules_config.get_blacklist()
        valid = []
        filtered = []

        for tag in tags:
            # 黑名单检查
            if tag in blacklist:
                filtered.append(tag)
                continue

            # 纯标点检查
            if PURE_PUNCT_PATTERN.match(tag):
                filtered.append(tag)
                continue

            # 长度检查
            if len(tag) < 2:
                filtered.append(tag)
                continue

            valid.append(tag)

        return valid, filtered

    def _apply_force_rules(self, tags: List[str], result_tags: List[str]) -> Tuple[List[str], List[Tuple]]:
        """1.2 强制规则拦截"""
        remaining = []
        applied = []

        for tag in tags:
            # 强制融入规则
            force_assimilate = self.rules_config.get_force_assimilate(tag)
            if force_assimilate:
                # 查找目标二级标签所属的一级标签
                all_secondary = self.tag_config.get_all_secondary_tags()
                if force_assimilate in all_secondary:
                    primary = all_secondary[force_assimilate]
                    self.tag_config.add_synonym(primary, force_assimilate, tag)
                    result_tags.append(f"{primary}/{force_assimilate}")
                    applied.append((tag, "强制融入", force_assimilate))
                    continue

            # 强制归类规则
            force_categorize = self.rules_config.get_force_categorize(tag)
            if force_categorize:
                self.tag_config.add_secondary_tag(force_categorize, tag)
                result_tags.append(f"{force_categorize}/{tag}")
                applied.append((tag, "强制归类", force_categorize))
                continue

            remaining.append(tag)

        return remaining, applied

    def _exact_match(self, tags: List[str], result_tags: List[str]) -> Tuple[List[str], List[str]]:
        """1.3 字面量比对【合并】"""
        all_secondary_map = self.tag_config.get_all_secondary_tags()
        remaining = []
        merged = []

        for tag in tags:
            if tag in all_secondary_map:
                primary = all_secondary_map[tag]
                result_tags.append(f"{primary}/{tag}")
                merged.append(tag)
            else:
                remaining.append(tag)

        return remaining, merged

# ============================================================
#                      MD文件处理
# ============================================================

class MDFileProcessor:
    """MD文件处理器"""

    def __init__(self, source_dir: str, tag_config: TagConfig, rules_config: RulesConfig, llm: LLMAssistant):
        self.source_dir = source_dir
        self.tag_config = tag_config
        self.rules_config = rules_config
        self.pipeline = TagPipeline(tag_config, rules_config, llm)

    def scan_all_md_files(self) -> List[str]:
        """扫描所有MD文件"""
        md_files = []
        source_path = Path(self.source_dir)

        for md_file in source_path.rglob("*.md"):
            if md_file.name in [TAG_CONFIG_FILENAME, RULES_CONFIG_FILENAME]:
                continue
            md_files.append(str(md_file))

        return md_files

    def parse_md_file(self, md_path: str) -> dict:
        """解析MD文件，提取信息

        字段说明：
        - tags: 原始标签（来自用户输入，不可变）
        - filename_tags: 来自文件名的原始标签（不可变）
        - finish_tags: 处理完成的标签（一级/二级格式，可重新生成）
        - category: 分类（专属标签来源）
        - author: 作者（专属标签来源）
        """
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {
            "path": md_path,
            "title": "",
            "category": "",
            "author": "",
            "tags": [],           # 原始标签，不变
            "filename_tags": [],  # 原始标签，不变
            "finish_tags": [],    # 处理完成的标签
            "content": content
        }

        # 提取YAML前置信息
        yaml_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if yaml_match:
            yaml_content = yaml_match.group(1)

            for line in yaml_content.split('\n'):
                if line.startswith('title:'):
                    result["title"] = line.split(':', 1)[1].strip().strip('"\'')
                elif line.startswith('category:'):
                    result["category"] = line.split(':', 1)[1].strip().strip('"\'')
                elif line.startswith('author:'):
                    result["author"] = line.split(':', 1)[1].strip().strip('"\'')
                elif line.startswith('filename_tags:'):
                    tags_str = line.split(':', 1)[1].strip()
                    try:
                        result["filename_tags"] = json.loads(tags_str)
                    except:
                        pass
                elif line.startswith('tags:'):
                    tags_str = line.split(':', 1)[1].strip()
                    try:
                        result["tags"] = json.loads(tags_str)
                    except:
                        result["tags"] = [t.strip().strip('"\'') for t in tags_str.split(',') if t.strip()]
                elif line.startswith('finish_tags:'):
                    tags_str = line.split(':', 1)[1].strip()
                    try:
                        result["finish_tags"] = json.loads(tags_str)
                    except:
                        result["finish_tags"] = [t.strip().strip('"\'') for t in tags_str.split(',') if t.strip()]

        return result

    def update_finish_tags(self, md_path: str, finish_tags: List[str]) -> bool:
        """更新MD文件的finish_tags字段

        注意：不修改原始tags字段，只更新finish_tags
        """
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        finish_tags_json = json.dumps(finish_tags, ensure_ascii=False)

        # 检查是否已有finish_tags字段
        if re.search(r'^finish_tags:', content, re.MULTILINE):
            # 替换现有finish_tags
            new_content = re.sub(
                r'^finish_tags:.*$',
                f'finish_tags: {finish_tags_json}',
                content,
                flags=re.MULTILINE
            )
        else:
            # 在tags字段后添加finish_tags
            new_content = re.sub(
                r'^(tags:.*$)',
                f'\\1\nfinish_tags: {finish_tags_json}',
                content,
                flags=re.MULTILINE
            )

        if new_content != content:
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        return False

    def process_single_file(self, md_path: str) -> dict:
        """处理单个MD文件"""
        md_info = self.parse_md_file(md_path)

        # 收集所有标签
        # 收集原始标签作为输入
        work_labels = []
        work_labels.extend(md_info.get("filename_tags", []))
        work_labels.extend(md_info.get("tags", []))

        # 通过流水线处理
        result_tags = self.pipeline.process(
            work_labels,
            category=md_info.get("category", ""),
            author=md_info.get("author", ""),
            existing_finish_tags=md_info.get("finish_tags", [])
        )

        return {
            "path": md_path,
            "result_tags": result_tags,
            "stats": self.pipeline.stats
        }

# ============================================================
#                      标签管理器
# ============================================================

class TagManager:
    """标签管理器主类"""

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.config_path = os.path.join(source_dir, TAG_CONFIG_FILENAME)
        self.rules_path = os.path.join(source_dir, RULES_CONFIG_FILENAME)

        self.tag_config = TagConfig(self.config_path)
        self.rules_config = RulesConfig(self.rules_path)
        self.llm = LLMAssistant(self.tag_config)
        self.md_processor = MDFileProcessor(source_dir, self.tag_config, self.rules_config, self.llm)

    def show_status(self):
        """显示当前状态"""
        print("\n" + "=" * 70)
        print("标签库状态")
        print("=" * 70)

        # 显示一级标签和二级标签
        print("\n【一级标签】")
        for primary, data in self.tag_config.config["primary_tags"].items():
            secondaries = data.get("二级", [])
            count = len(secondaries)
            created = data.get("created_at", "未知")
            marker = " (专属)" if primary in ["类别", "作者"] else ""
            marker = " (暂存)" if primary == "待分类" else marker
            print(f"\n  {primary}{marker} ({count}个二级标签) - 创建于 {created}")
            if secondaries:
                for i in range(0, len(secondaries), 5):
                    line = "    " + ", ".join(secondaries[i:i+5])
                    print(line)

        # 显示同义词
        synonyms = self.tag_config.config.get("synonyms", {})
        if synonyms:
            print("\n【同义词映射】")
            for standard, syns in synonyms.items():
                print(f"  {standard} ← {', '.join(syns)}")

        # 显示统计
        total_primary = len(self.tag_config.config["primary_tags"])
        total_secondary = sum(len(data.get("二级", [])) for data in self.tag_config.config["primary_tags"].values())
        total_synonyms = sum(len(syns) for syns in synonyms.values())

        print("\n【统计】")
        print(f"  一级标签: {total_primary}个")
        print(f"  二级标签: {total_secondary}个")
        print(f"  同义词: {total_synonyms}个")

    def scan_and_process(self, force_regenerate: bool = False):
        """扫描并处理所有MD文件

        Args:
            force_regenerate: 是否强制重新生成finish_tags（即使已有）
        """
        print("\n" + "=" * 70)
        print("扫描并处理MD文件...")
        print("=" * 70)

        md_files = self.md_processor.scan_all_md_files()
        print(f"\n找到 {len(md_files)} 个MD文件")

        total_stats = {
            "filtered": 0,
            "merged": 0,
            "assimilated": 0,
            "categorized": 0,
            "created": 0,
            "suspended": 0
        }

        skipped_count = 0

        for i, md_file in enumerate(md_files, 1):
            filename = Path(md_file).name[:40]
            print(f"\n{'='*60}")
            print(f"[{i}/{len(md_files)}] {filename}")
            print("=" * 60)

            try:
                md_info = self.md_processor.parse_md_file(md_file)

                # 如果已有finish_tags且不强制重新生成，跳过
                if not force_regenerate and md_info.get("finish_tags"):
                    print("  已有finish_tags，跳过（使用 --force 强制重新生成）")
                    skipped_count += 1
                    continue

                result = self.md_processor.process_single_file(md_file)

                # 累计统计
                for key in total_stats:
                    total_stats[key] += result["stats"][key]

                # 更新MD文件的finish_tags字段（不修改原始tags）
                self.md_processor.update_finish_tags(md_file, result["result_tags"])

            except Exception as e:
                print(f"  [错误] 处理失败: {str(e)}")

        # 汇总统计
        print("\n" + "=" * 70)
        print("处理完成！汇总统计：")
        print("=" * 70)
        if skipped_count:
            print(f"  跳过: {skipped_count} 个文件（已有finish_tags）")
        print(f"  过滤: {total_stats['filtered']} 个")
        print(f"  合并: {total_stats['merged']} 个")
        print(f"  融入: {total_stats['assimilated']} 个")
        print(f"  归类: {total_stats['categorized']} 个")
        print(f"  创立: {total_stats['created']} 个")
        print(f"  暂存: {total_stats['suspended']} 个")

    def process_high_frequency(self):
        """处理高频未分类标签（频次>=8，触发创立）"""
        print("\n" + "=" * 70)
        print("处理高频标签")
        print("=" * 70)

        # 从待分类中获取标签
        pending_secondary = self.tag_config.get_secondary_tags("待分类")
        if not pending_secondary:
            print("\n没有待处理的标签")
            return

        # 由于没有频次统计，暂时按列表展示
        print(f"\n待分类标签: {len(pending_secondary)} 个")
        for i, tag in enumerate(pending_secondary[:50], 1):
            print(f"  {i}. {tag}")
        if len(pending_secondary) > 50:
            print(f"  ... 还有 {len(pending_secondary) - 50} 个")

        # 筛选高频标签（这里简化处理，实际应统计频次）
        # 暂时让用户选择要处理的标签
        print("\n请输入要处理的标签序号（用逗号分隔，如: 1,3,5），或按回车跳过：")
        choice = input("选择: ").strip()

        if not choice:
            print("已跳过")
            return

        try:
            indices = [int(x.strip()) for x in choice.split(",")]
            selected_tags = [pending_secondary[i-1] for i in indices if 0 < i <= len(pending_secondary)]
        except:
            print("输入无效")
            return

        if not selected_tags:
            print("没有选择标签")
            return

        print(f"\n已选择 {len(selected_tags)} 个标签:")
        for tag in selected_tags:
            print(f"  - {tag}")

        # LLM建议新建一级标签
        print("\n正在分析...")
        suggestions = self.llm.suggest_new_primary(selected_tags)

        if not suggestions:
            print("\nLLM未建议新建一级标签，这些标签可能需要归入现有分类")
            return

        print("\n【LLM建议】")
        for sug in suggestions:
            print(f"  {sug.get('tag', '?')} → 新建一级标签: {sug.get('suggested_primary', '?')}")
            if sug.get('reason'):
                print(f"    原因: {sug['reason']}")

        # 用户确认
        print("\n操作选项:")
        print("  y - 接受所有建议")
        print("  i - 逐个确认")
        print("  n - 取消")
        print("  add rule - 将某个标签加入强制规则")

        confirm = input("选择: ").strip().lower()

        if confirm == 'y':
            self._apply_create_suggestions(suggestions)
        elif confirm == 'i':
            self._apply_create_suggestions_interactive(suggestions)
        elif confirm == 'add rule':
            self._add_rule_interactive(selected_tags)
        else:
            print("已取消")

    def _apply_create_suggestions(self, suggestions: List[dict]):
        """应用创立建议"""
        for sug in suggestions:
            tag = sug.get("tag")
            primary = sug.get("suggested_primary")
            if tag and primary:
                # 从待分类移除
                if tag in self.tag_config.config["primary_tags"]["待分类"]["二级"]:
                    self.tag_config.config["primary_tags"]["待分类"]["二级"].remove(tag)
                # 创建新一级标签
                self.tag_config.add_secondary_tag(primary, tag, is_new_primary=True)
                print(f"  创立: {primary}/{tag}")
        self.tag_config.save()
        print("\n已应用所有建议")

    def _apply_create_suggestions_interactive(self, suggestions: List[dict]):
        """逐个确认创立建议"""
        for sug in suggestions:
            tag = sug.get("tag")
            suggested = sug.get("suggested_primary")
            reason = sug.get("reason", "")

            if not tag or not suggested:
                continue

            print(f"\n  标签: {tag}")
            print(f"  建议一级标签: {suggested}")
            if reason:
                print(f"  原因: {reason}")

            custom = input("  一级标签名称[回车确认/自定义名称/s跳过]: ").strip()

            if custom.lower() == 's':
                continue

            final_primary = custom if custom else suggested

            if final_primary in ["类别", "作者", "待分类"]:
                print("  错误：这是保留名称")
                continue

            # 从待分类移除
            if tag in self.tag_config.config["primary_tags"]["待分类"]["二级"]:
                self.tag_config.config["primary_tags"]["待分类"]["二级"].remove(tag)

            self.tag_config.add_secondary_tag(final_primary, tag, is_new_primary=True)
            print(f"  已创建: {final_primary}/{tag}")

        self.tag_config.save()
        print("\n处理完成")

    def _add_rule_interactive(self, tags: List[str]):
        """交互式添加规则"""
        print("\n添加强制规则:")
        print("  1. 强制融入（标签 → 现有二级标签）")
        print("  2. 强制归类（标签 → 现有一级标签）")
        print("  3. 禁止融入（标签 ↛ 某个二级标签）")

        choice = input("选择类型: ").strip()

        if choice == "1":
            tag = input("输入标签: ").strip()
            target = input("融入到的二级标签: ").strip()
            if tag and target:
                if "force_assimilate" not in self.rules_config.config:
                    self.rules_config.config["force_assimilate"] = {}
                self.rules_config.config["force_assimilate"][tag] = target
                self.rules_config.save()
                print(f"已添加: {tag} → 强制融入 → {target}")

        elif choice == "2":
            tag = input("输入标签: ").strip()
            target = input("归入的一级标签: ").strip()
            if tag and target:
                if "force_categorize" not in self.rules_config.config:
                    self.rules_config.config["force_categorize"] = {}
                self.rules_config.config["force_categorize"][tag] = target
                self.rules_config.save()
                print(f"已添加: {tag} → 强制归类 → {target}")

        elif choice == "3":
            tag = input("输入标签: ").strip()
            blocked = input("禁止融入的二级标签（多个用逗号分隔）: ").strip()
            if tag and blocked:
                blocked_list = [x.strip() for x in blocked.split(",")]
                if "not_assimilate" not in self.rules_config.config:
                    self.rules_config.config["not_assimilate"] = {}
                self.rules_config.config["not_assimilate"][tag] = blocked_list
                self.rules_config.save()
                print(f"已添加: {tag} ↛ {blocked_list}")

        else:
            print("无效选择")

# ============================================================
#                      主菜单
# ============================================================

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("标签管理工具 v3.0")
    print("基于六大动作的流水线处理")
    print("=" * 70)
    print("\n说明:")
    print("  - tags: 原始标签（不变）")
    print("  - finish_tags: 处理后的标签（一级/二级格式）")

    # 获取源目录
    source_dir = DEFAULT_SOURCE_DIR
    if len(sys.argv) > 1:
        source_dir = sys.argv[1]

    if not os.path.exists(source_dir):
        print(f"\n错误：目录不存在 - {source_dir}")
        return

    manager = TagManager(source_dir)

    while True:
        print("\n" + "-" * 50)
        print("操作菜单:")
        print("  1. 查看标签库状态")
        print("  2. 扫描并处理MD文件（跳过已有finish_tags）")
        print("  3. 强制重新生成所有finish_tags")
        print("  4. 处理待分类标签")
        print("  5. 编辑强制规则")
        print("  0. 退出")
        print("-" * 50)

        choice = input("请选择: ").strip()

        if choice == "1":
            manager.show_status()
        elif choice == "2":
            manager.scan_and_process(force_regenerate=False)
        elif choice == "3":
            confirm = input("确认要重新生成所有finish_tags吗？(y/n): ").strip().lower()
            if confirm == 'y':
                manager.scan_and_process(force_regenerate=True)
            else:
                print("已取消")
        elif choice == "4":
            manager.process_high_frequency()
        elif choice == "5":
            print(f"\n规则配置文件: {manager.rules_path}")
            print("请直接编辑该文件后重启程序")
        elif choice == "0":
            print("\n再见！")
            break
        else:
            print("无效选择，请重试")

if __name__ == "__main__":
    main()