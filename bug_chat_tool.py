#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI对话式BUG记录工具 - 打印逻辑修复版
核心修复：
1. 彻底解决相似BUG检索完成后，先出输入框、不打印结果的问题
2. 内容打印和输入提示严格绑定，先出完整结果+操作选项，再提示输入
3. 优化状态机自动推进逻辑，初始化后自动完成内容打印，无需用户触发
4. 补全截断的代码，修复索引date字段缺失问题
5. 优化交互逻辑，避免输入和内容脱节
"""

import os
import json
import re
import datetime
import sys
import threading
from llm import llm

# 全局配置
LLM_TIMEOUT = 100  # LLM调用超时时间
AUTO_FILL_TEXT = "暂未确定"  # 兜底填充文本
MAX_SIMILAR_BUGS = 3  # 最多返回的相似BUG数量

# BUG核心特征关键词（用于识别BUG描述）
BUG_CORE_KEYWORDS = [
    'bug', '故障', '失败', '异常', '报错', '触发', '复现', '中断',
    '芯片', '协议', 'pd', 'ufcs', 'qc', 'otg', 'pmic', '电压', '电流',
    '时序', '状态机', '死机', '重启', '不工作', '无响应', '跳变', '不稳定',
    '识别', '协商', '通信', '超时', '丢包', '复位', '溢出', '下溢'
]

# 无意义过滤词（关键词匹配时过滤）
STOP_WORDS = ['的', '了', '是', '我', '有', '一个', '问题', '遇到', '这个', '什么', '在', '和', '就', '都']

class TimeoutException(Exception):
    """超时异常"""
    pass

class BugDialogTool:
    def __init__(self):
        self.llm = llm()
        self.bugs_dir = "bug_records"
        # 全局统一字段配置 - 适配bug_template.md模板
        self.required_fields = {
            "description": "问题现象（详细描述发生了什么，对应模板中的核心现象）",
            "product_line": "所属产品线（如PMIC、车载充电器、移动电源等）",
            "chip_model": "芯片型号（如SCV89601P等）",
            "protocol_type": "协议类型（如PD3.0、PD3.1、UFCS、QC等）",
            "severity": "严重级别（仅选Blocker/Critical/Major/Minor）",
            "mass_production": "是否量产环境（仅选是/否）",
            "trigger_condition": "触发条件（在什么情况下发生的，对应模板中的前置条件）",
            "reproduce_rate": "复现概率（如100%必现、偶发、低概率等）",
            "environment": "运行环境（如温度、电压、测试工具等，对应模板中的硬件环境）",
            "root_cause_hypothesis": "初步根因假设（你觉得可能是什么原因，对应模板中的表层原因）",
            "solution_tried": "已尝试的解决方案（你已经做了什么操作，对应模板中的临时修复）"
        }
        # 兜底表述关键词
        self.fallback_keywords = [
            "其他都暂未确定", "其余都待定", "其他都不确定", "剩下的都不知道",
            "其他暂无", "其余都未确定", "其他都没定", "剩下的暂未确定"
        ]
        self.bugs_index = {}
        
        # 创建目录
        if not os.path.exists(self.bugs_dir):
            os.makedirs(self.bugs_dir)
        
        # 加载索引
        self._load_bugs_index()
    
    def _load_bugs_index(self):
        """加载BUG记录索引"""
        index_file = os.path.join(self.bugs_dir, "bugs_index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    self.bugs_index = json.load(f)
            except Exception as e:
                print(f"[提示] 索引加载异常: {e}，已重置索引", flush=True)
                self.bugs_index = {}
        else:
            self.bugs_index = {}
    
    def _save_bugs_index(self):
        """保存BUG记录索引"""
        index_file = os.path.join(self.bugs_dir, "bugs_index.json")
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(self.bugs_index, f, ensure_ascii=False, indent=2)
    
    def _generate_bug_id(self):
        """生成唯一BUG ID"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"BUG_{timestamp}"
    
    def _extract_json_from_text(self, text):
        """强鲁棒性JSON提取，彻底解决格式报错"""
        if not text or not isinstance(text, str):
            return None
        
        text = text.strip()
        # 优先匹配数组（相似BUG搜索需要）
        array_pattern = r'\[[\s\S]*\]'
        array_matches = re.findall(array_pattern, text)
        for match in array_matches:
            try:
                match = re.sub(r',\s*([}\]])', r'\1', match)
                parsed = json.loads(match)
                if isinstance(parsed, list):
                    return parsed
            except:
                continue
        
        # 匹配JSON对象
        obj_pattern = r'\{[\s\S]*\}'
        obj_matches = re.findall(obj_pattern, text)
        for match in obj_matches:
            try:
                match = re.sub(r',\s*([}\]])', r'\1', match)
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    return parsed
            except:
                continue
        
        return None
    
    def _llm_call_with_timeout(self, prompt):
        """带超时的LLM调用，避免永久卡死"""
        result = None
        exception = None

        def llm_worker():
            nonlocal result, exception
            try:
                result = self.llm.ask_llm(prompt)
            except Exception as e:
                exception = e

        thread = threading.Thread(target=llm_worker, daemon=True)
        thread.start()
        thread.join(timeout=LLM_TIMEOUT)

        if thread.is_alive():
            raise TimeoutException(f"LLM调用超时，超过{LLM_TIMEOUT}秒无响应")
        if exception:
            raise exception
        if not result:
            raise ValueError("LLM返回空内容")
        return result
    
    def _call_llm_safely(self, prompt, expected_format="json"):
        """安全调用LLM，带超时、重试、强鲁棒性解析"""
        max_retries = 2
        for retry in range(max_retries):
            try:
                response = self._llm_call_with_timeout(prompt)
                if expected_format == "json":
                    parsed_data = self._extract_json_from_text(response)
                    if parsed_data is None:
                        raise ValueError("未找到有效JSON格式内容")
                    return parsed_data
                else:
                    return response.strip()
            except Exception as e:
                print(f"[警告] 第{retry+1}次调用失败: {str(e)}", flush=True)
                if retry < max_retries - 1:
                    print("[进度] 2秒后重试...", flush=True)
                    import time
                    time.sleep(2)
        
        print(f"[错误] AI调用多次失败", flush=True)
        return None
    
    # ==================== 核心升级：通用AI意图识别函数 ====================
    def _ai_intent_recognize(self, user_input, options, scene_desc):
        """
        通用AI意图识别：所有用户输入都通过这个函数匹配操作
        :param user_input: 用户输入的文本
        :param options: 可选操作字典，格式：{"操作指令": "操作描述"}
        :param scene_desc: 当前场景描述，告诉AI当前在做什么
        :return: 匹配到的操作指令，匹配失败返回None
        """
        if not user_input or not options:
            return None
        
        # 先做快速匹配：用户输入直接匹配指令key，不走AI，提升速度
        input_lower = user_input.strip().lower()
        for cmd in options.keys():
            if input_lower == cmd.lower():
                return cmd
        
        # 检查是否是BUG ID格式（支持带前缀和不带前缀）
        bug_id_to_check = user_input
        if not user_input.startswith('BUG_') and user_input.isdigit() and len(user_input) == 14:
            # 尝试添加前缀
            bug_id_to_check = f"BUG_{user_input}"
        
        if bug_id_to_check in self.bugs_index:
            # 直接查看指定BUG详情
            return bug_id_to_check
        
        # 快速匹配失败，走AI意图识别
        prompt = f"""
你是一个专业的用户意图识别专家，需要根据用户输入，匹配最符合的操作指令。

【当前场景】
{scene_desc}

【可选操作指令及说明】
{json.dumps(options, ensure_ascii=False, indent=2)}

【用户输入】
{user_input}

【严格规则】
1. 仅输出匹配到的操作指令，必须是上面【可选操作指令】里的key，绝对不能输出其他内容
2. 如果用户输入和多个操作匹配，选最符合的一个
3. 如果完全匹配不到任何操作，仅输出"none"，不要输出其他内容
4. 绝对不要输出任何解释、备注、标点符号，仅输出指令或"none"
"""
        try:
            # 调用AI，超时时间缩短，提升响应速度
            result = self._llm_call_with_timeout(prompt).strip().lower()
            # 校验返回结果是否在可选指令里
            for cmd in options.keys():
                if result == cmd.lower():
                    return cmd
            # 匹配失败返回None
            return None
        except:
            # AI调用失败，返回None，走兜底逻辑
            return None
    
    def _search_similar_bugs_ai(self, query_description):
        """
        优化版AI语义搜索：生成自然的相似原因，不再生硬罗列关键词
        """
        if not self.bugs_index:
            return []
        
        print("[进度] 正在AI语义匹配历史BUG记录...", flush=True)
        
        # 准备历史BUG简要信息
        all_bugs_summary = []
        for bug_id, bug_info in self.bugs_index.items():
            all_bugs_summary.append({
                "id": bug_id,
                "title": bug_info.get("title", ""),
                "description": bug_info.get("description", ""),
                "date": bug_info.get("date", "未知日期")
            })
        
        if len(all_bugs_summary) > 50:
            all_bugs_summary = all_bugs_summary[-50:]
        
        prompt = f"""
你是一个专业的BUG分析专家，从历史BUG中找出与当前描述最相似的{MAX_SIMILAR_BUGS}个记录，并给出相似度百分比。

【当前BUG描述】
{query_description}

【历史BUG列表】
{json.dumps(all_bugs_summary, ensure_ascii=False, indent=2)}

【严格规则】
1. 仅输出JSON数组，每个元素包含id、title、description、date、similarity_reason、similarity_percentage
2. similarity_reason要用自然语言描述，比如「都与OTG功能失败相关」，不要罗列关键词
3. similarity_percentage是0-100的整数，表示相似度百分比
4. 没有相似BUG就输出空数组[]，仅输出JSON，不要其他任何内容
5. 严格JSON格式，不能有语法错误

【输出格式】
[
    {{
        "id": "BUG_XXXXXX",
        "title": "BUG标题",
        "description": "BUG描述",
        "date": "BUG日期",
        "similarity_reason": "自然语言描述的相似原因",
        "similarity_percentage": 85
    }}
]
"""
        # 调用LLM
        max_retries = 2
        ai_result = None
        for retry in range(max_retries):
            try:
                print(f"[进度] 正在调用AI（第{retry+1}次）...", flush=True)
                response = self._llm_call_with_timeout(prompt)
                ai_result = self._extract_json_from_text(response)
                if isinstance(ai_result, list):
                    print("[进度] AI语义匹配完成！", flush=True)
                    break
            except Exception as e:
                print(f"[警告] 第{retry+1}次匹配失败: {str(e)}", flush=True)
                if retry < max_retries -1:
                    print("[进度] 2秒后重试...", flush=True)
                    import time
                    time.sleep(2)
        
        # AI调用失败，降级到关键词匹配
        if ai_result is None:
            print("[提示] AI语义匹配失败，将使用关键词匹配", flush=True)
            return self._search_similar_bugs_keyword(query_description)
        
        # 格式化返回结果
        similar_bugs = []
        try:
            for bug in ai_result:
                if isinstance(bug, dict) and "id" in bug and bug["id"] in self.bugs_index:
                    # 安全地获取所有字段，使用默认值
                    bug_info = self.bugs_index[bug["id"]]
                    similar_bugs.append({
                        "id": bug["id"],
                        "title": bug.get("title", bug_info.get("title", "")),
                        "description": bug.get("description", bug_info.get("description", "")),
                        "date": bug.get("date", bug_info.get("date", "未知日期")),
                        "similarity_reason": bug.get("similarity_reason", "语义相似"),
                        "similarity_percentage": bug.get("similarity_percentage", 0)
                    })
        except Exception as e:
            print(f"[提示] AI结果解析异常: {e}，使用关键词匹配", flush=True)
            return self._search_similar_bugs_keyword(query_description)
        
        return similar_bugs[:MAX_SIMILAR_BUGS]
    
    def _extract_keywords(self, text):
        """提取有效关键词，用于兜底匹配"""
        if not text:
            return []
        
        text = re.sub(r'[^\w\s]', ' ', text).lower()
        words = text.split()
        keywords = []
        for word in words:
            word = word.strip()
            if len(word) < 2 or word in STOP_WORDS:
                continue
            keywords.append(word)
        
        for kw in BUG_CORE_KEYWORDS:
            if kw in text:
                keywords.append(kw)
        
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
                    reason = "都与OTG功能失败相关"
                elif 'bc1' in matched_words and '失败' in matched_words:
                    reason = "都与BC1.2识别失败相关"
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
    
    def _extract_tags(self, text):
        """提取标签用于搜索优化"""
        tags = []
        for tag in BUG_CORE_KEYWORDS:
            if tag in text.lower():
                tags.append(tag)
        return tags
    
    def _init_collect_data(self, initial_desc):
        """初始化收集数据字典"""
        collect_data = {}
        for field in self.required_fields.keys():
            collect_data[field] = "待补充"
        collect_data["description"] = initial_desc
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
    
    def _auto_fill_fallback_fields(self, collect_data):
        """自动填充剩余字段为暂未确定"""
        updated_data = collect_data.copy()
        for field, value in updated_data.items():
            if value == "待补充":
                updated_data[field] = AUTO_FILL_TEXT
        return updated_data
    
    def _smart_input(self, prompt="你: "):
        """智能输入，单行/多行都支持"""
        print(prompt, end="", flush=True)
        try:
            first_line = input().strip()
            
            # 全局退出指令优先
            if first_line.lower() in ['exit', 'quit', '取消']:
                return "exit"
            if first_line == "完成":
                return "完成"
            # 多行模式入口
            if first_line.lower() == "multi":
                print("📝 已进入多行输入模式，输入完成后单独一行输入###提交", flush=True)
                lines = []
                while True:
                    line = input()
                    if line.strip() == "###":
                        break
                    lines.append(line)
                return "\n".join(lines).strip()
            
            return first_line
        
        except KeyboardInterrupt:
            return "exit"
        except Exception as e:
            print(f"[错误] 输入异常: {str(e)}", flush=True)
            return ""
    
    def _ai_extract_all_fields(self, user_input, collect_data):
        """AI自动全字段提取，用户输入任何内容都自动匹配所有字段"""
        filled_fields = [k for k, v in collect_data.items() if v != "待补充"]
        
        prompt = f"""
你是一个专业的BUG信息提取专家，从用户输入中提取BUG信息，更新JSON数据。

【核心规则】
1. 已填充字段：{filled_fields}，绝对不要修改、覆盖
2. 仅处理"待补充"的字段，用户没提到的保持"待补充"
3. 所有字段都是必填项，不能使用"暂未确定"等兜底表述
4. 仅输出更新后的完整JSON，不要其他任何内容

【字段说明】
{json.dumps(self.required_fields, ensure_ascii=False, indent=2)}

【当前已有数据】
{json.dumps(collect_data, ensure_ascii=False, indent=2)}

【用户输入】
{user_input}
"""
        ai_result = self._call_llm_safely(prompt, expected_format="json")
        if ai_result and isinstance(ai_result, dict):
            final_data = collect_data.copy()
            for field in self.required_fields.keys():
                if final_data[field] == "待补充" and field in ai_result:
                    new_value = str(ai_result[field]).strip()
                    if new_value and new_value != "待补充" and new_value != "None" and new_value != AUTO_FILL_TEXT:
                        final_data[field] = new_value
            
            return final_data
        
        return collect_data
    
    def _print_collect_status(self, collect_data):
        """打印当前收集状态"""
        print("\n📊 当前BUG信息收集状态：", flush=True)
        print("-"*50, flush=True)
        for field, field_desc in self.required_fields.items():
            field_name = field_desc.split("（")[0]
            value = collect_data[field]
            if value == "待补充":
                status = "❌ 待补充"
            elif value == AUTO_FILL_TEXT:
                status = "ℹ️  暂未确定"
            else:
                status = "✅ 已填充"
            print(f"{status} {field_name}: {value}", flush=True)
        print("-"*50, flush=True)
    
    def _generate_question(self, missing_field, missing_field_name, collect_data):
        """生成自然提问"""
        prompt = f"""
你是专业的嵌入式BUG记录助手，为缺失的字段生成简洁自然的提问。
【缺失字段】{missing_field}，说明：{self.required_fields[missing_field]}
【已有信息】{json.dumps(collect_data, ensure_ascii=False)}
【要求】仅输出提问本身，不要其他内容，简洁口语化
"""
        question = self._call_llm_safely(prompt, expected_format="text")
        return question if question else f"请补充一下{missing_field_name}："
    
    def start_conversational_record(self, initial_description=""):
        """用户主导的BUG记录流程"""
        print("\n" + "="*60, flush=True)
        print("🐞 AI对话式BUG记录助手", flush=True)
        print("="*60, flush=True)
        print("💡 【使用说明】", flush=True)
        print("1. 直接输入任何BUG相关信息，AI会自动提取所有匹配的字段", flush=True)
        print("2. 多行输入：输入multi按回车，进入多行模式，完成后单独一行输入###提交", flush=True)
        print("3. 批量兜底：输入「其他都暂未确定」，自动填充剩余所有字段", flush=True)
        print("4. 输入「完成」：随时终止收集，直接进入信息确认环节", flush=True)
        print("5. 输入exit：随时退出记录\n", flush=True)
        
        # 处理初始描述
        if not initial_description:
            print("请输入BUG相关信息（可以是现象、产品线、芯片等任何内容）：", flush=True)
            initial_description = self._smart_input(prompt="你: ")
            if initial_description == "exit":
                print("❌ 已退出BUG记录", flush=True)
                return
            if not initial_description:
                print("❌ 输入内容不能为空，已退出记录", flush=True)
                return
        
        # 初始化收集数据
        collect_data = self._init_collect_data(initial_description)
        print("📥 正在解析初始信息...", flush=True)
        collect_data = self._ai_extract_all_fields(initial_description, collect_data)
        self._print_collect_status(collect_data)
        
        # AI语义搜索相似BUG
        print("\n🔍 正在AI语义搜索历史相似BUG...", flush=True)
        similar_bugs = self._search_similar_bugs_ai(initial_description)
        similar_info = "无"
        if similar_bugs:
            similar_info = "已发现以下历史相似BUG供参考：\n"
            for bug in similar_bugs:
                similar_info += f"- {bug['id']} ({bug.get('date', '')}): {bug['title']}\n"
                similar_info += f"  相似原因: {bug['similarity_reason']}\n"
            print(similar_info, flush=True)
        else:
            print("✅ 未发现历史相似BUG", flush=True)
        
        # 核心收集循环 - 改为一次性显示所有待补充字段，并支持字段标签
        print("\n🤖 信息收集进行中，请补充以下字段信息：", flush=True)
        
        # 获取所有待补充字段列表
        missing_fields = []
        for field, field_desc in self.required_fields.items():
            if collect_data[field] == "待补充":
                field_name = field_desc.split("（")[0]
                missing_fields.append((field, field_name))
        
        if missing_fields:
            print("\n📋 请补充以下字段信息（可以一次性填写多个，用换行分隔）：", flush=True)
            for i, (field, field_name) in enumerate(missing_fields, 1):
                print(f"{i}. 【{field_name}】: ", flush=True)
            
            print("\n💡 提示：请按顺序填写上述字段，每个字段一行，完成后输入###提交", flush=True)
            print("   或者输入exit退出，输入完成跳过（但所有字段必须填写）", flush=True)
            print("   支持格式：字段编号: 内容 或 直接填写内容", flush=True)
            
            # 获取多行输入
            user_input_lines = []
            while True:
                line = self._smart_input(prompt="> ")
                
                if line == "exit":
                    print("❌ 已退出BUG记录", flush=True)
                    return
                if line == "完成":
                    print("⚠️ 所有必填字段必须填写，不能跳过", flush=True)
                    continue
                if line == "###":
                    break
                if line:
                    user_input_lines.append(line)
            
            # 处理多行输入 - 支持字段编号格式
            if user_input_lines:
                processed_input = []
                for line in user_input_lines:
                    # 检查是否是"编号: 内容"格式
                    if re.match(r'^\d+:', line):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            field_num = int(parts[0].strip())
                            content = parts[1].strip()
                            if 1 <= field_num <= len(missing_fields):
                                field_name = missing_fields[field_num-1][1]
                                processed_input.append(f"{field_name}: {content}")
                                continue
                    processed_input.append(line)
                
                combined_input = "\n".join(processed_input)
                print("📥 正在解析信息...", flush=True)
                collect_data = self._ai_extract_all_fields(combined_input, collect_data)
                self._print_collect_status(collect_data)
        
        # 检查是否全部完成
        if self._check_collect_complete(collect_data):
            print("\n🎉 所有BUG信息已全部收集完成！", flush=True)
        else:
            print("\n⚠️ 仍有字段未完成，请继续补充", flush=True)
        
        # ==================== 最终确认环节：AI意图匹配 ====================
        print("\n" + "="*60, flush=True)
        print("📋 最终BUG信息确认", flush=True)
        print("="*60, flush=True)
        for field, field_desc in self.required_fields.items():
            field_name = field_desc.split("（")[0]
            value = collect_data[field]
            print(f"【{field_name}】: {value}", flush=True)
        
        # 定义可选操作
        confirm_options = {
            "confirm": "确认以上信息无误，保存BUG记录",
            "modify": "修改某个字段的内容",
            "cancel": "取消记录，不保存任何内容，返回主菜单"
        }
        
        while True:
            user_input = input("\n请输入你的操作（确认/修改/取消）: ").strip()
            # 全局退出指令优先
            if user_input.lower() in ['exit', 'quit']:
                print("❌ 已退出BUG记录", flush=True)
                return
            
            # AI意图识别
            intent = self._ai_intent_recognize(
                user_input=user_input,
                options=confirm_options,
                scene_desc="当前处于BUG记录最终确认环节，用户需要选择确认保存、修改内容、还是取消记录"
            )
            
            # 处理识别结果
            if intent == "confirm":
                print("✅ 已确认，开始保存记录", flush=True)
                break
            elif intent == "modify":
                print("\n📖 可修改字段列表：", flush=True)
                for field, field_desc in self.required_fields.items():
                    field_name = field_desc.split("（")[0]
                    print(f"- {field}: {field_name}", flush=True)
                modify_field = input("\n请输入要修改的字段名: ").strip()
                if modify_field in self.required_fields:
                    field_name = self.required_fields[modify_field].split("（")[0]
                    new_value = input(f"请输入【{field_name}】的新内容: ").strip()
                    collect_data[modify_field] = new_value
                    print("✅ 修改成功，将重新展示完整信息", flush=True)
                    # 重新展示信息
                    print("\n" + "="*60, flush=True)
                    print("📋 最终BUG信息确认", flush=True)
                    print("="*60, flush=True)
                    for field, field_desc in self.required_fields.items():
                        field_name = field_desc.split("（")[0]
                        print(f"【{field_name}】: {collect_data[field]}", flush=True)
                else:
                    print("❌ 字段名不存在，请重新输入", flush=True)
            elif intent == "cancel":
                print("❌ 已取消BUG记录，未保存任何内容", flush=True)
                return
            else:
                # AI识别失败，兜底提示
                print("❌ 未识别到有效操作，请输入「确认」「修改」或「取消」", flush=True)
        
        # 保存BUG记录
        bug_id = self._generate_bug_id()
        self._save_bug_record(bug_id, collect_data, similar_info)
        
        # 完成提示
        print(f"\n🎉 BUG记录已成功保存！", flush=True)
        print(f"🆔 BUG ID: {bug_id}", flush=True)
        print(f"📁 文件路径: {os.path.join(self.bugs_dir, f'{bug_id}.md')}", flush=True)
        return bug_id
    
    def _save_bug_record(self, bug_id, bug_data, similar_info):
        """保存符合bug_template.md模板的Markdown记录，更新索引"""
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 映射字段到模板格式
        # 对于模板中但当前数据没有的字段，使用默认值
        firmware_version = "暂未确定"  # 模板有但当前数据没有
        reporter = "AI记录工具"  # 模板有但当前数据没有
        secondary_effect = "暂未发现"  # 模板有但当前数据没有
        pre_condition = bug_data.get('trigger_condition', '暂未确定')
        steps = "待补充详细触发步骤"  # 模板有但当前数据没有
        reproduce_condition = "待补充复现依赖条件"  # 模板有但当前数据没有
        hardware_env = bug_data.get('environment', '暂未确定')
        external_device = "待补充外部设备信息"  # 模板有但当前数据没有
        software_env = "待补充软件环境"  # 模板有但当前数据没有
        test_tools = "待补充测试工具"  # 模板有但当前数据没有
        log = "待补充日志信息"  # 模板有但当前数据没有
        waveform = "待补充波形信息"  # 模板有但当前数据没有
        packet = "待补充抓包信息"  # 模板有但当前数据没有
        surface_cause = bug_data.get('root_cause_hypothesis', '暂未确定')
        root_cause = "待深入分析深层原因"  # 模板有但当前数据没有
        patch = bug_data.get('solution_tried', '暂未尝试')
        long_term_solution = "待制定长期方案"  # 模板有但当前数据没有
        debug_steps = "待补充排查路径"  # 模板有但当前数据没有
        tags = "待补充标签"  # 模板有但当前数据没有
        
        md_content = f"""# 🐞 Bug 记录（精简版）

---

## 1 核心基本信息
| 字段       | 内容                  |
| ---------- | --------------------- |
| Bug ID     | {bug_id}              |
| 产品线     | {bug_data['product_line']} |
| 芯片型号   | {bug_data['chip_model']} |
| 固件版本   | {firmware_version}    |
| 严重级别   | {bug_data['severity']} |
| 提报人/时间 | {reporter} / {current_date} |

---

## 2 问题现象
核心现象（必填）
{bug_data['description']}

衍生现象（可选）
{secondary_effect}

---

## 3 复现核心信息
### 触发条件
前置条件：{pre_condition}
触发步骤：{steps}

### 复现关键
复现概率：{bug_data['reproduce_rate']}
复现依赖：{reproduce_condition}

---

## 4 运行环境（精简）
硬件/外部设备：{hardware_env} + {external_device}
软件/测试工具：{software_env} + {test_tools}

---

## 5 关键证据（核心）
日志/波形/抓包（按需填）：{log} / {waveform} / {packet}

---

## 6 根因与解决方案
### 根因
表层原因：{surface_cause}
深层原因：{root_cause}
Root Cause 类型（勾选）：
* [ ] 设计缺陷  * [ ] 实现错误  * [ ] 硬件行为差异  * [ ] 兼容问题  * [ ] 其他

### 修复方案
临时修复：{patch}
长期方案：{long_term_solution}

---

## 7 补充信息（可选）
排查路径：{debug_steps}
标签：{tags}

---
*本记录由AI对话式BUG记录工具自动生成*
"""
        
        # 保存文件
        file_name = f"{bug_id}.md"
        file_path = os.path.join(self.bugs_dir, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        # 更新索引 - 修复date字段缺失问题
        self.bugs_index[bug_id] = {
            'title': bug_data['description'][:60] + ('...' if len(bug_data['description'])>60 else ''),
            'description': bug_data['description'],
            'date': current_date
        }
        self._save_bugs_index()
        
        return file_path
    
    def list_all_bugs(self):
        """列出所有BUG记录"""
        if not self.bugs_index:
            print("\n📭 暂无BUG记录", flush=True)
            return
        print("\n📋 所有BUG记录列表：", flush=True)
        print("-"*60, flush=True)
        for bug_id, bug_info in self.bugs_index.items():
            print(f"🆔 {bug_id}", flush=True)
            print(f"   日期: {bug_info.get('date', '未知日期')}", flush=True)
            print(f"   标题: {bug_info['title']}", flush=True)
            print("-"*60, flush=True)
    
    def search_bugs(self, query=""):
        """AI语义搜索BUG记录"""
        if not query:
            query = input("\n请输入搜索关键词或BUG描述: ").strip()
        if not query:
            print("❌ 搜索内容不能为空", flush=True)
            return
        
        print(f"\n🔍 正在AI语义搜索包含「{query}」的BUG记录...", flush=True)
        similar_bugs = self._search_similar_bugs_ai(query)
        
        if not similar_bugs:
            print(f"\n📭 未找到相似的BUG记录", flush=True)
            return
        
        print(f"\n🔍 找到 {len(similar_bugs)} 条相似的BUG记录：", flush=True)
        print("-"*60, flush=True)
        for bug in similar_bugs:
            print(f"🆔 {bug['id']}", flush=True)
            print(f"   日期: {bug.get('date', '未知日期')}", flush=True)
            print(f"   标题: {bug['title']}", flush=True)
            print(f"   相似原因: {bug['similarity_reason']}", flush=True)
            print("-"*60, flush=True)
    
    def get_bug_detail(self, bug_id=""):
        """查看BUG详情（补全之前截断的代码）"""
        if not bug_id:
            bug_id = input("\n请输入要查看的BUG ID: ").strip()
        if not bug_id:
            print("❌ BUG ID不能为空", flush=True)
            return
        
        if bug_id not in self.bugs_index:
            print(f"❌ 未找到ID为「{bug_id}」的BUG记录", flush=True)
            return
        
        # 文件名与ID一致
        file_path = os.path.join(self.bugs_dir, f"{bug_id}.md")
        if not os.path.exists(file_path):
            print(f"❌ BUG记录文件不存在: {file_path}", flush=True)
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"\n📄 BUG {bug_id} 详细记录：", flush=True)
        print("="*60, flush=True)
        print(content, flush=True)
        print("="*60, flush=True)
    
    def print_help(self):
        """打印帮助说明"""
        print("\n" + "="*60, flush=True)
        print("📖 BUG记录工具帮助说明", flush=True)
        print("="*60, flush=True)
        print("【核心指令】", flush=True)
        print("1       进入BUG记录模式，手动记录新BUG", flush=True)
        print("2       列出所有已保存的BUG记录", flush=True)
        print("3       AI语义搜索相似BUG记录", flush=True)
        print("4       查看指定BUG ID的详细记录", flush=True)
        print("help    查看本帮助说明", flush=True)
        print("exit    退出工具", flush=True)
        print("\n【快速使用】", flush=True)
        print("直接输入BUG描述，工具会先匹配历史记录，再询问是否新建", flush=True)
        print("\n【AI智能匹配】", flush=True)
        print("所有输入环节都支持口语化内容，AI会自动识别你的意图", flush=True)
        print("="*60, flush=True)
    
    def _is_valid_bug_input(self, user_input):
        """判断用户输入是否为有效BUG描述"""
        if not user_input or len(user_input) < 3:
            return False
        input_lower = user_input.lower()
        for kw in BUG_CORE_KEYWORDS:
            if kw in input_lower:
                return True
        return False
    
    def chat_with_ai(self, user_input):
        """非标准命令由AI直接回复"""
        print(f"\n🤖 正在思考...", flush=True)
        
        prompt = f"""
你是专业的BUG记录工具助手，也可以和用户友好闲聊。
【用户输入】{user_input}
【要求】回复简洁友好，不超过300字，纯文本，不要Markdown格式。如果用户问的是BUG相关问题，引导使用工具功能。
"""
        try:
            response = self._llm_call_with_timeout(prompt)
            response = response.strip()
            if len(response) > 500:
                response = response[:500] + "..."
            print(f"\nAI: {response}", flush=True)
        except Exception as e:
            print(f"\n❌ AI回复失败: {str(e)}", flush=True)
            print("💡 你可以输入help查看帮助，或输入BUG描述开始记录", flush=True)
    
    # ==================== 核心流程：状态机重构，修复打印顺序问题 ====================
    def handle_bug_description(self, bug_description):
        """
        处理用户输入的BUG描述：状态机重构版，修复打印顺序问题
        初始化后自动执行首次process，完成所有内容打印，再返回状态机
        """
        print(f"\n🔍 检测到BUG描述，正在匹配历史相似记录...", flush=True)
        
        # 第一步：AI语义匹配历史记录
        similar_bugs = self._search_similar_bugs_ai(bug_description)
        
        # 状态机定义（重构，优化打印逻辑）
        class BugDescriptionStateMachine:
            def __init__(self, tool, bug_description, similar_bugs):
                self.tool = tool
                self.bug_description = bug_description
                self.similar_bugs = similar_bugs
                self.state = "INITIAL"
                self.should_exit = False
                self.need_input = False
                self.input_prompt = ""  # 输入提示语，和内容绑定
                self.selected_bug = None
            
            def process(self, user_input=None):
                """处理状态转换，返回是否需要输入"""
                if self.state == "INITIAL":
                    return self._handle_initial_state()
                elif self.state == "HAS_SIMILAR_BUGS":
                    return self._handle_has_similar_bugs_state(user_input)
                elif self.state == "NO_SIMILAR_BUGS":
                    return self._handle_no_similar_bugs_state(user_input)
                elif self.state == "VIEW_BUG_DETAIL":
                    return self._handle_view_bug_detail_state()
                elif self.state == "CREATE_NEW_BUG":
                    return self._handle_create_new_bug_state()
                elif self.state == "RETURN_TO_MAIN":
                    return self._handle_return_to_main_state()
                else:
                    print("❌ 未知状态，返回主菜单", flush=True)
                    self.should_exit = True
                    return False
            
            def _handle_initial_state(self):
                """初始状态：根据是否有相似BUG决定下一步，自动执行打印"""
                if self.similar_bugs:
                    self.state = "HAS_SIMILAR_BUGS"
                    # 首次进入直接执行打印，无需用户输入
                    return self._handle_has_similar_bugs_state()
                else:
                    self.state = "NO_SIMILAR_BUGS"
                    # 首次进入直接执行打印，无需用户输入
                    return self._handle_no_similar_bugs_state()
            
            def _handle_has_similar_bugs_state(self, user_input=None):
                """有相似BUG状态：先打印完整内容，再提示输入"""
                # 首次进入状态，打印完整的相似BUG结果和操作选项
                if user_input is None:
                    print("\n✅ 找到以下历史相似BUG记录：", flush=True)
                    print("-"*60, flush=True)
                    for idx, bug in enumerate(self.similar_bugs, 1):
                        similarity_percentage = bug.get('similarity_percentage', 0)
                        print(f"{idx}. 🆔 {bug['id']} | 日期: {bug['date']} | 相似度: {similarity_percentage}%", flush=True)
                        print(f"   标题: {bug['title']}", flush=True)
                        print(f"   相似原因: {bug['similarity_reason']}", flush=True)
                        print("-"*60, flush=True)
                    
                    # 打印操作选项
                    print("\n📋 可选操作：", flush=True)
                    for idx, bug in enumerate(self.similar_bugs, 1):
                        print(f"{idx}. 查看第{idx}条BUG的详细记录", flush=True)
                    print(f"{len(self.similar_bugs)+1}. 新建BUG记录", flush=True)
                    print(f"{len(self.similar_bugs)+2}. 返回主菜单", flush=True)
                    
                    # 设置输入提示语，和内容绑定
                    self.input_prompt = "请输入你的选择: "
                    self.need_input = True
                    return True
                
                # 处理用户输入
                # 全局退出指令优先
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 已退出", flush=True)
                    self.should_exit = True
                    self.need_input = False
                    return False
                
                # 快速匹配：数字
                if user_input.isdigit():
                    num = int(user_input)
                    if 1 <= num <= len(self.similar_bugs):
                        self.selected_bug = self.similar_bugs[num-1]
                        self.state = "VIEW_BUG_DETAIL"
                        self.need_input = False
                        return False
                    elif num == len(self.similar_bugs) + 1:
                        self.state = "CREATE_NEW_BUG"
                        self.need_input = False
                        return False
                    elif num == len(self.similar_bugs) + 2:
                        self.state = "RETURN_TO_MAIN"
                        self.need_input = False
                        return False
                
                # AI意图识别
                options = {}
                for idx, bug in enumerate(self.similar_bugs, 1):
                    options[str(idx)] = f"查看第{idx}条BUG的详细记录"
                options["new"] = "新建BUG记录"
                options["back"] = "返回主菜单"
                
                scene_desc = f"当前找到了{len(self.similar_bugs)}条相似的历史BUG记录，用户需要选择查看某条记录的详情、新建BUG记录，还是返回主菜单"
                
                intent = self.tool._ai_intent_recognize(
                    user_input=user_input,
                    options=options,
                    scene_desc=scene_desc
                )
                
                if intent and intent.isdigit() and 1 <= int(intent) <= len(self.similar_bugs):
                    self.selected_bug = self.similar_bugs[int(intent)-1]
                    self.state = "VIEW_BUG_DETAIL"
                    self.need_input = False
                elif intent == "new":
                    self.state = "CREATE_NEW_BUG"
                    self.need_input = False
                elif intent == "back":
                    self.state = "RETURN_TO_MAIN"
                    self.need_input = False
                else:
                    print("❌ 未识别到有效操作，请重新输入", flush=True)
                    self.need_input = True
                
                return self.need_input
            
            def _handle_no_similar_bugs_state(self, user_input=None):
                """无相似BUG状态：先打印提示，再提示输入"""
                # 首次进入状态，打印提示
                if user_input is None:
                    print("\n✅ 未找到相似的历史BUG记录", flush=True)
                    # 设置输入提示语
                    self.input_prompt = "是否需要新建BUG记录？(新建/返回): "
                    self.need_input = True
                    return True
                
                # 处理用户输入
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 已退出", flush=True)
                    self.should_exit = True
                    self.need_input = False
                    return False
                
                options = {
                    "new": "新建一条BUG记录",
                    "back": "返回主菜单，不新建记录"
                }
                
                intent = self.tool._ai_intent_recognize(
                    user_input=user_input,
                    options=options,
                    scene_desc="当前未找到相似BUG记录，用户需要选择新建记录还是返回主菜单"
                )
                
                if intent == "new":
                    self.state = "CREATE_NEW_BUG"
                    self.need_input = False
                elif intent == "back":
                    self.state = "RETURN_TO_MAIN"
                    self.need_input = False
                else:
                    print("❌ 未识别到有效操作，请输入「新建」或「返回」", flush=True)
                    self.need_input = True
                
                return self.need_input
            
            def _handle_view_bug_detail_state(self):
                """查看BUG详情状态"""
                self.tool.get_bug_detail(bug_id=self.selected_bug['id'])
                # 查看完详情后直接返回主菜单
                self.should_exit = True
                return False
            
            def _handle_create_new_bug_state(self):
                """新建BUG记录状态"""
                print("\n📝 进入新建BUG记录模式", flush=True)
                self.tool.start_conversational_record(initial_description=self.bug_description)
                self.should_exit = True
                return False
            
            def _handle_return_to_main_state(self):
                """返回主菜单状态"""
                print("\n🔙 返回主菜单", flush=True)
                self.should_exit = True
                return False
        
        # 【核心修复】初始化状态机后，立即执行一次process，自动完成状态切换和内容打印
        state_machine = BugDescriptionStateMachine(self, bug_description, similar_bugs)
        # 首次执行，自动打印所有内容，返回是否需要输入
        state_machine.process()
        
        # 返回初始化完成、内容已打印的状态机
        return state_machine

