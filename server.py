#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py - Flask HTTP API 后端服务器
为 Electron 前端提供 HTTP API
"""
import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

from llm import create_chat_session
from bug_record_core import BugRecord, BugToolUI

# 初始化 Flask
app = Flask(__name__)
CORS(app)  # 允许跨域

# 会话管理
SYSTEM_PROMPT = "你是一个友好、简洁的中文聊天助手。"
sessions = {}  # session_id -> ChatSession
current_session_id = None
chat_session = None

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "chat_sessions")


def get_or_create_session(session_id):
    """获取或创建会话"""
    global sessions, chat_session, current_session_id
    if session_id not in sessions:
        sessions[session_id] = create_chat_session(
            system_prompt=SYSTEM_PROMPT,
            session_id=session_id
        )
    current_session_id = session_id
    chat_session = sessions[session_id]
    return chat_session


def generate_session_id():
    """生成唯一会话 ID"""
    from datetime import datetime
    return datetime.now().strftime("chat_%Y%m%d_%H%M%S")


def list_all_sessions():
    """列出所有已保存的会话"""
    import json
    result = []
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    for fname in sorted(os.listdir(SESSIONS_DIR), reverse=True):
        if not fname.endswith('.json'):
            continue
        sid = fname[:-5]
        fpath = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            messages = data.get('messages', [])
            # 获取第一条用户消息作为标题
            title = '新对话'
            for msg in messages:
                if msg.get('role') == 'user':
                    title = msg['content'][:30]
                    break
            msg_count = len([m for m in messages if m.get('role') != 'system'])
            if msg_count == 0:
                continue
            last_update = data.get('last_update', '')
            result.append({
                'id': sid,
                'title': title,
                'message_count': msg_count,
                'last_update': last_update
            })
        except Exception:
            continue
    return result


# 启动时创建新会话
current_session_id = generate_session_id()
chat_session = get_or_create_session(current_session_id)

# BUG 记录工具
bug_record = None
bug_ui = None


def extract_pdf_content(file_path: str) -> str:
    """提取 PDF 文件的文本内容"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(f"--- 第 {page_num} 页 ---\n{page_text}")
            content = "\n\n".join(text_parts)
            return content if content.strip() else "[PDF 文件内容为空或无法提取文本]"
    except ImportError:
        return "[错误：未安装 PyPDF2 库，无法解析 PDF。请运行：pip install PyPDF2]"
    except Exception as e:
        return f"[PDF 解析错误：{str(e)}]"


# ==================== API 路由 ====================

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "message": "Server is running"})


@app.route('/api/chat', methods=['POST'])
def chat():
    """对话模式 - 发送消息"""
    data = request.get_json()
    text = (data.get('text') or '').strip()
    
    if not text:
        return jsonify({"success": False, "error": "输入不能为空"})
    
    try:
        reply = chat_session.send(text)
        return jsonify({"success": True, "reply": reply})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    """清空当前对话上下文并删除本地记录"""
    chat_session.reset()
    # 删除本地存储文件
    try:
        storage_file = chat_session.storage_file
        if os.path.exists(storage_file):
            os.remove(storage_file)
            print(f"[会话] 已删除本地记录: {storage_file}")
    except Exception as e:
        print(f"[会话] 删除本地记录失败: {e}")
    return jsonify({"success": True})


@app.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    """获取当前对话历史"""
    try:
        history = chat_session.get_chat_history()
        return jsonify({"success": True, "history": history, "session_id": current_session_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==================== 会话管理 API ====================

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """获取所有会话列表"""
    try:
        session_list = list_all_sessions()
        return jsonify({"success": True, "sessions": session_list, "current": current_session_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/sessions/new', methods=['POST'])
def new_session():
    """创建新会话"""
    global current_session_id, chat_session
    try:
        new_id = generate_session_id()
        chat_session = get_or_create_session(new_id)
        return jsonify({"success": True, "session_id": new_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/sessions/switch', methods=['POST'])
def switch_session():
    """切换到指定会话"""
    global current_session_id, chat_session
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"success": False, "error": "缺少 session_id"})
    try:
        chat_session = get_or_create_session(session_id)
        history = chat_session.get_chat_history()
        return jsonify({"success": True, "session_id": session_id, "history": history})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/sessions/delete', methods=['POST'])
def delete_session():
    """删除指定会话"""
    global current_session_id, chat_session, sessions
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"success": False, "error": "缺少 session_id"})
    try:
        # 从内存移除
        if session_id in sessions:
            del sessions[session_id]
        # 删除文件
        fpath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(fpath):
            os.remove(fpath)
        # 如果删的是当前会话，创建新的
        if session_id == current_session_id:
            new_id = generate_session_id()
            chat_session = get_or_create_session(new_id)
        return jsonify({"success": True, "current": current_session_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/file/read', methods=['POST'])
def read_file():
    """读取文件内容（支持 PDF）"""
    data = request.get_json()
    file_path = data.get('path')
    question = data.get('question', '')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"})
    
    try:
        # 判断文件类型
        if file_path.lower().endswith('.pdf'):
            content = extract_pdf_content(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        
        file_name = os.path.basename(file_path)
        
        # 构建带文件信息的提示
        if question:
            prompt = f"请分析以下文件内容，并回答问题：{question}\n\n文件名：{file_name}\n\n内容：\n{content[:10000]}"
        else:
            prompt = f"请分析以下文件内容：\n\n文件名：{file_name}\n\n内容：\n{content[:10000]}"
        
        if len(content) > 10000:
            prompt += "\n\n[注意：文件内容过长，已截取前 10000 字符]"
        
        # 发送给 AI 分析
        reply = chat_session.send(prompt)
        return jsonify({"success": True, "reply": reply, "file_name": file_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/bug/input', methods=['POST'])
def bug_input():
    """BUG 模式 - 接收输入"""
    data = request.get_json()
    text = (data.get('text') or '').strip()
    
    # TODO: 实现 BUG 工具逻辑
    return jsonify({"success": True, "message": f"已接收输入: {text}"})


# ==================== 主入口 ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5678))
    print(f"[Server] 启动 Flask 服务器，端口: {port}")
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
