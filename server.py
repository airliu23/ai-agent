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
from bug_record_core import BugRecord
from ui import QueueUI
import threading
import time

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

# BUG 记录工具（队列驱动模式）
bug_ui = QueueUI()
bug_record = BugRecord(bug_ui)

def _bug_core_loop():
    """核心线程：运行 BUG 记录工具的同步代码"""
    while True:
        user_input = bug_ui.input_queue.get()  # 阻塞等待输入
        try:
            bug_record.run(user_input)
        except Exception as e:
            bug_ui.output_queue.put(f"[错误] {e}")

# 启动 BUG 工具后台线程
threading.Thread(target=_bug_core_loop, daemon=True).start()


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


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}


def is_image_file(file_path):
    """判断是否为图片文件"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def encode_image_base64(file_path):
    """将图片编码为 base64"""
    import base64
    with open(file_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_image_mime(file_path):
    """获取图片 MIME 类型"""
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
        '.svg': 'image/svg+xml'
    }
    return mime_map.get(ext, 'image/png')


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


@app.route('/api/dir/list', methods=['POST'])
def list_directory():
    """列出目录内容"""
    data = request.get_json()
    dir_path = data.get('path', os.path.expanduser('~'))
    
    # 处理特殊路径
    if dir_path == '~':
        dir_path = os.path.expanduser('~')
    
    if not os.path.exists(dir_path):
        return jsonify({"success": False, "error": "目录不存在"})
    
    if not os.path.isdir(dir_path):
        return jsonify({"success": False, "error": "不是目录"})
    
    try:
        items = []
        for name in os.listdir(dir_path):
            full_path = os.path.join(dir_path, name)
            try:
                is_dir = os.path.isdir(full_path)
                stat_info = os.stat(full_path)
                items.append({
                    "name": name,
                    "path": full_path,
                    "isDir": is_dir,
                    "isImage": is_image_file(full_path) if not is_dir else False,
                    "size": format_file_size(stat_info.st_size) if not is_dir else "",
                    "mtime": stat_info.st_mtime
                })
            except (PermissionError, OSError):
                continue
        
        # 排序：目录在前，然后按名称排序
        items.sort(key=lambda x: (not x['isDir'], x['name'].lower()))
        
        return jsonify({
            "success": True,
            "path": dir_path,
            "parent": os.path.dirname(dir_path) if dir_path != '/' else None,
            "items": items
        })
    except PermissionError:
        return jsonify({"success": False, "error": "没有访问权限"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/file/thumbnail', methods=['GET'])
def get_thumbnail():
    """获取图片缩略图"""
    file_path = request.args.get('path')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"}), 404
    
    if not is_image_file(file_path):
        return jsonify({"success": False, "error": "不是图片文件"}), 400
    
    try:
        # 直接返回图片文件
        from flask import send_file
        return send_file(file_path, mimetype=get_image_mime(file_path))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/file/info', methods=['POST'])
def file_info():
    """获取文件信息（不分析内容）"""
    data = request.get_json()
    file_path = data.get('path')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"})
    
    try:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        is_image = is_image_file(file_path)
        
        return jsonify({
            "success": True,
            "path": file_path,
            "name": file_name,
            "size": format_file_size(file_size),
            "isImage": is_image
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/file/read', methods=['POST'])
def read_file():
    """读取文件内容（支持 PDF、图片、文本）"""
    data = request.get_json()
    file_path = data.get('path')
    question = data.get('question', '')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"})
    
    try:
        file_name = os.path.basename(file_path)

        # 图片文件 - 使用 vision 多模态分析
        if is_image_file(file_path):
            image_b64 = encode_image_base64(file_path)
            mime = get_image_mime(file_path)
            text = question if question else f"请详细分析这张图片的内容。图片文件名：{file_name}"
            
            # 构建 OpenAI vision 格式的多模态消息
            multimodal_content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}
            ]
            reply = chat_session.send_multimodal(multimodal_content)
            return jsonify({"success": True, "reply": reply, "file_name": file_name})

        # PDF 文件
        if file_path.lower().endswith('.pdf'):
            content = extract_pdf_content(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        
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


@app.route('/bug_records/images/<path:filename>')
def bug_records_image(filename):
    """提供 bug_records/images/ 目录下的图片静态文件服务"""
    from flask import send_from_directory
    images_dir = os.path.join(os.path.dirname(__file__), 'bug_records', 'images')
    return send_from_directory(images_dir, filename)


@app.route('/api/bug/image', methods=['POST'])
def bug_image():
    """BUG 模式 - 添加图片"""
    data = request.get_json()
    file_path = data.get('path')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"})
    
    if not is_image_file(file_path):
        return jsonify({"success": False, "error": "不是图片文件"})
    
    try:
        # 发送图片指令给 BUG 工具
        bug_ui.push_input(f"img:{file_path}")
        
        # 等待处理
        time.sleep(0.3)
        
        # 发送空行结束图片添加循环
        bug_ui.push_input("")
        
        # 等待处理完成
        max_wait = 5
        waited = 0
        while waited < max_wait:
            time.sleep(0.2)
            waited += 0.2
            if bug_ui.is_waiting_input():
                break
        
        reply = bug_ui.get_output() or f"✅ 已添加图片: {os.path.basename(file_path)}"
        
        return jsonify({
            "success": True,
            "reply": reply,
            "file_name": os.path.basename(file_path)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/bug/file', methods=['POST'])
def bug_file():
    """BUG 模式 - 添加文本文件"""
    data = request.get_json()
    file_path = data.get('path')
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"success": False, "error": "文件不存在"})
    
    # 检查是否为文本文件
    text_extensions = ['.txt', '.log', '.md', '.json', '.xml', '.csv', '.c', '.h', '.py', '.js', '.html', '.css']
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in text_extensions:
        return jsonify({"success": False, "error": "不支持的文件类型"})
    
    try:
        # 发送文件指令给 BUG 工具
        bug_ui.push_input(f"file:{file_path}")
        
        # 等待处理
        time.sleep(0.3)
        
        # 发送空行结束文件添加循环
        bug_ui.push_input("")
        
        # 等待处理完成
        max_wait = 5
        waited = 0
        while waited < max_wait:
            time.sleep(0.2)
            waited += 0.2
            if bug_ui.is_waiting_input():
                break
        
        reply = bug_ui.get_output() or f"✅ 已添加文件: {os.path.basename(file_path)}"
        
        return jsonify({
            "success": True,
            "reply": reply,
            "file_name": os.path.basename(file_path)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/paste_image', methods=['POST'])
def paste_image():
    """普通模式 - 粘贴图片（base64），保存到临时目录"""
    import base64
    
    data = request.get_json()
    base64_data = data.get('base64')
    filename = data.get('filename', 'paste.png')
    
    if not base64_data:
        return jsonify({"success": False, "error": "无图片数据"})
    
    try:
        # 解析 base64（可能带有 data:image/xxx;base64, 前缀）
        if ',' in base64_data:
            base64_data = base64_data.split(',', 1)[1]
        
        # 解码
        image_bytes = base64.b64decode(base64_data)
        
        # 保存到临时文件
        temp_dir = os.path.join(os.path.dirname(__file__), 'bug_records', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)
        
        return jsonify({
            "success": True,
            "reply": f"✅ 已粘贴图片: {filename}，请在输入框中输入问题并发送",
            "file_name": filename,
            "temp_path": temp_path
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/bug/paste_image', methods=['POST'])
def bug_paste_image():
    """BUG 模式 - 粘贴图片（base64）"""
    import base64
    
    data = request.get_json()
    base64_data = data.get('base64')
    filename = data.get('filename', 'paste.png')
    
    if not base64_data:
        return jsonify({"success": False, "error": "无图片数据"})
    
    try:
        # 解析 base64（可能带有 data:image/xxx;base64, 前缀）
        if ',' in base64_data:
            base64_data = base64_data.split(',', 1)[1]
        
        # 解码
        image_bytes = base64.b64decode(base64_data)
        
        # 保存到临时文件
        temp_dir = os.path.join(os.path.dirname(__file__), 'bug_records', 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)
        
        # 发送图片指令给 BUG 工具
        bug_ui.push_input(f"img:{temp_path}")
        
        # 等待处理
        time.sleep(0.3)
        
        # 发送空行结束图片添加循环
        bug_ui.push_input("")
        
        # 等待处理完成
        max_wait = 5
        waited = 0
        while waited < max_wait:
            time.sleep(0.2)
            waited += 0.2
            if bug_ui.is_waiting_input():
                break
        
        reply = bug_ui.get_output() or f"✅ 已粘贴图片: {filename}"
        
        # 临时文件保留在 bug_records/temp/ 目录，等待 BUG 记录保存时复制到正式目录
        
        return jsonify({
            "success": True,
            "reply": reply,
            "file_name": filename,
            "temp_path": temp_path
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/bug/cancel_paste', methods=['POST'])
def bug_cancel_paste():
    """取消粘贴图片 - 清理临时文件"""
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({"success": True})
    
    try:
        temp_dir = os.path.join(os.path.dirname(__file__), 'bug_records', 'temp')
        temp_path = os.path.join(temp_dir, filename)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/bug/input', methods=['POST'])
def bug_input():
    """BUG 模式 - 接收输入并处理"""
    data = request.get_json()
    text = (data.get('text') or '').strip()
    
    if not text:
        return jsonify({"success": False, "error": "输入不能为空"})
    
    try:
        # 推送输入到核心线程
        bug_ui.push_input(text)
        
        # 等待核心线程处理（直到它等待下一次输入）
        max_wait = 30
        waited = 0
        while waited < max_wait:
            time.sleep(0.2)
            waited += 0.2
            # 核心程序在等待输入，说明本次处理完成
            if bug_ui.is_waiting_input():
                break
        
        # 获取输出
        reply = bug_ui.get_output() or "已处理"
        waiting = bug_ui.is_waiting_input()
        prompt = bug_ui.get_input_prompt() if waiting else ""
        
        return jsonify({
            "success": True, 
            "reply": reply,
            "waiting_input": waiting,
            "input_prompt": prompt
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==================== 主入口 ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5678))
    print(f"[Server] 启动 Flask 服务器，端口: {port}")
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
