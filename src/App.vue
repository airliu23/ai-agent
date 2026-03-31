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
                @selectFile="openFileBrowser"
                @sendFile="handleSendFile"
                @pasteImage="handlePasteImage"
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
        
        <!-- 文件浏览器 -->
        <FileBrowser
            :visible="fileBrowserVisible"
            @select="onFileSelected"
            @cancel="fileBrowserVisible = false"
        />
    </div>
</template>

<script>
import Sidebar from './components/Sidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import FileBrowser from './components/FileBrowser.vue'
import { useTheme } from './composables/useTheme.js'

export default {
    name: 'App',
    components: { Sidebar, ChatPanel, ConfirmDialog, FileBrowser },
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
            fileBrowserVisible: false,
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
                            // 映射 assistant -> ai
                            const type = msg.role === 'assistant' ? 'ai' : msg.role
                            this.$refs.chatPanel.addMessage(type, msg.content)
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
                    const result = await window.pywebview.api.receive_input(text)
                    if (result && result.success) {
                        this.$refs.chatPanel.addMessage('ai', result.reply)
                        this.setStatus('ready', '处理完成')
                    } else {
                        this.$refs.chatPanel.addMessage('system', 'BUG 工具错误：' + ((result && result.error) || '未知错误'))
                        this.setStatus('error', '处理失败')
                    }
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
        openFileBrowser() {
            this.fileBrowserVisible = true
        },
        onFileSelected(fileInfo) {
            this.fileBrowserVisible = false
            this.$refs.chatPanel.setPendingFile({
                path: fileInfo.path,
                name: fileInfo.name,
                size: fileInfo.size,
                isImage: fileInfo.isImage
            })
        },
        async handleSendFile({ path, question }) {
            if (!(window.pywebview && window.pywebview.api)) {
                this.$refs.chatPanel.addMessage('system', '当前未连接到 API。')
                return
            }

            try {
                // BUG 模式下，支持图片和文本文件
                if (this.currentMode === 'bug') {
                    const isImage = /\.(png|jpg|jpeg|gif|bmp|webp|svg)$/i.test(path)
                    const isTextFile = /\.(txt|log|md|json|xml|csv|c|h|py|js|html|css)$/i.test(path)
                    
                    if (isImage) {
                        this.setStatus('busy', '正在添加图片...')
                        const result = await window.pywebview.api.add_bug_image(path)
                        if (result && result.success) {
                            this.$refs.chatPanel.hideWelcome()
                            this.$refs.chatPanel.addMessage('user', `🖼️ ${result.file_name}`)
                            this.$refs.chatPanel.addMessage('ai', result.reply)
                            this.setStatus('ready', '图片已添加')
                        } else {
                            this.$refs.chatPanel.addMessage('system', '添加图片失败：' + (result?.error || '未知错误'))
                            this.setStatus('error', '添加失败')
                        }
                    } else if (isTextFile) {
                        this.setStatus('busy', '正在添加文件...')
                        const result = await window.pywebview.api.add_bug_file(path)
                        if (result && result.success) {
                            this.$refs.chatPanel.hideWelcome()
                            this.$refs.chatPanel.addMessage('user', `📄 ${result.file_name}`)
                            this.$refs.chatPanel.addMessage('ai', result.reply)
                            this.setStatus('ready', '文件已添加')
                        } else {
                            this.$refs.chatPanel.addMessage('system', '添加文件失败：' + (result?.error || '未知错误'))
                            this.setStatus('error', '添加失败')
                        }
                    } else {
                        this.$refs.chatPanel.addMessage('system', 'BUG 模式支持图片和文本文件')
                    }
                    return
                }

                // Chat 模式 - 原有流程
                this.setStatus('busy', '正在分析文件...')
                const result = await window.pywebview.api.analyze_file(path, question)

                if (!result || !result.success) {
                    this.setStatus('ready', '就绪')
                    this.$refs.chatPanel.addMessage('system', '文件分析失败：' + (result?.error || '未知错误'))
                    return
                }

                this.$refs.chatPanel.hideWelcome()
                const isImage = /\.(png|jpg|jpeg|gif|bmp|webp|svg)$/i.test(result.file_name)
                const icon = isImage ? '🖼️' : '📎'
                this.$refs.chatPanel.addMessage('user', `${icon} ${result.file_name}${question ? ' - ' + question : ''}`)
                this.$refs.chatPanel.addMessage('ai', result.reply)
                this.setStatus('ready', '文件分析完成')
                await this.loadSessions()
            } catch (error) {
                this.$refs.chatPanel.addMessage('system', '文件分析失败：' + error)
                this.setStatus('error', '文件分析失败')
            }
        },
        async handlePasteImage(blob) {
            if (!(window.pywebview && window.pywebview.api)) {
                this.$refs.chatPanel.addMessage('system', '当前未连接到 API。')
                return
            }
            
            try {
                this.setStatus('busy', '正在处理粘贴的图片...')
                
                // 将 blob 转换为 base64
                const reader = new FileReader()
                const base64Promise = new Promise((resolve, reject) => {
                    reader.onload = () => resolve(reader.result)
                    reader.onerror = reject
                })
                reader.readAsDataURL(blob)
                const base64Data = await base64Promise
                
                // 生成文件名
                const ext = blob.type.split('/')[1] || 'png'
                const filename = `paste_${Date.now()}.${ext}`
                
                // 根据当前模式调用不同的 API
                let result
                if (this.currentMode === 'bug') {
                    result = await window.pywebview.api.bug_paste_image(base64Data, filename)
                } else {
                    result = await window.pywebview.api.paste_image(base64Data, filename)
                }
                
                if (result && result.success) {
                    this.$refs.chatPanel.hideWelcome()
                    this.$refs.chatPanel.addMessage('user', `🖼️ ${result.file_name}`)
                    if (result.reply) {
                        this.$refs.chatPanel.addMessage('ai', result.reply)
                    }
                    this.setStatus('ready', '图片已添加')
                } else {
                    this.$refs.chatPanel.addMessage('system', '粘贴图片失败：' + (result?.error || '未知错误'))
                    this.setStatus('error', '粘贴失败')
                }
            } catch (error) {
                this.$refs.chatPanel.addMessage('system', '粘贴图片失败：' + error)
                this.setStatus('error', '粘贴失败')
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
