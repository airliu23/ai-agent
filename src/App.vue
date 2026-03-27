<template>
    <div class="app-container">
        <div class="main-container">
            <Sidebar 
                :currentMode="currentMode"
                :sessions="sessions"
                :currentSessionId="currentSessionId"
                @setMode="setMode"
                @listBugs="listBugs"
                @searchBugs="searchBugs"
                @clearChatContext="showClearContextDialog"
                @clearOutput="showClearOutputDialog"
                @newRecord="newRecord"
                @newSession="newSession"
                @switchSession="switchSession"
                @deleteSession="showDeleteSessionDialog"
            />
            <ChatPanel 
                ref="chatPanel"
                :currentMode="currentMode"
                :status="status"
                :statusText="statusText"
                @send="handleSend"
                @sendFile="handleSendFile"
            />
        </div>
        <div class="status-bar">
            <span>
                <span :class="['status-indicator', 'status-' + status]"></span>
                <span>{{ statusText }}</span>
            </span>
            <span class="status-shortcuts">Ctrl+Enter 发送 | Shift+Enter 换行</span>
        </div>

        <!-- 确认弹窗 -->
        <ConfirmDialog 
            :visible="dialog.visible"
            :title="dialog.title"
            :description="dialog.description"
            :icon="dialog.icon"
            :confirmText="dialog.confirmText"
            @confirm="dialog.onConfirm"
            @cancel="dialog.visible = false"
        />
    </div>
</template>

<script>
import Sidebar from './components/Sidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import { useTheme } from './composables/useTheme.js'

