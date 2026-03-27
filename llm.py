#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 模块 - AI 大语言模型集成
提供 AI 对话、意图识别、信息提取等功能

安全提示：API Key 通过环境变量 LLM_API_KEY 或 .env 文件配置
"""
import os
import re
import requests
import json
import time
import re
import threading
from typing import Optional, Dict, List, Union, Any
from datetime import datetime


class TimeoutException(Exception):
    """超时异常"""
    pass


class LLMConfig:
    """LLM 配置类"""
    LLM_TIMEOUT = 100  # LLM 调用超时时间（秒）
    MAX_RETRY_COUNT = 2  # 最大重试次数
    REQUEST_TIMEOUT = 60  # 请求超时时间（秒）
    DEFAULT_MODEL = "gpt-5.4"
    
    @classmethod
    def get_default_api_url(cls):
        """从环境变量获取默认 API URL，如果没有设置则使用备用地址"""
        return os.environ.get("LLM_API_URL", "xxx")


def _load_env_from_file(env_file=".env"):
    """
    从 .env 文件加载环境变量（支持 export 格式）
    
    Args:
        env_file: .env 文件路径
    """
    if not os.path.exists(env_file):
        return
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                # 支持 export 格式：export KEY=value
                if line.startswith('export '):
                    line = line[7:]
                # 解析 KEY=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    # 移除引号
                    value = value.strip().strip('"').strip("'")
                    # 只设置尚未存在的环境变量
                    if key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        print(f"[警告] 读取.env 文件失败：{e}")


# 在模块加载时从 .env 文件加载环境变量
_load_env_from_file()


class LLMClass:
    """LLM 客户端类"""
    
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None, 
                 model: Optional[str] = None):
        """
        初始化 LLM 客户端
        
        Args:
            api_key: API 密钥，默认从环境变量 LLM_API_KEY 或 .env 文件读取
            api_url: API 地址，默认使用配置文件中的地址
            model: 模型名称，默认使用 qwen3.5-plus
        """
        self.api_url = api_url or LLMConfig.get_default_api_url()
        self.model_path = model or LLMConfig.DEFAULT_MODEL
        
        # 从参数或环境变量获取 API Key（支持 .env 文件）
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        
        if not self.api_key:
            print("[警告] 未设置 API Key，请配置环境变量 LLM_API_KEY 或在 .env 文件中设置")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = LLMConfig.REQUEST_TIMEOUT

    def chat(self, messages: List[Dict[str, str]]) -> Union[str, Dict]:
        """
        使用完整消息列表进行多轮对话
        
        Args:
            messages: OpenAI 兼容格式的消息列表，
                     例如 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            
        Returns:
            成功时返回回复内容字符串，失败时返回包含 error 字段的字典
        """
        data = {
            "model": self.model_path,
            "messages": messages,
            "stream": False
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                return content
            else:
                return {"error": "API 响应格式异常，未找到有效回复内容"}

        except requests.exceptions.Timeout:
            return {"error": f"请求超时（{self.timeout}秒）"}
        except requests.exceptions.RequestException as e:
            return {"error": f"请求错误：{str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"解析响应错误：{str(e)}"}
        except Exception as e:
            return {"error": f"未知错误：{str(e)}"}

    def ask_llm(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> Union[str, Dict]:
        """
        向 LLM 发送单轮请求并获取回复
        
        Args:
            prompt: 用户提示内容
            system_prompt: 系统提示词
            
        Returns:
            成功时返回回复内容字符串，失败时返回包含 error 字段的字典
        """
        return self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])

    def _extract_json_from_text(self, text: str) -> Optional[Union[List, Dict]]:
        """
        从文本中提取 JSON 数据
        
        Args:
            text: 包含 JSON 的文本
            
        Returns:
            解析后的 JSON 对象（列表或字典），失败返回 None
        """
        if not text or not isinstance(text, str):
            return None
        
        text = text.strip()
        
        # 优先匹配数组
        for match in re.findall(r'\[[\s\S]*\]', text):
            try:
                match = re.sub(r',\s*([}\]])', r'\1', match)
                parsed = json.loads(match)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # 匹配对象
        for match in re.findall(r'\{[\s\S]*\}', text):
            try:
                match = re.sub(r',\s*([}\]])', r'\1', match)
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _llm_call_with_timeout(self, prompt) -> str:
        """
        带超时的 LLM 调用
        
        Args:
            prompt: 提示内容
            
        Returns:
            LLM 回复内容
            
        Raises:
            TimeoutException: 超时异常
            ValueError: 返回空内容异常
        """
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
        thread.join(timeout=LLMConfig.LLM_TIMEOUT)

        if thread.is_alive():
            raise TimeoutException(f"LLM 调用超时，超过{LLMConfig.LLM_TIMEOUT}秒无响应")
        if exception:
            raise exception
        if not result:
            raise ValueError("LLM 返回空内容")
        return result
    
    def _call_llm_safely(self, prompt, expected_format="json"):
        """
        安全调用 LLM，带超时、重试、鲁棒性解析
        
        Args:
            prompt: 提示内容
            expected_format: 期望格式 "json" 或 "text"
            
        Returns:
            解析后的结果，失败返回 None
        """
        for retry in range(LLMConfig.MAX_RETRY_COUNT):
            try:
                response = self._llm_call_with_timeout(prompt)
                if expected_format == "json":
                    parsed_data = self._extract_json_from_text(response)
                    if parsed_data is None:
                        raise ValueError("未找到有效 JSON 格式内容")
                    return parsed_data
                else:
                    return response.strip()
            except Exception as e:
                print(f"[警告] 第{retry+1}次调用失败：{str(e)}", flush=True)
                if retry < LLMConfig.MAX_RETRY_COUNT - 1:
                    print("[进度] 2 秒后重试...", flush=True)
                    time.sleep(2)
        
        print(f"[错误] AI 调用多次失败", flush=True)
        return None

class ChatSession:
    """多轮对话会话类，负责维护完整对话上下文"""

    def __init__(
        self,
        llm_client: Optional[LLMClass] = None,
        system_prompt: str = "You are a helpful assistant.",
        max_history_rounds: int = 10,
        session_id: str = "default"
    ):
        """
        初始化对话会话

        Args:
            llm_client: LLM 客户端实例
            system_prompt: 系统提示词
            max_history_rounds: 最大保留历史轮数（不含 system）
            session_id: 会话ID，用于持久化存储
        """
        self.llm_client = llm_client or LLMClass()
        self.system_prompt = system_prompt
        self.max_history_rounds = max_history_rounds
        self.session_id = session_id
        self.messages: List[Dict[str, str]] = []
        self.storage_dir = os.path.join(os.path.dirname(__file__), "chat_sessions")
        self.storage_file = os.path.join(self.storage_dir, f"{session_id}.json")
        self._load_session()

    def _load_session(self):
        """从文件加载会话历史"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.messages = data.get("messages", [])
                    # 检查是否需要重置（超过24小时）
                    last_time = data.get("last_update", "")
                    if last_time:
                        try:
                            last_dt = datetime.fromisoformat(last_time)
                            if (datetime.now() - last_dt).days >= 1:
                                print(f"[会话] 历史会话超过24小时，已重置")
                                self._reset_memory()
                                return
                        except:
                            pass
                    print(f"[会话] 已加载历史对话，共 {len(self.messages)} 条消息")
            except Exception as e:
                print(f"[会话] 加载历史失败: {e}")
                self._reset_memory()
        else:
            self._reset_memory()

    def _reset_memory(self):
        """仅重置内存中的消息，不写入磁盘"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _save_session(self):
        """保存会话历史到文件"""
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            data = {
                "session_id": self.session_id,
                "messages": self.messages,
                "last_update": datetime.now().isoformat()
            }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[会话] 保存失败: {e}")

    def reset(self):
        """重置会话，仅保留 system prompt"""
        self._reset_memory()
        self._save_session()

    def get_messages(self) -> List[Dict[str, str]]:
        """获取当前会话消息副本"""
        return [message.copy() for message in self.messages]

    def get_chat_history(self) -> List[Dict[str, str]]:
        """获取对话历史（不含system消息）"""
        return [msg for msg in self.messages if msg["role"] != "system"]

    def set_system_prompt(self, system_prompt: str):
        """更新系统提示词并重置上下文"""
        self.system_prompt = system_prompt
        self.reset()

    def _trim_history(self):
        """裁剪历史上下文，避免消息无限增长"""
        system_message = self.messages[0] if self.messages else {
            "role": "system",
            "content": self.system_prompt
        }
        conversation_messages = self.messages[1:]
        max_message_count = max(self.max_history_rounds * 2, 0)

        if len(conversation_messages) > max_message_count:
            conversation_messages = conversation_messages[-max_message_count:]

        self.messages = [system_message] + conversation_messages

    def send(self, user_input: str) -> str:
        """
        发送一条用户消息并获取 assistant 回复，同时写入上下文

        Args:
            user_input: 用户输入

        Returns:
            assistant 回复文本

        Raises:
            ValueError: 输入为空或模型返回异常
        """
        user_input = str(user_input).strip()
        if not user_input:
            raise ValueError("用户输入不能为空")

        self.messages.append({"role": "user", "content": user_input})
        self._trim_history()

        response = self.llm_client.chat(self.messages)

        if isinstance(response, dict):
            self.messages.pop()
            raise ValueError(response.get("error", "AI 服务调用失败"))

        assistant_reply = str(response).strip()
        if not assistant_reply:
            self.messages.pop()
            raise ValueError("AI 返回空内容")

        self.messages.append({"role": "assistant", "content": assistant_reply})
        self._trim_history()
        self._save_session()  # 保存会话
        return assistant_reply


def create_chat_session(
    system_prompt: str = "You are a helpful assistant.",
    llm_client: Optional[LLMClass] = None,
    max_history_rounds: int = 10,
    session_id: str = "default"
) -> ChatSession:
    """创建一个多轮对话会话"""
    return ChatSession(
        llm_client=llm_client,
        system_prompt=system_prompt,
        max_history_rounds=max_history_rounds,
        session_id=session_id
    )


llm_instance = LLMClass()

def ai_extract_all_fields(user_input, collect_data, required_fields):
    """AI 自动全字段提取，用户输入任何内容都自动匹配所有字段"""
    filled_fields = [k for k, v in collect_data.items() if v != "待补充"]
    
    prompt = f"""
