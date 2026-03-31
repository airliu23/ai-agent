#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 对话式 BUG 记录工具 - 重构优化版
优化内容：统一常量配置、添加类型注解、改进错误处理、存储层抽象
"""
import os
import re
import datetime
from typing import Dict, List, Optional, Any
from llm import (
    ai_intent_recognize, 
    ai_extract_all_fields, 
    ai_generate_question, 
    search_similar_bugs,
    ai_humanize_reply
)
from ui import TerminalUI, UI
from storage import BugStorage, FileStorage

# ==================== 常量配置 ====================
# LLM 相关配置
LLM_TIMEOUT = 100
AUTO_FILL_TEXT = "暂未确定"
MAX_SIMILAR_BUGS = 3
MAX_BUGS_FOR_SEARCH = 50
MAX_RETRY_COUNT = 2

# BUG 核心特征关键词
BUG_CORE_KEYWORDS = [
    'bug', '故障', '失败', '异常', '报错', '触发', '复现', '中断',
    '芯片', '协议', 'pd', 'ufcs', 'qc', 'otg', 'ts', 'pmic', '电压', '电流',
    '时序', '状态机', '死机', '重启', '不工作', '无响应', '跳变', '不稳定',
    '识别', '协商', '通信', '超时', '丢包', '复位', 'reset', 'hardreset', '溢出', '下溢'
]

# 无意义过滤词
STOP_WORDS = [
    '的', '了', '是', '我', '有', '一个', '问题', '遇到', '这个', '什么', '在', '和', '就', '都'
]

# 兜底表述关键词
FALLBACK_KEYWORDS = [
    "其他都暂未确定", "其余都待定", "其他都不确定", "剩下的都不知道",
    "其他暂无", "其余都未确定", "其他都没定", "剩下的暂未确定"
]

# 退出和完成指令
EXIT_COMMANDS = ['exit', 'quit', '取消']
MULTI_LINE_MARKER = "###"

# 更新意图关键词
UPDATE_KEYWORDS = [
    '更新', '进展', '补充', '追加', '修改', '新动态', '新情况',
    '发现了', '已解决', '已修复', '找到了', '根因', '定位到',
    # 回溯修正类
    '分析错了', '之前错了', '搞错了', '判断错了', '弄错了',
    '之前说的', '之前分析', '之前那个', '那个问题', '上次那个',
    # 继续分析类
    '继续分析', '再看看', '再分析', '重新分析', '重新看',
    '增加'

]

# 分析类更新关键词（用于判断是否应插入分析路径section）
ANALYSIS_KEYWORDS = [
    '分析错了', '之前分析', '重新分析', '再分析', '分析结果',
    '根因', '原因是', '问题是', '发现是', '定位到', '确认是',
    '错误是', '实际是', '其实是'
]

# BUG ID 正则模式
BUG_ID_PATTERN = r'BUG_\d{14}'

# 核心基本信息字段（第1步：一次性收集）
CORE_FIELDS = {
    "product_line": "所属产品线（如 PMIC、车载充电器、移动电源等）",
    "chip_model": "芯片型号（如 SCV89601P 等）",
    "protocol_type": "协议类型（如 PD3.0、PD3.1、UFCS、QC 等）",
    "severity": "严重级别（仅选 Blocker/Critical/Major/Minor）",
    "mass_production": "是否量产环境（仅选是/否）",
}

# 问题描述信息字段（第2步：累积收集）
DESCRIPTION_FIELDS = {
    "description": "问题现象（详细描述发生了什么）",
}

# 复现与分析字段（第3步：确认收集）
ANALYSIS_FIELDS = {
    "trigger_condition": "触发条件（在什么情况下发生的）",
    "reproduce_rate": "复现概率（如 100% 必现、偶发、低概率等）",
    "root_cause_hypothesis": "初步根因假设（你觉得可能是什么原因）",
    "solution_tried": "已尝试的解决方案（你已经做了什么操作）"
}

# BUG 记录必填字段（合并）
REQUIRED_FIELDS = {**CORE_FIELDS, **DESCRIPTION_FIELDS, **ANALYSIS_FIELDS}

class BugDialogTool:
    """BUG 对话框工具类 - 负责用户交互和数据收集"""
    
    def __init__(self, ui: Optional[UI] = None, storage: Optional[BugStorage] = None):
        self.ui = ui or TerminalUI()
        self.storage = storage or FileStorage()
        self.required_fields = REQUIRED_FIELDS.copy()
        self.fallback_keywords = FALLBACK_KEYWORDS.copy()
        self.bugs_index: Dict[str, Dict[str, str]] = {}
        self._index_dirty = False  # 索引脏标记，优化文件写入
        
        # 初始化存储并加载索引
        self.storage.init()
        self._load_bugs_index()
    
    def _reply(self, raw_message: str, context: str = "") -> None:
        """对 ui.write 的拟人化封装：将系统消息通过 AI 改写后发送到对话框"""
        humanized = ai_humanize_reply(raw_message, context)
        self.ui.write(humanized)
    
    def _load_bugs_index(self) -> None:
        """加载 BUG 记录索引"""
        try:
            self.bugs_index = self.storage.load_index()
            self._index_dirty = False
        except Exception as e:
            self.ui.log(f"[提示] 索引加载异常：{e}，已重置索引")
            self.bugs_index = {}
            self._index_dirty = True
    
    def _save_bugs_index(self) -> None:
        """保存 BUG 记录索引（带脏标记优化）"""
        if not self._index_dirty:
            return
        if self.storage.save_index(self.bugs_index):
            self._index_dirty = False
        else:
            self.ui.log("[错误] 索引保存失败")
    
    def _generate_bug_id(self) -> str:
        """生成唯一 BUG ID"""
        return self.storage.generate_id()
    
    def _search_similar_bugs_ai(self, query_description: str) -> List[Dict[str, Any]]:
        """AI 语义搜索相似 BUG 记录"""
        return search_similar_bugs(
            self.bugs_index, 
            query_description, 
            MAX_SIMILAR_BUGS, 
            MAX_BUGS_FOR_SEARCH, 
            MAX_RETRY_COUNT
        )
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取有效关键词，用于兜底匹配"""
        if not text:
            return []
        text = re.sub(r'[^\w\s]', ' ', text).lower()
        words = text.split()
        keywords = [word for word in words if len(word) >= 2 and word not in STOP_WORDS]
        keywords.extend([kw for kw in BUG_CORE_KEYWORDS if kw in text])
        return list(set(keywords))
    
    def _search_similar_bugs_keyword(self, query_description):
        """兜底关键词匹配，优化相似原因描述"""
        similar_bugs = []
        query_keywords = self._extract_keywords(query_description)
        if not query_keywords:
            return []
        
        for bug_id, bug_info in self.bugs_index.items():
            full_text = f"{bug_info['title']} {bug_info['description']} {bug_info.get('product_line', '')} {bug_info.get('chip_model', '')}".lower()
            match_count = 0
            matched_words = []
            for kw in query_keywords:
                if kw in full_text:
                    match_count += 1
                    matched_words.append(kw)
            
            if match_count > 0:
                # 计算相似度百分比（基于关键词匹配数量）
                max_possible_matches = len(query_keywords)
                similarity_percentage = min(100, int((match_count / max_possible_matches) * 100)) if max_possible_matches > 0 else 0
                
                # 生成自然的相似原因
                if 'otg' in matched_words and '失败' in matched_words:
                    reason = "都与 OTG 功能失败相关"
                elif 'bc1' in matched_words and '失败' in matched_words:
                    reason = "都与 BC1.2 识别失败相关"
                elif len(matched_words) == 1:
                    reason = f"都包含{matched_words[0]}相关问题"
                else:
                    reason = f"匹配到核心关键词：{','.join(matched_words[:3])}"
                
                similar_bugs.append({
                    "id": bug_id,
                    "title": bug_info['title'],
                    "description": bug_info['description'],
                    "date": bug_info.get('date', '未知日期'),
                    "match_count": match_count,
                    "similarity_reason": reason,
                    "similarity_percentage": similarity_percentage
                })
        
        return sorted(similar_bugs, key=lambda x: x.get('match_count', 0), reverse=True)[:MAX_SIMILAR_BUGS]
    
    def _extract_tags(self, text: str) -> List[str]:
        """提取标签用于搜索优化"""
        return [tag for tag in BUG_CORE_KEYWORDS if tag in text.lower()]
    
    def _init_collect_data(self, initial_desc):
        """初始化收集数据字典"""
        collect_data = {}
        for field in self.required_fields.keys():
            collect_data[field] = "待补充"
        collect_data["description"] = initial_desc
        collect_data["images"] = []  # 图片路径列表
        collect_data["files"] = []   # 文件路径列表
        return collect_data
    
    def _check_collect_complete(self, collect_data):
        """检查是否所有字段都已收集完成"""
        for field, value in collect_data.items():
            if value == "待补充":
                return False
        return True
    
    def _get_missing_field(self, collect_data):
        """获取当前第一个待补充的字段"""
        for field, field_desc in self.required_fields.items():
            if collect_data[field] == "待补充":
                return field, field_desc.split("（")[0]
        return None, None
    
    def _check_has_fallback_statement(self, user_input):
        """检查是否包含兜底表述"""
        for keyword in self.fallback_keywords:
            if keyword in user_input:
                return True
        return False
    
    def _auto_fill_fallback_fields(self, collect_data: Dict[str, str]) -> Dict[str, str]:
        """自动填充剩余字段为暂未确定"""
        return {k: (v if v != "待补充" else AUTO_FILL_TEXT) for k, v in collect_data.items()}
    
    def _smart_input(self, prompt="你："):
        """智能输入，简化版本"""
        self.ui.log(prompt, end="")
        try:
            user_input = self.ui.read().strip()
            
            # 全局退出指令优先
            if user_input.lower() in ['exit', 'quit', '取消']:
                return "exit"
            if user_input == "完成":
                return "完成"
            
            return user_input
        
        except KeyboardInterrupt:
            return "exit"
        except Exception as e:
            self.ui.log(f"[错误] 输入异常：{str(e)}")
            return ""
    
    def _prompt_add_images(self, collect_data: Dict[str, Any], pending_images: List[str] = None) -> None:
        """提示用户添加图片，支持从 pending_images 获取或交互式输入"""
        image_paths = list(pending_images) if pending_images else []
        
        # 如果有待处理的图片，直接添加
        if image_paths:
            self.add_images(collect_data, image_paths)
            self.ui.log(f"📷 已添加 {len(image_paths)} 张图片")
            return
        
        # 否则交互式输入路径
        # 使用 ui.write 直接输出，避免 AI 拟人化的延迟导致输入时序问题
        self.ui.write("请粘贴图片或提供图片路径，每行一个，输入空行结束：")
        
        while True:
            path = self.ui.read("").strip()
            if not path:
                break
            # 处理 img: 前缀（从 API 传入的粘贴图片）
            if path.startswith("img:"):
                path = path[4:]
            if os.path.exists(path):
                image_paths.append(path)
                self.ui.log(f"✅ 已添加: {os.path.basename(path)}")
            else:
                self.ui.log(f"❌ 文件不存在: {path}")
        
        if image_paths:
            self.add_images(collect_data, image_paths)
            self.ui.log(f"📷 已添加 {len(collect_data.get('images', []))} 张图片")
        else:
            self.ui.log("ℹ️ 未添加图片")

    
    def _ai_extract_all_fields(self, user_input, collect_data):
        """AI 自动全字段提取，用户输入任何内容都自动匹配所有字段"""
        return ai_extract_all_fields(user_input, collect_data, self.required_fields)
    
    def _print_collect_status(self, collect_data: Dict[str, str]) -> None:
        """打印当前收集状态"""
        self.ui.log("\n📊 当前 BUG 信息收集状态：")
        self.ui.log("-" * 50)
        for field, field_desc in self.required_fields.items():
            field_name = field_desc.split("（")[0]
            value = collect_data[field]
            if value == "待补充":
                status = "❌ 待补充"
            elif value == AUTO_FILL_TEXT:
                status = "ℹ️  暂未确定"
            else:
                status = "✅ 已填充"
            self.ui.log(f"{status} {field_name}: {value}")
        self.ui.log("-" * 50)
    
    def _generate_question(self, missing_field, missing_field_name, collect_data):
        """生成自然提问"""
        return ai_generate_question(missing_field, missing_field_name, collect_data, self.required_fields[missing_field])
        
    def add_images(self, collect_data: Dict[str, Any], image_paths: List[str]) -> None:
        """添加图片到 BUG 记录"""
        if 'images' not in collect_data:
            collect_data['images'] = []
            
        for path in image_paths:
            if os.path.exists(path):
                collect_data['images'].append(path)
                self.ui.log(f"✅ 已添加图片: {os.path.basename(path)}")
            else:
                self.ui.log(f"❌ 图片不存在: {path}")
        
    def start_conversational_record(self, initial_description="", initial_images=None, initial_files=None):
        """用户主导的 BUG 记录流程 - 两阶段收集"""
        self.ui.log("\n" + "="*60)
        self.ui.log("🐞 AI 对话式 BUG 记录助手")
        self.ui.log("="*60)
        
        # 处理初始描述
        if not initial_description:
            self.ui.log("请输入 BUG 相关信息：")
            initial_description = self._smart_input(prompt="你：")
            if initial_description == "exit":
                self.ui.log("❌ 已退出 BUG 记录")
                return
            if not initial_description:
                self.ui.log("❌ 输入内容不能为空，已退出记录")
                return
        
        # 初始化收集数据
        collect_data = self._init_collect_data(initial_description)
        
        # 添加初始图片
        if initial_images:
            for img_path in initial_images:
                if os.path.exists(img_path):
                    collect_data['images'].append(img_path)
            if collect_data['images']:
                self.ui.log(f"📷 已添加 {len(collect_data['images'])} 张图片")
        
        # 添加初始文件
        if initial_files:
            for file_path in initial_files:
                if os.path.exists(file_path):
                    collect_data['files'].append(file_path)
            if collect_data['files']:
                self.ui.log(f"📄 已添加 {len(collect_data['files'])} 个文件")
        
        # 解析初始信息
        self.ui.log("📥 正在解析初始信息...")
        collect_data = self._ai_extract_all_fields(initial_description, collect_data)
        
        # AI 语义搜索相似 BUG
        self.ui.log("\n🔍 正在搜索历史相似 BUG...")
        similar_bugs = self._search_similar_bugs_ai(initial_description)
        similar_info = "无"
        if similar_bugs:
            similar_info = "已发现以下历史相似 BUG 供参考：\n"
            for bug in similar_bugs:
                similar_info += f"- {bug['id']} ({bug.get('date', '')}): {bug['title']}\n"
            self._reply(similar_info)
        else:
            self._reply("未发现历史相似 BUG，这是一个新问题。")
        
        # ==================== 阶段1: 一次性收集核心基本信息 ====================
        missing_core = []
        for field, field_desc in CORE_FIELDS.items():
            if collect_data.get(field) == "待补充":
                field_name = field_desc.split("（")[0]
                missing_core.append((field, field_name))
        
        if missing_core:
            fields_list = "\n".join([f"  {i}. 【{field_name}】" for i, (field, field_name) in enumerate(missing_core, 1)])
            self._reply(f"好的，接下来需要补充一些核心基本信息（一次性填写即可）：\n{fields_list}\n\n可以用「产品线: PMIC, 芯片型号: SCV89601P, ...」这样的格式填写，也可以输入 multi 进入多行模式")
            
            user_input = self._smart_input(prompt="> ")
            if user_input == "exit":
                self.ui.log("❌ 已退出 BUG 记录")
                return
            
            if user_input.lower() == "multi":
                self.ui.log("📝 多行模式，输入 ### 提交")
                lines = []
                while True:
                    line = self.ui.read("  ")
                    if line.strip() == "###":
                        break
                    lines.append(line)
                user_input = "\n".join(lines)
            
            if user_input and user_input != "完成":
                self.ui.log("📥 解析核心信息...")
                collect_data = self._ai_extract_all_fields(user_input, collect_data)
        
        # ==================== 阶段2: 累积收集问题描述（多条消息） ====================
        self._reply("接下来请补充问题描述，可以分多次输入，或直接粘贴图片。\n支持：文字描述、触发条件、分析假设、已尝试方案等。\n\n**指令说明：**\n- 输入「完成」结束描述进入下一步\n- 直接粘贴图片即可添加\n- 输入「exit」取消并退出")
        
        accumulated_descriptions = [initial_description]  # 累积所有描述
        
        while True:
            user_input = self._smart_input(prompt="> ")
            
            # 自动识别粘贴的图片（img: 前缀）
            if user_input.startswith("img:"):
                path = user_input[4:]
                if os.path.exists(path):
                    if 'images' not in collect_data:
                        collect_data['images'] = []
                    collect_data['images'].append(path)
                    self.ui.log(f"📷 已添加图片: {os.path.basename(path)}")
                else:
                    self.ui.log(f"❌ 图片文件不存在: {path}")
                continue
            
            # AI 语义识别用户意图
            action_options = """1. 完成描述，进入下一步
2. 取消并退出
3. 继续补充描述内容"""
            intent = ai_intent_recognize(
                user_input=user_input,
                options=action_options,
                scene_desc="用户正在补充BUG问题描述，可以选择完成、退出，或继续输入描述"
            )
            
            if intent == "2" or user_input.lower() in ["exit", "quit", "退出", "取消"]:
                self.ui.log("❌ 已退出 BUG 记录")
                return
            
            if intent == "1" or user_input in ["完成", "结束了", "done", "ok", "好的"]:
                break
            
            if user_input:
                # 累积描述
                accumulated_descriptions.append(user_input)
                self.ui.log("📥 解析补充信息...")
                collect_data = self._ai_extract_all_fields(user_input, collect_data)
                self.ui.log(f"✅ 已累积 {len(accumulated_descriptions)} 条描述，{len(collect_data.get('images', []))} 张图片")
        
        # 合并所有描述到 description 字段
        if len(accumulated_descriptions) > 1:
            full_description = "\n\n".join(accumulated_descriptions)
            collect_data['description'] = full_description
        
        # ==================== 阶段3: 确认复现信息和分析路径 ====================
        missing_analysis = []
        for field, field_desc in ANALYSIS_FIELDS.items():
            if collect_data.get(field) == "待补充":
                field_name = field_desc.split("（")[0]
                missing_analysis.append((field, field_name))
        
        if missing_analysis:
            fields_list = "\n".join([f"  {i}. 【{field_name}】" for i, (field, field_name) in enumerate(missing_analysis, 1)])
            self._reply(f"还需要补充一些复现和分析信息：\n{fields_list}\n\n可以用「触发条件: xxx, 复现概率: 100%必现, ...」的格式填写，输入 skip 可跳过（自动填充为暂未确定）")
            
            user_input = self._smart_input(prompt="> ")
            if user_input == "exit":
                self.ui.log("❌ 已退出 BUG 记录")
                return
            
            if user_input.lower() != "skip" and user_input:
                self.ui.log("📥 解析复现与分析信息...")
                collect_data = self._ai_extract_all_fields(user_input, collect_data)
        
        # 自动填充未完成字段
        for field in REQUIRED_FIELDS:
            if collect_data.get(field) == "待补充":
                collect_data[field] = AUTO_FILL_TEXT
        
        # ==================== 最终确认环节：AI 意图匹配 ====================
        self.ui.log("\n" + "="*60)
        self.ui.log("📋 最终 BUG 信息确认")
        self.ui.log("="*60)
        for field, field_desc in self.required_fields.items():
            field_name = field_desc.split("（")[0]
            value = collect_data[field]
            self.ui.log(f"【{field_name}】: {value}")
        
        # 显示附件图片数量
        image_count = len(collect_data.get('images', []))
        self.ui.log(f"【附件图片】: {image_count} 张")
        
        # 定义可选操作（使用带编号的字符串格式）
        confirm_options = """1. 确认以上信息无误，保存 BUG 记录
2. 修改某个字段的内容
3. 取消记录，不保存任何内容，返回主菜单"""
        
        self._reply("请确认以上信息是否正确：\n- 输入「确认」保存 BUG 记录\n- 输入「修改」修改某个字段\n- 输入「取消」不保存并返回主菜单")
        
        while True:
            user_input = self.ui.read("> ").strip()
            # 全局退出指令优先
            if user_input.lower() in ['exit', 'quit']:
                self.ui.log("❌ 已退出 BUG 记录")
                return
            
            # 使用 AI 意图识别（支持中英文模糊匹配）
            intent = ai_intent_recognize(
                user_input=user_input,
                options=confirm_options,
                scene_desc="当前处于 BUG 记录最终确认环节，用户需要选择确认保存、修改内容、还是取消记录"
            )
            
            # 处理识别结果（intent 返回的是编号字符串，如"1"、"2"、"3"）
            if intent == "1":  # confirm
                self.ui.log("✅ 已确认，开始保存记录")
                break
            elif intent == "2":  # modify
                self.ui.log("\n📖 可修改字段列表：")
                for field, field_desc in self.required_fields.items():
                    field_name = field_desc.split("（")[0]
                    self.ui.log(f"- {field}: {field_name}")
                modify_field = self.ui.read("\n请输入要修改的字段名：").strip()
                if modify_field in self.required_fields:
                    field_name = self.required_fields[modify_field].split("（")[0]
                    new_value = self.ui.read(f"请输入【{field_name}】的新内容：").strip()
                    collect_data[modify_field] = new_value
                    self.ui.log("✅ 修改成功，将重新展示完整信息")
                    # 重新展示信息
                    self.ui.log("\n" + "="*60)
                    self.ui.log("📋 最终 BUG 信息确认")
                    self.ui.log("="*60)
                    for field, field_desc in self.required_fields.items():
                        field_name = field_desc.split("（")[0]
                        self.ui.log(f"【{field_name}】: {collect_data[field]}")
                else:
                    self.ui.log("❌ 字段名不存在，请重新输入")
            elif intent == "3":  # cancel
                self.ui.log("❌ 已取消 BUG 记录，未保存任何内容")
                return
            else:
                # AI 识别失败，兜底提示
                self.ui.log("❌ 未识别到有效操作，请输入「确认」「修改」或「取消」")
        
        # 保存 BUG 记录
        bug_id = self._generate_bug_id()
        file_path = self._save_bug_record(bug_id, collect_data, similar_info)
        
        # 完成提示
        self.ui.log(f"\n🎉 BUG 记录已成功保存！")
        self.ui.log(f"🆔 BUG ID: {bug_id}")
        self.ui.log(f"📁 文件路径：{file_path}")
        return bug_id
    
    def _save_bug_record(self, bug_id, bug_data, similar_info):
        """保存符合 bug_template.md 模板的 Markdown 记录，更新索引"""
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 处理图片：复制到存储目录
        image_paths = bug_data.get('images', [])
        
        # 从描述中提取 img: 前缀的图片路径
        description = bug_data['description']
        inline_images = re.findall(r'img:([^\s\n]+)', description)
        
        # 从描述中提取 Markdown 格式的图片路径 ![](path)
        markdown_images = re.findall(r'!\[.*?\]\(([^\)]+)\)', description)
        
        # 合并所有图片路径（去重）
        all_image_paths = list(image_paths)
        for p in inline_images:
            if p not in all_image_paths and os.path.exists(p):
                all_image_paths.append(p)
        for p in markdown_images:
            if p not in all_image_paths and os.path.exists(p):
                all_image_paths.append(p)
        
        # 保存所有图片到本地目录
        saved_images = self.storage.save_images(bug_id, all_image_paths)
        
        # 构建原始路径到本地路径的映射
        path_mapping = {}
        for i, orig_path in enumerate(all_image_paths):
            if i < len(saved_images):
                path_mapping[orig_path] = saved_images[i]
        
        # 替换描述中的 img: 路径为本地保存的路径
        def replace_img_path(match):
            orig_path = match.group(1)
            local_path = path_mapping.get(orig_path, orig_path)
            return f"![]({local_path})"
        
        description = re.sub(r'img:([^\s\n]+)', replace_img_path, description)
        
        # 替换描述中的 Markdown 图片路径为本地保存的路径
        def replace_markdown_img_path(match):
            alt_text = match.group(1)
            orig_path = match.group(2)
            local_path = path_mapping.get(orig_path, orig_path)
            return f"![]({local_path})"
        
        description = re.sub(r'!\[(.*?)\]\(([^\)]+)\)', replace_markdown_img_path, description)
        
        # 生成附件图片 Markdown（只显示非内联的图片）
        images_markdown = ""
        inline_saved = len(inline_images)
        attachment_images = saved_images[:len(image_paths)] if image_paths else []
        if attachment_images:
            images_markdown = "\n\n**附件截图**\n\n"
            for i, img_path in enumerate(attachment_images, 1):
                images_markdown += f"![截图{i}]({img_path})\n"
        
        # 处理文件：复制到存储目录
        file_paths = bug_data.get('files', [])
        files_markdown = ""
        if file_paths:
            saved_files = self.storage.save_files(bug_id, file_paths)
            if saved_files:
                files_markdown = "\n\n**附件文件**\n\n"
                for rel_path, original_name in saved_files:
                    files_markdown += f"- [{original_name}]({rel_path})\n"
        
        # 映射字段到模板格式
        # 对于模板中但当前数据没有的字段，使用默认值
        firmware_version = "暂未确定"
        reporter = "AI 记录工具"
        secondary_effect = "暂未发现"
        pre_condition = bug_data.get('trigger_condition', '暂未确定')
        steps = "待补充详细触发步骤"
        reproduce_condition = "待补充复现依赖条件"
        surface_cause = bug_data.get('root_cause_hypothesis', '暂未确定')
        root_cause = "待深入分析深层原因"
        solution_tried = bug_data.get('solution_tried', '暂未尝试')
        patch = solution_tried
        long_term_solution = "待制定长期方案"
        debug_steps = "待补充排查路径"
        tags = "待补充标签"
        
        md_content = f"""# 🐞 Bug 记录

---

## 1 核心基本信息

| 字段         | 内容                    |
| ------------ | ----------------------- |
| Bug ID       | {bug_id}              |
| 产品线       | {bug_data['product_line']} |
| 芯片型号     | {bug_data['chip_model']} |
| 协议类型     | {bug_data.get('protocol_type', '暂未确定')} |
| 固件版本     | {firmware_version}    |
| 严重级别     | {bug_data['severity']} |
| 是否量产环境 | {bug_data.get('mass_production', '暂未确定')} |
| 提报人/时间  | {reporter} / {current_date} |

---

## 2 问题现象

**核心现象（必填）**

{description}{images_markdown}{files_markdown}

**衍生现象（可选）**

{secondary_effect}

---

## 3 复现核心信息

### 触发条件
- **前置条件**：{pre_condition}
- **触发步骤**：{steps}

### 复现关键
- **复现概率**：{bug_data['reproduce_rate']}
- **复现依赖**：{reproduce_condition}

---

## 4 分析过程

### 4.1 第 1 次分析
- **时间**：{current_date}
- **分析内容**：{surface_cause}
- **行动项**：{solution_tried}

---
"""
        
        # 使用存储层保存 BUG 记录
        index_entry = {
            'title': bug_data['description'][:60] + ('...' if len(bug_data['description'])>60 else ''),
            'description': bug_data['description'],
            'date': current_date
        }
        file_path = self.storage.save_bug(bug_id, md_content, index_entry)
        
        # 更新索引
        self.bugs_index[bug_id] = index_entry
        self._index_dirty = True
        self._save_bugs_index()
        
        return file_path
    
    def list_all_bugs(self):
        """列出所有 BUG 记录"""
        if not self.bugs_index:
            self.ui.log("\n📭 暂无 BUG 记录")
            return
        self.ui.log("\n📋 所有 BUG 记录列表：")
        self.ui.log("-"*60)
        for bug_id, bug_info in self.bugs_index.items():
            self.ui.log(f"🆔 {bug_id}")
            self.ui.log(f"   日期：{bug_info.get('date', '未知日期')}")
            self.ui.log(f"   标题：{bug_info['title']}")
            self.ui.log("-"*60)
    
    def search_bugs(self, query=""):
        """AI 语义搜索 BUG 记录"""
        if not query:
            query = self.ui.read("\n请输入搜索关键词或 BUG 描述：").strip()
        if not query:
            self.ui.log("❌ 搜索内容不能为空")
            return
        
        self.ui.log(f"\n🔍 正在 AI 语义搜索包含「{query}」的 BUG 记录...")
        similar_bugs = self._search_similar_bugs_ai(query)
        
        if not similar_bugs:
            self.ui.log(f"\n📭 未找到相似的 BUG 记录")
            return
        
        self.ui.log(f"\n🔍 找到 {len(similar_bugs)} 条相似的 BUG 记录：")
        self.ui.log("-"*60)
        for bug in similar_bugs:
            self.ui.log(f"🆔 {bug['id']}")
            self.ui.log(f"   日期：{bug.get('date', '未知日期')}")
            self.ui.log(f"   标题：{bug['title']}")
            self.ui.log(f"   相似原因：{bug['similarity_reason']}")
            self.ui.log("-"*60)
    
    def get_bug_detail(self, bug_id=""):
        """查看 BUG 详情"""
        if not bug_id:
            bug_id = self.ui.read("\n请输入要查看的 BUG ID: ").strip()
        if not bug_id:
            self.ui.log("❌ BUG ID 不能为空")
            return
        
        if bug_id not in self.bugs_index:
            self.ui.log(f"❌ 未找到 ID 为「{bug_id}」的 BUG 记录")
            return
        
        # 使用存储层获取 BUG 记录
        content = self.storage.get_bug(bug_id)
        if not content:
            self.ui.log(f"❌ BUG 记录文件不存在")
            return
        
        self.ui.write(content)
    
    def print_help(self):
        """打印帮助说明"""
        help_text = """## 📖 BUG 记录工具帮助说明

**核心功能：**
- 直接输入 BUG 描述，我会先匹配历史记录，再询问是否新建
- 告诉我「某条 BUG 有新进展」，可追加更新已有记录
- 所有输入都支持口语化，AI 会自动识别你的意图

**快捷指令：**
- 列出所有记录 / 查看某条 BUG 详情
- 查看帮助 / 退出工具"""
        self._reply(help_text)
    
    def _is_valid_bug_input(self, user_input: str) -> bool:
        """判断用户输入是否为有效 BUG 描述"""
        if not user_input or len(user_input) < 3:
            return False
        input_lower = user_input.lower()
        return any(kw in input_lower for kw in BUG_CORE_KEYWORDS)
    
    def _extract_bug_id(self, user_input: str) -> Optional[str]:
        """从用户输入中提取 BUG ID"""
        match = re.search(BUG_ID_PATTERN, user_input)
        return match.group(0) if match else None
    
    def _is_update_intent(self, user_input: str) -> bool:
        """判断是否为更新意图"""
        input_lower = user_input.lower()
        return any(kw in input_lower for kw in UPDATE_KEYWORDS)
    
    def _is_analysis_update(self, user_input: str) -> bool:
        """判断是否为分析类更新（应插入分析路径section）"""
        return any(kw in user_input for kw in ANALYSIS_KEYWORDS)
    
    def _append_analysis(self, bug_id: str, description: str) -> bool:
        """追加分析到 BUG 记录的分析过程section（追加到文件末尾）"""
        content = self.storage.get_bug(bug_id)
        if not content:
            self.ui.log(f"❌ BUG 记录文件不存在")
            return False
        
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 从描述中提取结论（关键词后的内容作为结论）
        conclusion = "待补充"
        conclusion_keywords = ['具体的错误是', '错误是', '原因是', '问题是', '实际是', '其实是', '确认是', '发现是', '定位到']
        for kw in conclusion_keywords:
            if kw in description:
                parts = description.split(kw, 1)
                if len(parts) > 1 and parts[1].strip():
                    conclusion = parts[1].strip()
                    break
        
        # 从已有内容中提取已尝试方案作为行动项
        action_item = "待补充"
        if "**行动项**：" in content:
            # 找到最后一次分析的行动项
            matches = list(re.finditer(r'\*\*行动项\*\*：([^\n]+)', content))
            if matches:
                last_action = matches[-1].group(1).strip()
                if last_action not in ['暂未尝试', '待补充', '']:
                    action_item = last_action
        
        # 查找已有的分析次数
        analysis_pattern = r'### 4\.(\d+) 第 \d+ 次分析'
        matches = list(re.finditer(analysis_pattern, content))
        
        if matches:
            last_num = int(matches[-1].group(1))
            next_num = last_num + 1
        else:
            next_num = 1
        
        # 追加到文件末尾
        new_analysis = f"""

### 4.{next_num} 第 {next_num} 次分析
- **时间**：{current_time}
- **分析内容**：{conclusion}
- **行动项**：{action_item}

---
"""
        content = content.rstrip() + new_analysis
        
        # 保存更新后的内容
        if self.storage.save_bug_content(bug_id, content):
            self.ui.log(f"✅ 分析已添加到 {bug_id} 的分析过程")
            return True
        return False
    
    def _handle_update_without_id(self, user_input: str, initial_images: List[str] = None, initial_files: List[str] = None) -> Optional[str]:
        """处理没有明确 BUG ID 的更新意图"""
        self.ui.log("\n🔍 检测到更新意图，正在搜索相关 BUG 记录...")
        
        # 搜索相似 BUG
        similar_bugs = self._search_similar_bugs_ai(user_input)
        
        if not similar_bugs:
            # 尝试关键词兜底匹配
            similar_bugs = self._search_similar_bugs_keyword(user_input)
        
        if not similar_bugs:
            self.ui.log("❌ 未找到相关的 BUG 记录")
            self._reply("没有找到相关的 BUG 记录，请提供更具体的描述，或者直接告诉我 BUG ID（如 BUG_20260310103121）")
            return None
        
        # 显示匹配结果，让用户选择
        output = "找到以下可能相关的 BUG 记录：\n\n"
        for idx, bug in enumerate(similar_bugs, 1):
            similarity = bug.get('similarity_percentage', 0)
            output += f"{idx}. 🆔 {bug['id']} | 日期：{bug.get('date', '未知')}\n"
            output += f"   标题：{bug['title']}\n"
            output += f"   相似度：{similarity}% | 原因：{bug.get('similarity_reason', '')}\n\n"
        output += f"请告诉我要更新哪一条（输入编号 1-{len(similar_bugs)}），或输入「取消」返回。"
        self._reply(output)
        
        while True:
            choice = self.ui.read("选择: ").strip()
            
            if choice.lower() in ['exit', 'quit', '取消', '返回']:
                self.ui.log("🔙 已取消更新操作")
                return None
            
            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(similar_bugs):
                    selected_bug = similar_bugs[num - 1]
                    bug_id = selected_bug['id']
                    self.ui.log(f"\n✅ 已选择：{bug_id}")
                    # 提取更新描述（移除更新关键词，保留实际内容）
                    update_desc = user_input
                    for kw in UPDATE_KEYWORDS:
                        update_desc = update_desc.replace(kw, '')
                    update_desc = update_desc.strip()
                    return self.update_bug_record(bug_id, update_desc, initial_images, initial_files)
                else:
                    self.ui.log(f"❌ 请输入 1-{len(similar_bugs)} 之间的数字")
            else:
                self.ui.log("❌ 请输入有效的编号或「取消」")
    
    def update_bug_record(self, bug_id: str, update_description: str = "", initial_images: List[str] = None, initial_files: List[str] = None):
        """更新已有 BUG 记录 - 支持多次输入累积"""
        # 检查 BUG 是否存在
        if bug_id not in self.bugs_index:
            self.ui.log(f"❌ 未找到 BUG 记录：{bug_id}")
            return None
        
        bug_info = self.bugs_index[bug_id]
        self.ui.log(f"\n📝 更新 BUG 记录：{bug_id}")
        self.ui.log(f"📌 原标题：{bug_info['title']}")
        self.ui.log(f"📅 创建时间：{bug_info.get('date', '未知')}")
        self.ui.log("="*60)
        
        # 累积收集更新内容
        accumulated_content = []
        accumulated_images = list(initial_images) if initial_images else []
        accumulated_files = list(initial_files) if initial_files else []
        
        # 如果有初始描述，先加入
        if update_description:
            accumulated_content.append(update_description)
            self.ui.log(f"📥 初始内容：{update_description}")
        
        # 提示用户继续输入
        self._reply("好的，请继续输入更新内容，可以分多次输入。\n\n**指令说明：**\n- 输入「完成」保存更新\n- 输入「img」添加图片\n- 输入「exit」取消并退出\n- 输入「multi」进入多行模式（输入###结束）")
        
        while True:
            user_input = self._smart_input(prompt="> ")
            
            # AI 语义识别用户意图
            action_options = """1. 完成并保存更新
2. 取消并退出
3. 添加图片
4. 进入多行输入模式
5. 继续输入更新内容"""
            intent = ai_intent_recognize(
                user_input=user_input,
                options=action_options,
                scene_desc="用户正在更新BUG记录，可以选择完成保存、退出、添加图片、进入多行模式，或继续输入内容"
            )
            
            if intent == "2" or user_input.lower() in ["exit", "quit", "退出", "取消"]:
                self.ui.log("❌ 已取消更新")
                return None
            
            if intent == "1" or user_input in ["完成", "结束了", "done", "ok", "好的", "保存"]:
                break
            
            # 处理粘贴图片（img: 前缀）
            if user_input.startswith("img:"):
                path = user_input[4:].strip()
                if os.path.exists(path):
                    accumulated_images.append(path)
                    self.ui.log(f"🖼️ 已添加图片: {os.path.basename(path)}")
                    self.ui.log(f"✅ 当前累积 {len(accumulated_content)} 条内容，{len(accumulated_images)} 张图片")
                else:
                    self.ui.log(f"❌ 图片不存在: {path}")
                continue
            
            # 处理文本文件（file: 前缀）
            if user_input.startswith("file:"):
                path = user_input[5:].strip()
                if os.path.exists(path):
                    accumulated_files.append(path)
                    self.ui.log(f"📄 已添加文件: {os.path.basename(path)}")
                    self.ui.log(f"✅ 当前累积 {len(accumulated_content)} 条内容，{len(accumulated_images)} 张图片，{len(accumulated_files)} 个文件")
                else:
                    self.ui.log(f"❌ 文件不存在: {path}")
                continue
            
            if user_input.lower() == "img":
                # 添加图片
                self._reply("请输入图片路径，输入空行结束：")
                while True:
                    path = self.ui.read("图片: ").strip()
                    if not path:
                        break
                    if path.startswith("img:"):
                        path = path[4:]
                    if os.path.exists(path):
                        accumulated_images.append(path)
                        self.ui.log(f"✅ 已添加: {os.path.basename(path)}")
                    else:
                        self.ui.log(f"❌ 文件不存在: {path}")
                continue
            
            if user_input.lower() == "multi":
                self.ui.log("📝 多行模式，输入 ### 提交")
                lines = []
                while True:
                    line = self.ui.read("  ")
                    if line.strip() == "###":
                        break
                    lines.append(line)
                user_input = "\n".join(lines)
            
            if user_input:
                accumulated_content.append(user_input)
                self.ui.log(f"✅ 已累积 {len(accumulated_content)} 条内容，{len(accumulated_images)} 张图片，{len(accumulated_files)} 个文件")
        
        # 合并所有内容
        if not accumulated_content and not accumulated_images and not accumulated_files:
            self.ui.log("❌ 未输入任何内容")
            return None
        
        full_content = "\n\n".join(accumulated_content)
        
        # 判断是分析类更新还是普通进展更新
        if self._is_analysis_update(full_content):
            self._append_analysis(bug_id, full_content)
        else:
            self._append_progress(bug_id, full_content, accumulated_images, accumulated_files)
        
        return bug_id
    
    def _append_progress(self, bug_id: str, description: str = "", images: List[str] = None, files: List[str] = None):
        """追加进展到 BUG 记录"""
        if not description and not images and not files:
            self._reply("请输入新的进展内容：")
            description = self.ui.read("进展内容: ").strip()
        
        if not description and not images and not files:
            self.ui.log("❌ 进展内容不能为空")
            return
        
        # 处理图片
        saved_images = []
        if images:
            saved_images = self.storage.save_images(bug_id, images)
        
        # 处理文件
        saved_files = []
        if files:
            saved_files = self.storage.save_files(bug_id, files)
        
        # 生成进展内容
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        progress_content = f"\n\n---\n\n## 📌 更新进展 ({current_time})\n\n{description}\n" if description else f"\n\n---\n\n## 📌 更新进展 ({current_time})\n"
        
        if saved_images:
            progress_content += "\n### 附加图片\n"
            for i, img_path in enumerate(saved_images, 1):
                progress_content += f"![{i}]({img_path})\n"
        
        if saved_files:
            progress_content += "\n### 附件文件\n"
            for rel_path, original_name in saved_files:
                progress_content += f"- [{original_name}]({rel_path})\n"
        
        # 追加到文件
        if self.storage.append_progress(bug_id, progress_content):
            self.ui.log(f"✅ 进展已追加到 {bug_id}")
            
            # 更新索引中的时间
            self.bugs_index[bug_id]['last_update'] = current_time
            self._index_dirty = True
            self._save_bugs_index()
        else:
            self.ui.log("❌ 追加进展失败")
    
    def _prompt_add_images_to_bug(self, bug_id: str):
        """提示用户添加图片到已有 BUG"""
        self._reply(f"请提供要添加到 {bug_id} 的图片路径，每行一个，输入空行结束：")
        
        image_paths = []
        while True:
            path = self.ui.read("图片路径: ").strip()
            if not path:
                break
            # 处理 img: 前缀（从 API 传入）
            if path.startswith("img:"):
                path = path[4:]
            if os.path.exists(path):
                image_paths.append(path)
                self.ui.log(f"✅ 已添加: {os.path.basename(path)}")
            else:
                self.ui.log(f"❌ 文件不存在: {path}")
        
        if image_paths:
            saved_images = self.storage.save_images(bug_id, image_paths)
            if saved_images:
                # 生成图片追加内容
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                img_content = f"\n\n---\n\n## 🖼️ 追加图片 ({current_time})\n\n"
                for i, img_path in enumerate(saved_images, 1):
                    img_content += f"![{i}]({img_path})\n"
                
                self.storage.append_progress(bug_id, img_content)
                self.ui.log(f"📷 已添加 {len(saved_images)} 张图片到 {bug_id}")
        else:
            self.ui.log("ℹ️ 未添加图片")
    
    def handle_bug_description(self, bug_description, initial_images=None, initial_files=None):
        """处理用户输入的 BUG 描述：支持交互式流程"""
        self.ui.log(f"\n🔍 检测到 BUG 描述，正在匹配历史相似记录...")
        
        # AI 语义匹配历史记录
        similar_bugs = self._search_similar_bugs_ai(bug_description)
        if similar_bugs:
            output = "找到以下历史相似 BUG 记录：\n\n"
            for idx, bug in enumerate(similar_bugs, 1):
                similarity_percentage = bug.get('similarity_percentage', 0)
                output += f"{idx}. 🆔 {bug['id']} | 日期：{bug['date']} | 相似度：{similarity_percentage}%\n"
                output += f"   标题：{bug['title']}\n"
                output += f"   相似原因：{bug['similarity_reason']}\n\n"
            
            # 提示操作选项
            for idx in range(1, len(similar_bugs)+1):
                output += f"  输入 {idx} 查看第{idx}条 BUG 的详细记录\n"
            output += f"  输入「新建」创建新 BUG 记录\n"
            output += f"  输入「返回」回到主菜单"
            self._reply(output)
            
            # 等待用户选择
            # 构建选项列表（动态根据相似 BUG 数量）
            view_options = "\n".join([f"{idx}. 查看第{idx}条 BUG 的详细记录（{bug['id']}）" for idx, bug in enumerate(similar_bugs, 1)])
            choice_options = f"""{view_options}
{len(similar_bugs)+1}. 新建 BUG 记录
{len(similar_bugs)+2}. 返回主菜单"""
            new_idx = len(similar_bugs) + 1
            back_idx = len(similar_bugs) + 2

            while True:
                user_input = self.ui.read("> ").strip()
                if not user_input:
                    continue

                # 兜底：如果只有一条相似BUG，用户输入"查看"/"看"等，默认查看第一条
                if len(similar_bugs) == 1 and user_input in ['查看', '看', '看看', '详情', '详细']:
                    self.get_bug_detail(bug_id=similar_bugs[0]['id'])
                    return None

                intent = ai_intent_recognize(
                    user_input=user_input,
                    options=choice_options,
                    scene_desc=f"用户正在查看相似 BUG 列表，可以选择查看某条详细记录、新建 BUG 或返回主菜单"
                )

                if intent and intent.isdigit():
                    num = int(intent)
                    if 1 <= num <= len(similar_bugs):
                        self.get_bug_detail(bug_id=similar_bugs[num-1]['id'])
                        return None
                    elif num == new_idx:
                        self.ui.log("\n📝 进入新建 BUG 记录模式")
                        return self.start_conversational_record(initial_description=bug_description, initial_images=initial_images, initial_files=initial_files)
                    elif num == back_idx:
                        self.ui.log("\n🔙 返回主菜单")
                        return None

                self._reply("未识别到你的意图。请直接输入编号（如 1），或输入「新建」创建新记录，或输入「返回」回到主菜单。")
        else:
            self._reply("没有找到历史相似 BUG 记录，看起来这是一个新问题。\n- 输入「新建」创建新 BUG 记录\n- 输入「返回」回到主菜单")
            choice_options = """1. 新建 BUG 记录
2. 返回主菜单"""
            while True:
                user_input = self.ui.read("> ").strip()
                if not user_input:
                    continue

                # 兜底关键词匹配
                if user_input in ['新建', '创建', '新', 'yes', 'y', '是', '好']:
                    self.ui.log("\n📝 进入新建 BUG 记录模式")
                    return self.start_conversational_record(initial_description=bug_description, initial_images=initial_images, initial_files=initial_files)
                if user_input in ['返回', 'back', '取消', 'no', 'n', '否', '不']:
                    self.ui.log("\n🔙 返回主菜单")
                    return None

                intent = ai_intent_recognize(
                    user_input=user_input,
                    options=choice_options,
                    scene_desc="未找到相似 BUG，用户选择是否新建 BUG 记录或返回主菜单"
                )

                if intent == "1":
                    self.ui.log("\n📝 进入新建 BUG 记录模式")
                    return self.start_conversational_record(initial_description=bug_description, initial_images=initial_images, initial_files=initial_files)
                elif intent == "2":
                    self.ui.log("\n🔙 返回主菜单")
                    return None

                self._reply("未识别到你的意图。请输入「新建」创建新记录，或输入「返回」回到主菜单。")
        
        return None