# ==================== 主函数重构，修复输入提示和内容脱节问题 ====================
def main():
    """主程序入口，修复打印顺序问题"""
    tool = BugDialogTool()
    print("="*60, flush=True)
    print("🐞 BUG记录与查询工具 - 全AI意图匹配修复版", flush=True)
    print("="*60, flush=True)
    print("📖 输入help查看完整帮助说明，输入exit退出工具", flush=True)
    print("💡 所有输入都支持口语化内容，AI会自动识别你的意图", flush=True)
    print("="*60, flush=True)
    
    # 状态机实例，用于处理BUG描述
    current_state_machine = None
    
    while True:
        try:
            if current_state_machine is None:
                # 正常模式，等待用户输入
                user_input = input("\nBUG工具> ").strip()
                user_input_lower = user_input.lower()
                
                # 主菜单AI意图识别
                main_menu_options = {
                    "list": "列出所有已保存的BUG记录",
                    "detail": "查看指定BUG ID的详细记录",
                    "help": "查看帮助说明、功能列表、你能做什么、有什么功能、使用说明",
                    "exit": "退出工具"
                }
                
                main_intent = tool._ai_intent_recognize(
                    user_input=user_input,
                    options=main_menu_options,
                    scene_desc="当前处于BUG记录工具主菜单，用户可以选择查看列表、查看详情、查看帮助、退出工具或者其他"
                )
                
                print(main_intent)
                # 处理主菜单意图识别结果
                if main_intent == "list":
                    tool.list_all_bugs()
                    continue
                elif main_intent == "detail":
                    tool.get_bug_detail()
                    continue
                elif main_intent == "help":
                    tool.print_help()
                    continue
                elif main_intent == "exit":
                    print("👋 感谢使用，再见！", flush=True)
                    break
                
                # 核心逻辑：判断是否为BUG描述
                if tool._is_valid_bug_input(user_input):
                    # 【核心修复】handle_bug_description内部已经完成了内容打印
                    current_state_machine = tool.handle_bug_description(bug_description=user_input)
                    # 如果状态机已经结束，直接重置
                    if current_state_machine and current_state_machine.should_exit:
                        current_state_machine = None
                else:
                    # 非BUG描述，走AI闲聊
                    tool.chat_with_ai(user_input)
            else:
                # 状态机模式：【核心修复】使用状态机内部绑定的输入提示语，不会提前跳出
                user_input = input(current_state_machine.input_prompt).strip()
                
                # 全局退出指令优先
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 已退出", flush=True)
                    current_state_machine = None
                    continue
                
                # 处理状态机输入
                need_input = current_state_machine.process(user_input)
                
                # 状态机不需要输入了，继续推进流程
                if not need_input:
                    while not current_state_machine.should_exit and not need_input:
                        need_input = current_state_machine.process()
                    
                    # 状态机结束，重置
                    if current_state_machine.should_exit:
                        current_state_machine = None
        
        except KeyboardInterrupt:
            print("\n👋 程序被用户中断，已退出", flush=True)
            break
        except Exception as e:
            print(f"❌ 程序运行异常: {str(e)}", flush=True)

if __name__ == "__main__":
    main()