export default {
    name: 'App',
    components: { Sidebar, ChatPanel, ConfirmDialog },
    setup() {
        // 初始化主题（确保 DOM 属性被设置）
        useTheme()
    },
    data() {
        return {
            currentMode: 'chat',
            status: 'ready',
            statusText: '就绪',
            sessions: [],
            currentSessionId: '',
            dialog: {
                visible: false,
                title: '',
                description: '',
                icon: '⚠️',
                confirmText: '确定',
                onConfirm: () => {}
            }
        }
    },
    async mounted() {
        await this.loadSessions()
    },
    methods: {
        setMode(mode) {
            this.currentMode = mode
        },
        setStatus(status, text) {
            this.status = status
            this.statusText = text
        },
        async loadSessions() {
            let retries = 0
            while (!(window.pywebview && window.pywebview.api) && retries < 50) {
                await new Promise(resolve => setTimeout(resolve, 100))
                retries++
            }

            if (!(window.pywebview && window.pywebview.api)) {
                console.log('API 未就绪')
                return
            }

            try {
                const result = await window.pywebview.api.get_sessions()
                if (result && result.success) {
                    this.sessions = result.sessions || []
                    this.currentSessionId = result.current || ''
                }
            } catch (error) {
                console.log('加载会话列表失败:', error)
            }
        },
        async newSession() {
            if (!(window.pywebview && window.pywebview.api)) return
            try {
                const result = await window.pywebview.api.new_session()
                if (result && result.success) {
                    this.currentSessionId = result.session_id
                    this.$refs.chatPanel.clearMessages()
                    await this.loadSessions()
                }
            } catch (error) {
                console.log('创建新会话失败:', error)
            }
        },
        async switchSession(sessionId) {
            if (sessionId === this.currentSessionId) return
            if (!(window.pywebview && window.pywebview.api)) return
            try {
                const result = await window.pywebview.api.switch_session(sessionId)
                if (result && result.success) {
                    this.currentSessionId = result.session_id
                    this.$refs.chatPanel.clearMessages()
                    if (result.history && result.history.length > 0) {
                        this.$refs.chatPanel.hideWelcome()
                        for (const msg of result.history) {
                            this.$refs.chatPanel.addMessage(msg.role, msg.content)
                        }
                    }
                }
            } catch (error) {
                console.log('切换会话失败:', error)
            }
        },
        showDeleteSessionDialog(sessionId) {
            this.dialog = {
                visible: true,
                title: '删除对话',
                description: '确定要永久删除这个对话吗？此操作不可撤销。',
                icon: '🗑️',
                confirmText: '删除',
                onConfirm: () => {
                    this.dialog.visible = false
                    this.deleteSession(sessionId)
                }
            }
        },
        async deleteSession(sessionId) {
            if (!(window.pywebview && window.pywebview.api)) return
            try {
                const result = await window.pywebview.api.delete_session(sessionId)
                if (result && result.success) {
                    // 如果删的是当前会话，清空聊天面板
                    if (sessionId === this.currentSessionId) {
                        this.currentSessionId = result.current
                        this.$refs.chatPanel.clearMessages()
                    }
                    await this.loadSessions()
                }
            } catch (error) {
                console.log('删除会话失败:', error)
            }
        },
        async handleSend(text) {
            if (!(window.pywebview && window.pywebview.api)) {
                this.$refs.chatPanel.addMessage('system', '当前未连接到 API。')
                return
            }

            if (this.currentMode === 'chat') {
                await this.sendChat(text)
            } else {
                this.setStatus('busy', 'BUG 工具处理中...')
                try {
                    await window.pywebview.api.receive_input(text)
                    this.setStatus('ready', '就绪')
                } catch (error) {
                    this.$refs.chatPanel.addMessage('system', '发送失败：' + error)
                    this.setStatus('error', '发送失败')
                }
            }
        },
        async sendChat(text) {
            try {
                this.setStatus('busy', 'AI 思考中...')
                const result = await window.pywebview.api.receive_chat(text)
                if (result && result.success) {
                    this.$refs.chatPanel.addMessage('ai', result.reply)
                    this.setStatus('ready', '对话完成')
                    // 刷新会话列表（更新标题）
                    await this.loadSessions()
                } else {
                    this.$refs.chatPanel.addMessage('system', '对话失败：' + ((result && result.error) || '未知错误'))
                    this.setStatus('error', '对话失败')
                }
            } catch (error) {
                this.$refs.chatPanel.addMessage('system', '对话失败：' + error)
                this.setStatus('error', '对话失败')
            }
        },
        async handleSendFile(question) {
            if (!(window.pywebview && window.pywebview.api)) {
                this.$refs.chatPanel.addMessage('system', '当前未连接到 API。')
                return
            }

            try {
                this.setStatus('busy', '正在打开文件选择框...')
                const result = await window.pywebview.api.receive_chat_file(question)

                if (!result || !result.success) {
                    this.setStatus('ready', '就绪')
                    if (result && result.error && result.error !== '未选择文件') {
                        this.$refs.chatPanel.addMessage('system', '文件分析失败：' + result.error)
                    }
                    return
                }

                this.$refs.chatPanel.hideWelcome()
                this.$refs.chatPanel.addMessage('user', `📎 ${result.file_name}${question ? ' - ' + question : ''}`)
                this.$refs.chatPanel.addMessage('ai', result.reply)
                this.setStatus('ready', '文件分析完成')
            } catch (error) {
                this.$refs.chatPanel.addMessage('system', '文件分析失败：' + error)
                this.setStatus('error', '文件分析失败')
            }
        },
        showClearContextDialog() {
            this.dialog = {
                visible: true,
                title: '清空对话上下文',
                description: '确定要清除所有智慧的结晶吗？这将删除对话历史和本地记录。',
                icon: '🧹',
                confirmText: '清空',
                onConfirm: () => {
                    this.dialog.visible = false
                    this.clearChatContext()
                }
            }
        },
        showClearOutputDialog() {
            this.dialog = {
                visible: true,
                title: '清空对话',
                description: '确定要清空当前对话内容吗？',
                icon: '🗑️',
                confirmText: '清空',
                onConfirm: () => {
                    this.dialog.visible = false
                    this.clearOutput()
                }
            }
        },
        async clearChatContext() {
            if (!(window.pywebview && window.pywebview.api)) {
                this.$refs.chatPanel.addMessage('system', '当前未连接到 API。')
                return
            }

            try {
                await window.pywebview.api.clear_chat()
                this.clearOutput()
                this.setStatus('ready', '对话上下文已清空')
            } catch (error) {
                this.$refs.chatPanel.addMessage('system', '清空对话上下文失败：' + error)
                this.setStatus('error', '清空失败')
            }
        },
        clearOutput() {
            this.$refs.chatPanel.clearMessages()
        },
        newRecord() {
            this.currentMode = 'bug'
            this.$refs.chatPanel.setInputAndSend('新建 BUG 记录')
        },
        listBugs() {
            this.currentMode = 'bug'
            this.$refs.chatPanel.setInputAndSend('列出所有 BUG')
        },
        searchBugs() {
            const keyword = prompt('请输入搜索关键词：')
            if (keyword) {
                this.currentMode = 'bug'
                this.$refs.chatPanel.setInputAndSend('搜索 ' + keyword)
            }
        }
    }
}
</script>

<style scoped>
.app-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.status-shortcuts {
    opacity: 0.7;
}
</style>