你是一个专业的 BUG 信息提取专家，从用户输入中提取 BUG 信息，更新 JSON 数据。

【核心规则】
1. 已填充字段：{filled_fields}，绝对不要修改、覆盖
2. 仅处理"待补充"的字段，用户没提到的保持"待补充"
3. 所有字段都是必填项，不能使用"暂未确定"等兜底表述
4. 仅输出更新后的完整 JSON，不要其他任何内容

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
你是专业的嵌入式 BUG 记录助手，为缺失的字段生成简洁自然的提问。
【缺失字段】{missing_field}，说明：{field_description}
【已有信息】{json.dumps(collect_data, ensure_ascii=False)}
【要求】仅输出提问本身，不要其他内容，简洁口语化
"""
    question = llm_instance._call_llm_safely(prompt, expected_format="text")
    return question if question else f"请补充一下{missing_field_name}："

def ai_chat(user_input):
    """AI 闲聊功能"""
    prompt = f"""
你是专业的 BUG 记录工具助手，也可以和用户友好闲聊。
【用户输入】{user_input}
【要求】回复简洁友好，不超过 300 字，纯文本，不要 Markdown 格式。如果用户问的是 BUG 相关问题，引导使用工具功能。
"""
    try:
        response = llm_instance._llm_call_with_timeout(prompt)
        # 处理可能返回的错误字典
        if isinstance(response, dict):
            return f"AI 服务不可用：{response.get('error', '未知错误')}"
        response = response.strip()
        if len(response) > 500:
            response = response[:500] + "..."
        return response
    except Exception as e:
        return f"AI 回复失败：{str(e)}"

def search_similar_bugs(bugs_index, query_description, max_similar_bugs, max_bugs_for_search, max_retry_count):
    """
    优化版 AI 语义搜索：生成自然的相似原因，不再生硬罗列关键词
    """
    if not bugs_index:
        return []
    
    print("[进度] 正在 AI 语义匹配历史 BUG 记录...", flush=True)
    
    # 准备历史 BUG 简要信息
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
你是一个专业的 BUG 分析专家，从历史 BUG 中找出与当前描述最相似的{max_similar_bugs}个记录，并给出相似度百分比。

【当前 BUG 描述】
{query_description}

【历史 BUG 列表】
{json.dumps(all_bugs_summary, ensure_ascii=False, indent=2)}

【严格规则】
1. 仅输出 JSON 数组，每个元素包含 id、title、description、date、similarity_reason、similarity_percentage
2. similarity_reason 要用自然语言描述，比如「都与 OTG 功能失败相关」，不要罗列关键词
3. similarity_percentage 是 0-100 的整数，表示相似度百分比
4. 没有相似 BUG 就输出空数组 []，仅输出 JSON，不要其他任何内容
5. 严格 JSON 格式，不能有语法错误

【输出格式】
[
    {{
        "id": "BUG_XXXXXX",
        "title": "BUG 标题",
        "description": "BUG 描述",
        "date": "BUG 日期",
        "similarity_reason": "自然语言描述的相似原因",
        "similarity_percentage": 85
    }}
]
"""
    # 调用 LLM
    ai_result = None
    for retry in range(max_retry_count):
        try:
            print(f"[进度] 正在调用 AI（第{retry+1}次）...", flush=True)
            response = llm_instance._llm_call_with_timeout(prompt)
            ai_result = llm_instance._extract_json_from_text(response)
            if isinstance(ai_result, list):
                print("[进度] AI 语义匹配完成！", flush=True)
                break
        except Exception as e:
            print(f"[警告] 第{retry+1}次匹配失败：{str(e)}", flush=True)
            if retry < max_retry_count -1:
                print("[进度] 2 秒后重试...", flush=True)
                time.sleep(2)
    
    # AI 调用失败，返回空列表
    if ai_result is None:
        print("[提示] AI 语义匹配失败", flush=True)
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
        print(f"[提示] AI 结果解析异常：{e}", flush=True)
        return []
    
    return similar_bugs[:max_similar_bugs]


