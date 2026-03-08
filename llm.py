import requests
import json
import time
import re
import threading

class TimeoutException(Exception):
    """超时异常"""
    pass

# 配置常量类
class LLMConfig:
    """LLM配置类"""
    LLM_TIMEOUT = 100  # LLM调用超时时间
    MAX_RETRY_COUNT = 2  # 最大重试次数

CONFIG = LLMConfig()

class LLMClass:
    def __init__(self):
        self.api_url = "https://model.southchips.net/v1/chat/completions"
        # self.api_url = "https://127.0.0.1"
        self.model_path = "DeepSeek-V3.1-Terminus"
        self.headers = {
            "Content-Type": "application/json"
        }
        self.timeout = 60  # 请求超时时间（秒）

    def ask_llm(self, prompt):
        data = {
            "model": self.model_path,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "stream": True
        }

        try:
            start_time = time.time()
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json=data, 
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 解析拼接
            full_content = ""  # 存储最终完整的回复内容
            last_data_time = time.time()

            # 逐行读取响应流
            for line in response.iter_lines():
                # 检查总超时
                if time.time() - start_time > self.timeout:
                    return {"error": f"请求超时（{self.timeout}秒）"}
                
                # 检查数据流超时（5秒内没有新数据）
                if time.time() - last_data_time > 5:
                    return {"error": "数据流超时（5秒内无新数据）"}
                
                # 过滤空行
                if not line:
                    continue
                
                # 解码行内容，去除首尾空白
                line_str = line.decode("utf-8").strip()
                last_data_time = time.time()  # 更新最后数据时间
                
                # 过滤非data开头的行
                if not line_str.startswith("data: "):
                    continue
                
                # 提取data: 后面的内容
                data_str = line_str[len("data: "):].strip()
                
                # 结束标识，退出循环
                if data_str == "[DONE]":
                    break
                
                # 解析JSON，提取增量内容
                try:
                    chunk = json.loads(data_str)
                    # 提取增量文本片段
                    delta_content = chunk["choices"][0]["delta"].get("content", "")
                    if delta_content:  # 过滤空内容
                        full_content += delta_content
                except Exception as e:
                    # 跳过解析失败的块，避免程序崩溃
                    print(f"\n解析块失败: {e}, 块内容: {data_str}")
                    continue
            
            return full_content
        except requests.exceptions.Timeout:
            return {"error": f"请求超时（{self.timeout}秒）"}
        except requests.exceptions.RequestException as e:
            return {"error": f"请求错误: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"解析响应错误: {str(e)}"}
        except Exception as e:
            return {"error": f"未知错误: {str(e)}"}

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
                result = self.ask_llm(prompt)
            except Exception as e:
                exception = e

        thread = threading.Thread(target=llm_worker, daemon=True)
        thread.start()
        thread.join(timeout=CONFIG.LLM_TIMEOUT)

        if thread.is_alive():
            raise TimeoutException(f"LLM调用超时，超过{CONFIG.LLM_TIMEOUT}秒无响应")
        if exception:
            raise exception
        if not result:
            raise ValueError("LLM返回空内容")
        return result
    
    def _call_llm_safely(self, prompt, expected_format="json"):
        """安全调用LLM，带超时、重试、强鲁棒性解析"""
        for retry in range(CONFIG.MAX_RETRY_COUNT):
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
                if retry < CONFIG.MAX_RETRY_COUNT - 1:
                    print("[进度] 2秒后重试...", flush=True)
                    time.sleep(2)
        
        print(f"[错误] AI调用多次失败", flush=True)
        return None

llm_instance = LLMClass()

def ai_extract_all_fields(user_input, collect_data, required_fields):
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
{json.dumps(required_fields, ensure_ascii=False, indent=2)}

【当前已有数据】
{json.dumps(collect_data, ensure_ascii=False, indent=2)}

【用户输入】
{user_input}
"""
    ai_result = llm_instance._call_llm_safely(prompt, expected_format="json")
    if ai_result and isinstance(ai_result, dict):
        final_data = collect_data.copy()
        for field in required_fields.keys():
            if final_data[field] == "待补充" and field in ai_result:
                new_value = str(ai_result[field]).strip()
                if new_value and new_value != "待补充" and new_value != "None":
                    final_data[field] = new_value
        
        return final_data
    
    return collect_data

def ai_generate_question(missing_field, missing_field_name, collect_data, field_description):
    """生成自然提问"""
    prompt = f"""
你是专业的嵌入式BUG记录助手，为缺失的字段生成简洁自然的提问。
【缺失字段】{missing_field}，说明：{field_description}
【已有信息】{json.dumps(collect_data, ensure_ascii=False)}
【要求】仅输出提问本身，不要其他内容，简洁口语化
"""
    question = llm_instance._call_llm_safely(prompt, expected_format="text")
    return question if question else f"请补充一下{missing_field_name}："

def ai_chat(user_input):
    """AI闲聊功能"""
    prompt = f"""
你是专业的BUG记录工具助手，也可以和用户友好闲聊。
【用户输入】{user_input}
【要求】回复简洁友好，不超过300字，纯文本，不要Markdown格式。如果用户问的是BUG相关问题，引导使用工具功能。
"""
    try:
        response = llm_instance._llm_call_with_timeout(prompt)
        response = response.strip()
        if len(response) > 500:
            response = response[:500] + "..."
        return response
    except Exception as e:
        return f"AI回复失败: {str(e)}"

def search_similar_bugs(bugs_index, query_description, max_similar_bugs, max_bugs_for_search, max_retry_count):
    """
    优化版AI语义搜索：生成自然的相似原因，不再生硬罗列关键词
    """
    if not bugs_index:
        return []
    
    print("[进度] 正在AI语义匹配历史BUG记录...", flush=True)
    
    # 准备历史BUG简要信息
    all_bugs_summary = []
    for bug_id, bug_info in bugs_index.items():
        all_bugs_summary.append({
            "id": bug_id,
            "title": bug_info.get("title", ""),
            "description": bug_info.get("description", ""),
            "date": bug_info.get("date", "未知日期")
        })
    
    if len(all_bugs_summary) > max_bugs_for_search:
        all_bugs_summary = all_bugs_summary[-max_bugs_for_search:]
    
    prompt = f"""
你是一个专业的BUG分析专家，从历史BUG中找出与当前描述最相似的{max_similar_bugs}个记录，并给出相似度百分比。

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
    ai_result = None
    for retry in range(max_retry_count):
        try:
            print(f"[进度] 正在调用AI（第{retry+1}次）...", flush=True)
            response = llm_instance._llm_call_with_timeout(prompt)
            ai_result = llm_instance._extract_json_from_text(response)
            if isinstance(ai_result, list):
                print("[进度] AI语义匹配完成！", flush=True)
                break
        except Exception as e:
            print(f"[警告] 第{retry+1}次匹配失败: {str(e)}", flush=True)
            if retry < max_retry_count -1:
                print("[进度] 2秒后重试...", flush=True)
                time.sleep(2)
    
    # AI调用失败，返回空列表
    if ai_result is None:
        print("[提示] AI语义匹配失败", flush=True)
        return []
    
    # 格式化返回结果
    similar_bugs = []
    try:
        for bug in ai_result:
            if isinstance(bug, dict) and "id" in bug and bug["id"] in bugs_index:
                # 安全地获取所有字段，使用默认值
                bug_info = bugs_index[bug["id"]]
                similar_bugs.append({
                    "id": bug["id"],
                    "title": bug.get("title", bug_info.get("title", "")),
                    "description": bug.get("description", bug_info.get("description", "")),
                    "date": bug.get("date", bug_info.get("date", "未知日期")),
                    "similarity_reason": bug.get("similarity_reason", "语义相似"),
                    "similarity_percentage": bug.get("similarity_percentage", 0)
                })
    except Exception as e:
        print(f"[提示] AI结果解析异常: {e}", flush=True)
        return []
    
    return similar_bugs[:max_similar_bugs]


def ai_intent_recognize(user_input, options, scene_desc):
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
    
    # 快速匹配失败，走AI意图识别
    prompt = f"""
你是一个专业的用户意图识别专家，需要根据用户输入，匹配最符合的操作指令。

【当前场景】
{scene_desc}

【可选操作指令及说明】
{json.dumps(options, ensure_ascii=False, indent=2)}

【用户输入】
{user_input}

【重要规则】
1. 如果是普通的问候语（如你好、hello、hi等），应该返回"none"，因为这些不是功能指令
2. 如果用户输入与BUG相关（包含bug、故障、失败、异常等关键词），应该返回"none"，让系统走BUG描述处理流程
3. 仅当用户明确表达想要执行某个功能时，才返回对应的操作指令
4. 如果完全匹配不到任何操作，仅输出"none"，不要输出其他内容
5. 绝对不要输出任何解释、备注、标点符号，仅输出指令或"none"
"""
    try:
        # 调用AI，超时时间缩短，提升响应速度
        result = llm_instance._llm_call_with_timeout(prompt).strip().lower()
        # 校验返回结果是否在可选指令里
        for cmd in options.keys():
            if result == cmd.lower():
                return cmd
        # 匹配失败返回None
        return None
    except:
        # AI调用失败，返回None，走兜底逻辑
        return None