class BugRecord():
    def __init__(self, ui: UI = None):
        self.tool = BugDialogTool(ui)
        self._pending_images = []  # 待添加的图片路径列表
        self._pending_files = []   # 待添加的文本文件内容列表

    def add_pending_image(self, image_path: str) -> str:
        """添加待处理的图片"""
        if os.path.exists(image_path):
            self._pending_images.append(image_path)
            return f"✅ 已添加图片: {os.path.basename(image_path)}（当前共 {len(self._pending_images)} 张）"
        return f"❌ 图片不存在: {image_path}"

    def add_pending_file(self, file_path: str) -> str:
        """添加待处理的文本文件（保存路径）"""
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            self._pending_files.append(file_path)
            return f"✅ 已添加文件: {filename}（当前共 {len(self._pending_files)} 个）"
        return f"❌ 文件不存在: {file_path}"

    def get_pending_images(self) -> List[str]:
        """获取并清空待处理的图片"""
        images = self._pending_images.copy()
        self._pending_images = []
        return images

    def get_pending_files(self) -> List[str]:
        """获取并清空待处理的文件路径"""
        files = self._pending_files.copy()
        self._pending_files = []
        return files

    def run(self, user_input):
        # 正常模式，等待用户输入
        user_input = user_input.strip()
        
        if user_input == "":
            return
        
        # 所有输入统一通过 AI 语义识别处理
        main_menu_options = """1. 列出所有已保存的 BUG 记录
2. 查看指定 BUG ID 的详细记录
3. 查看帮助说明、功能列表、你能做什么、有什么功能、使用说明
4. 退出工具
5. 更新 BUG 记录
6. 记录新的 BUG"""
        
        main_intent = ai_intent_recognize(
            user_input=user_input,
            options=main_menu_options,
            scene_desc="当前处于 BUG 记录工具主菜单，用户可以选择查看列表、查看详情、查看帮助、退出工具、更新已有 BUG 记录，或者描述一个新的 BUG 问题"
        )
        
        # 处理主菜单意图识别结果
        if main_intent == "1":  # list
            self.tool.list_all_bugs()
            return
        elif main_intent == "2":  # detail
            self.tool.get_bug_detail()
            return
        elif main_intent == "3":  # help
            self.tool.print_help()
            return
        elif main_intent == "4":  # exit
            self.tool.ui.log("👋 感谢使用，再见！")
            return
        elif main_intent == "5":  # update
            # 进入 BUG 更新流程
            pending_images = self.get_pending_images()
            pending_files = self.get_pending_files()
            self.tool._handle_update_without_id(user_input, pending_images, pending_files)
            return
        elif main_intent == "6":  # new bug
            # 先搜索相似 BUG，让用户选择查看或新建
            pending_images = self.get_pending_images()
            pending_files = self.get_pending_files()
            self.tool.handle_bug_description(bug_description=user_input, initial_images=pending_images, initial_files=pending_files)
            return
        
        # 兜底：如果 AI 识别失败，默认尝试作为 BUG 描述处理（先搜索相似 BUG）
        pending_images = self.get_pending_images()
        pending_files = self.get_pending_files()
        self.tool.handle_bug_description(bug_description=user_input, initial_images=pending_images, initial_files=pending_files)
    
if __name__ == "__main__":
    ui = TerminalUI()
    bugrecord = BugRecord(ui)
    
    ui.log("🐞 BUG 记录工具已启动，输入 help 查看帮助")
    ui.log("提示：使用异步输入系统，可以外部推送输入")
    
    while True:
        # 使用异步输入
        user_input = input("\nBUG 工具> ")
        # ui.push_input(user_input)
        
        bugrecord.run(user_input)