def ai_intent_recognize(user_input, options, scene_desc):
    """
    通用 AI 意图识别：所有用户输入都通过 AI 匹配操作（不使用本地字典匹配）
    :param user_input: 用户输入的文本
    :param options: 可选操作字典，格式：{"操作指令": "目标值"}，目标值可以是数字或其他标识
    :param scene_desc: 当前场景描述，告诉 AI 当前在做什么
    :return: 匹配到的目标值（字符串形式），匹配失败返回 None
    """
    if not user_input or not options:
        return None
    
    prompt = f"""
你是一个专业的用户意图识别专家，需要根据用户输入，匹配最符合的操作编号。

【当前场景】
{scene_desc}

【可选操作及编号】
{options}

【用户输入】
{user_input}

【重要规则】
1. 如果是普通的问候语（如你好、hello、hi 等），应该返回"none"，因为这些不是功能指令
2. 如果用户输入与 BUG 相关（包含 bug、故障、失败、异常等关键词），应该返回"none"，让系统走 BUG 描述处理流程
3. 支持中英文模糊匹配和同义词识别，**关键词优先匹配**：
   - 输入包含"新建"、"创建"、"新增"、"添加"、"new"、"create"等词 → 必须匹配"新建"操作
   - 输入包含"返回"、"回去"、"退出"、"back"、"return"、"主菜单"等词 → 必须匹配"返回"操作
   - 输入包含"确认"、"yes"、"y"、"ok"、"okay"、"sure"、"好的"、"没问题"等词 → 必须匹配"确认"操作
   - 输入包含"修改"、"change"、"edit"、"modify"、"改一下"等词 → 必须匹配"修改"操作
   - 输入包含"取消"、"no"、"n"、"cancel"、"quit"、"不了"、"不要"等词 → 必须匹配"取消"操作
   - 只有当输入包含"第一"、"第 1"、"第一个"、"第一条"等明确序号时 → 才匹配查看对应序号的操作
4. 如果完全匹配不到任何操作，仅输出"none"，不要输出其他内容
"""
    try:
        # 调用 AI，超时时间缩短，提升响应速度
        result = llm_instance._llm_call_with_timeout(prompt).strip().lower()
        
        # 如果是"none"或者无效结果，返回 None
        if result == "none":
            return None

        return str(result)

    except Exception:
        # AI 调用失败，返回 None，走兜底逻辑
        return None


if __name__ == "__main__":
    session = create_chat_session(system_prompt="你是一个友好、简洁的中文助手。")
    print("多轮对话测试已启动，输入 exit 退出，输入 clear 清空上下文。")

    while True:
        try:
            user_text = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出对话。")
            break

        if not user_text:
            continue

        if user_text.lower() in {"exit", "quit"}:
            print("已退出对话。")
            break

        if user_text.lower() == "clear":
            session.reset()
            print("上下文已清空。")
            continue

        try:
            reply = session.send(user_text)
            print(f"AI：{reply}")
        except Exception as e:
            print(f"AI：对话失败：{e}")
