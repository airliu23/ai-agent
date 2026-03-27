<template>
    <div class="chat-container">
        <div class="messages-area" ref="messagesArea">
            <!-- 欢迎卡片 -->
            <div class="welcome-card" v-if="showWelcome">
                <div class="welcome-emoji">{{ welcomeEmoji }}</div>
                <div class="welcome-title">{{ welcomeGreeting }}</div>
                <div class="welcome-desc">
                    我是你的智能助手，可以帮助你记录、管理和分析 BUG。<br>
                    支持自然语言对话，也可以直接上传文件进行分析。
                </div>
                <div class="welcome-tips">
                    <span class="welcome-tip">💬 自然语言对话</span>
                    <span class="welcome-tip">📎 文件上传分析</span>
                    <span class="welcome-tip">🔍 智能搜索</span>
                    <span class="welcome-tip">📝 Markdown 支持</span>
                </div>
            </div>

            <!-- 消息列表 -->
            <MessageItem 
                v-for="(msg, index) in messages" 
                :key="index"
                :type="msg.type"
                :content="msg.content"
                @copy="copyMessage(index)"
                @delete="deleteMessage(index)"
            />

            <!-- 打字动画 -->
            <TypingIndicator v-if="status === 'busy'" />
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
            <div class="input-wrapper">
                <!-- 文件预览 -->
                <div class="pending-file" v-if="pendingFile">
                    <div class="pending-file-info">
                        <span class="pending-file-icon">{{ pendingFile.isImage ? '🖼️' : '📄' }}</span>
                        <div class="pending-file-detail">
                            <span class="pending-file-name">{{ pendingFile.name }}</span>
                            <span class="pending-file-size">{{ pendingFile.size }}</span>
                        </div>
                    </div>
                    <button class="pending-file-remove" @click="removePendingFile" title="移除文件">✕</button>
                </div>
                <textarea 
                    class="input-textarea" 
                    ref="inputText"
                    v-model="inputValue"
                    :placeholder="pendingFile ? '输入对该文件的问题，然后发送...' : placeholder"
                    @input="autoResize"
                    @keydown="handleKeydown"
                ></textarea>
                <div class="input-toolbar">
                    <div class="toolbar-left">
                        <button class="toolbar-btn" @click="selectFile" title="上传文件">
                            📎 上传文件
                        </button>
                        <button class="toolbar-btn" @click="showShortcuts" title="快捷指令">
                            ⚡ 快捷指令
                        </button>
                    </div>
                    <button class="send-btn" :disabled="status === 'busy'" @click="handleSend">
                        <span v-if="status === 'busy'" class="send-loading">⟳</span>
                        <span v-else>➤</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import MessageItem from './MessageItem.vue'
import TypingIndicator from './TypingIndicator.vue'

export default {
    name: 'ChatPanel',
    components: { MessageItem, TypingIndicator },
    props: {
        currentMode: { type: String, default: 'chat' },
        status: { type: String, default: 'ready' }
    },
    data() {
        return {
            inputValue: '',
            messages: [],
            showWelcome: true,
            pendingFile: null  // { path, name, size, isImage }
        }
    },
    computed: {
        placeholder() {
            return this.currentMode === 'chat'
                ? '输入消息，按 Enter 发送，Shift+Enter 换行...'
                : '输入 BUG 描述、指令或搜索关键词...'
        },
        welcomeEmoji() {
            const hour = new Date().getHours()
            if (hour >= 6 && hour < 11) return '🌅'
            if (hour >= 11 && hour < 14) return '☀️'
            if (hour >= 14 && hour < 18) return '☕'
            if (hour >= 18 && hour < 22) return '🌆'
            return '🌙'
        },
        welcomeGreeting() {
            const hour = new Date().getHours()
            if (hour >= 6 && hour < 11) return '早上好！今天也要元气满满地抓 BUG 呀~'
            if (hour >= 11 && hour < 14) return '中午好！吃饱饭了继续消灭 BUG！'
            if (hour >= 14 && hour < 18) return '下午好！来杯咖啡，继续高效排障！'
            if (hour >= 18 && hour < 22) return '晚上好！BUG 不急，注意休息~'
            return '夜深了！熬夜抓 BUG 也要注意身体呀~'
        }
    },
    methods: {
        autoResize() {
            const textarea = this.$refs.inputText
            if (textarea) {
                textarea.style.height = 'auto'
                textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
            }
        },
        handleKeydown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                this.handleSend()
            }
        },
        handleSend() {
            const text = this.inputValue.trim()
            
            // 有待发送文件时
            if (this.pendingFile) {
                this.inputValue = ''
                this.$refs.inputText.style.height = 'auto'
                this.$emit('sendFile', { path: this.pendingFile.path, question: text })
                this.pendingFile = null
                return
            }
            
            // 普通文本消息
            if (!text) return
            this.inputValue = ''
            this.$refs.inputText.style.height = 'auto'
            this.addMessage('user', text)
            this.$emit('send', text)
        },
        async selectFile() {
            this.$emit('selectFile')
        },
        setPendingFile(fileInfo) {
            this.pendingFile = fileInfo
        },
        removePendingFile() {
            this.pendingFile = null
        },
        addMessage(type, content) {
            this.showWelcome = false
            this.messages.push({ type, content })
            
            this.$nextTick(() => {
                const area = this.$refs.messagesArea
                if (type === 'user') {
                    area.scrollTop = area.scrollHeight
                } else {
                    const lastMsg = area.lastElementChild
                    if (lastMsg) {
                        lastMsg.scrollIntoView({ behavior: 'smooth', block: 'start' })
                    }
                }
            })
        },
        hideWelcome() {
            this.showWelcome = false
        },
        clearMessages() {
            this.messages = []
            this.showWelcome = true
        },
        setInputAndSend(text) {
            this.inputValue = text
            this.$nextTick(() => this.handleSend())
        },
        deleteMessage(index) {
            this.messages.splice(index, 1)
            if (this.messages.length === 0) {
                this.showWelcome = true
            }
        },
        async copyMessage(index) {
            const msg = this.messages[index]
            if (!msg) return
            try {
                await navigator.clipboard.writeText(msg.content)
            } catch (e) {
                console.error('复制失败', e)
            }
        },
        showShortcuts() {
            const shortcuts = `
常用快捷指令：
• 新建 BUG 记录
• 列出所有 BUG
• 搜索 [关键词]
• 查看 BUG [编号]
• 帮助
            `.trim()
            this.addMessage('system', shortcuts)
        }
    }
}
</script>

