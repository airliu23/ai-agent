// GUI 应用逻辑
const app = {
    outputContent: '',
    
    // 初始化
    init() {
        console.log('GUI initialized');
        this.bindEvents();
        this.setStatus('ready', '就绪');
    },
    
    // 绑定事件
    bindEvents() {
        const inputText = document.getElementById('inputText');
        if (inputText) {
            inputText.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    this.send();
                }
            });
        }
    },
    
    // 发送消息
    send() {
        const inputText = document.getElementById('inputText');
        if (!inputText) return;
        
        const text = inputText.value.trim();
        if (!text) return;
        
        // 显示用户消息
        this.appendOutput('**你**: ' + text + '\n\n');
        
        // 调用 Python API
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.receive_input(text);
        }
        
        // 清空输入框
        inputText.value = '';
    },
    
    // 追加内容（Python 调用）
    appendOutput(content) {
        this.outputContent += content;
        this.renderOutput();
    },
    
    // 渲染输出
    renderOutput() {
        const panel = document.getElementById('outputPanel');
        if (!panel) return;
        
        // 简单的 HTML 转义
        let html = this.outputContent
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
        
        panel.innerHTML = html;
        panel.scrollTop = panel.scrollHeight;
    },
    
    // 清空输出
    clearOutput() {
        this.outputContent = '';
        const panel = document.getElementById('outputPanel');
        if (panel) panel.innerHTML = '';
    },
    
    // 清空输入
    clearInput() {
        const inputText = document.getElementById('inputText');
        if (inputText) inputText.value = '';
    },
    
    // 设置状态
    setStatus(status, text) {
        const indicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        if (indicator && statusText) {
            indicator.className = 'status-indicator status-' + status;
            statusText.textContent = text;
        }
    },
    
    // 新建记录
    newRecord() {
        this.sendCommand('新建 BUG 记录');
    },
    
    // 列表
    listBugs() {
        this.sendCommand('列出所有 BUG');
    },
    
    // 搜索
    searchBugs() {
        const keyword = prompt('请输入搜索关键词：');
        if (keyword) {
            this.sendCommand('搜索 ' + keyword);
        }
    },
    
    // 发送命令
    sendCommand(cmd) {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.receive_input(cmd);
        }
    }
};

// 立即初始化
app.init();