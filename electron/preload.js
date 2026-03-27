const { contextBridge, ipcRenderer } = require('electron');

// Python 后端 API 地址
const API_BASE = 'http://127.0.0.1:5678';

// 封装 API 调用
const api = {
    // 健康检查
    async health() {
        const res = await fetch(`${API_BASE}/api/health`);
        return res.json();
    },

    // 对话模式 - 发送消息
    async receive_chat(text) {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        return res.json();
    },

    // 清空对话上下文
    async clear_chat() {
        const res = await fetch(`${API_BASE}/api/chat/clear`, {
            method: 'POST'
        });
        return res.json();
    },

    // 获取对话历史
    async get_chat_history() {
        const res = await fetch(`${API_BASE}/api/chat/history`);
        return res.json();
    },

    // ===== 会话管理 =====

    // 获取所有会话列表
    async get_sessions() {
        const res = await fetch(`${API_BASE}/api/sessions`);
        return res.json();
    },

    // 创建新会话
    async new_session() {
        const res = await fetch(`${API_BASE}/api/sessions/new`, { method: 'POST' });
        return res.json();
    },

    // 切换会话
    async switch_session(session_id) {
        const res = await fetch(`${API_BASE}/api/sessions/switch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id })
        });
        return res.json();
    },

    // 删除会话
    async delete_session(session_id) {
        const res = await fetch(`${API_BASE}/api/sessions/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id })
        });
        return res.json();
    },

    // BUG 模式 - 发送指令
    async receive_input(text) {
        const res = await fetch(`${API_BASE}/api/bug/input`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        return res.json();
    },

    // 选择文件并分析（通过 Electron 对话框）
    async receive_chat_file(question) {
        const filePath = await ipcRenderer.invoke('dialog:openFile');
        if (!filePath) {
            return { success: false, error: '未选择文件' };
        }
        // 发送文件路径和问题到后端处理
        const res = await fetch(`${API_BASE}/api/file/read`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath, question: question || '' })
        });
        return res.json();
    },

    // 选择文件（仅选择，不分析）
    async choose_chat_file() {
        const filePath = await ipcRenderer.invoke('dialog:openFile');
        if (!filePath) {
            return { success: false, error: '未选择文件' };
        }
        const res = await fetch(`${API_BASE}/api/file/read`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath })
        });
        return res.json();
    }
};

// 暴露 API 到渲染进程（保持与 pywebview 相同的接口）
contextBridge.exposeInMainWorld('pywebview', { api });
contextBridge.exposeInMainWorld('electronAPI', {
    openFile: () => ipcRenderer.invoke('dialog:openFile')
});