<style scoped>
.chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-base);
    transition: background var(--transition-normal);
}

.messages-area {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-lg);
    display: flex;
    flex-direction: column;
    align-items: center;
}

/* 欢迎消息 */
.welcome-card {
    background: var(--bg-elevated);
    border-radius: var(--radius-lg);
    padding: var(--space-2xl);
    margin: 20px auto;
    max-width: 600px;
    text-align: center;
    border: 1px solid var(--border-secondary);
    box-shadow: var(--shadow-md);
    transition: background var(--transition-normal), border-color var(--transition-normal), box-shadow var(--transition-normal);
}

.welcome-emoji {
    font-size: 48px;
    margin-bottom: var(--space-md);
}

.welcome-title {
    font-size: var(--font-lg);
    font-weight: 600;
    margin-bottom: var(--space-sm);
    color: var(--text-primary);
    line-height: var(--line-height-relaxed);
}

.welcome-desc {
    font-size: var(--font-md);
    color: var(--text-secondary);
    line-height: var(--line-height-relaxed);
}

.welcome-tips {
    margin-top: var(--space-lg);
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-sm);
    justify-content: center;
}

.welcome-tip {
    background: var(--primary-light);
    color: var(--primary);
    padding: 6px 14px;
    border-radius: var(--radius-xl);
    font-size: 13px;
    border: 1px solid var(--primary-border);
    transition: all var(--transition-fast);
}

.welcome-tip:hover {
    box-shadow: var(--shadow-sm);
    transform: translateY(-1px);
}

/* 输入区域 */
.input-area {
    background: linear-gradient(to bottom, transparent, var(--bg-base) 20%);
    padding: var(--space-lg) 20px;
    margin-top: -40px;
    position: relative;
    z-index: 10;
}

.input-wrapper {
    max-width: var(--input-max-width);
    margin: 0 auto;
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-xl);
    padding: var(--space-md) var(--space-lg);
    background: var(--bg-input);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-normal);
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-sm);
}

.input-wrapper:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.15);
}

.input-textarea {
    width: 100%;
    border: none;
    outline: none;
    resize: none;
    font-size: 15px;
    line-height: var(--line-height-normal);
    min-height: 60px;
    max-height: 120px;
    font-family: inherit;
    background: transparent;
    color: var(--text-primary);
    padding: var(--space-sm);
    border-radius: var(--radius-md);
    flex: 6;
}

.input-textarea::placeholder {
    color: var(--text-placeholder);
}

.input-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex: 4;
    min-height: 32px;
}

.toolbar-left {
    display: flex;
    gap: var(--space-sm);
}

.toolbar-btn {
    background: none;
    border: none;
    padding: var(--space-xs) 6px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: var(--font-xs);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    transition: all var(--transition-fast);
}

.toolbar-btn:hover {
    background: var(--primary-light);
    color: var(--primary);
}

.send-btn {
    background: var(--primary);
    color: var(--text-inverse);
    border: none;
    width: 36px;
    height: 36px;
    border-radius: var(--radius-full);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all var(--transition-fast);
    box-shadow: 0 2px 6px rgba(22, 119, 255, 0.3);
}

.send-btn:hover {
    background: var(--primary-hover);
    transform: scale(1.05);
    box-shadow: 0 3px 10px rgba(22, 119, 255, 0.4);
}

.send-btn:disabled {
    background: var(--text-disabled);
    cursor: not-allowed;
    box-shadow: none;
    transform: none;
}

.send-loading {
    display: inline-block;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

/* 待发送文件预览 */
.pending-file {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-container);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    padding: 8px 12px;
    margin-bottom: 8px;
}

.pending-file-info {
    display: flex;
    align-items: center;
    gap: 10px;
}

.pending-file-icon {
    font-size: 24px;
}

.pending-file-detail {
    display: flex;
    flex-direction: column;
}

.pending-file-name {
    font-size: var(--font-sm);
    color: var(--text-primary);
    font-weight: 500;
}

.pending-file-size {
    font-size: 11px;
    color: var(--text-tertiary);
}

.pending-file-remove {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-tertiary);
    font-size: 14px;
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
}

.pending-file-remove:hover {
    color: var(--danger);
    background: rgba(255, 77, 79, 0.1);
}
</style>
