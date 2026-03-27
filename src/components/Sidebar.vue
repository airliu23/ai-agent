<template>
    <div :class="['sidebar', { collapsed }]">
        <div class="sidebar-toggle" @click="collapsed = !collapsed" title="展开/收起">◀</div>
        
        <!-- 标题区域 -->
        <div class="sidebar-header">
            <div class="sidebar-title">🐞 AI Agent</div>
            <div class="sidebar-subtitle">智能管理助手</div>
        </div>

        <div class="sidebar-divider"></div>

        <!-- 新建对话按钮 -->
        <button class="new-chat-btn" :title="collapsed ? '新建对话' : ''" @click="$emit('newSession')">
            ✨ <span>新建对话</span>
        </button>

        <div class="sidebar-divider"></div>

        <!-- 会话列表 -->
        <div class="session-section" v-if="!collapsed">
            <div class="mode-title">历史对话</div>
            <div class="session-list">
                <div 
                    v-for="session in sessions" 
                    :key="session.id"
                    :class="['session-item', { active: session.id === currentSessionId }]"
                    @click="$emit('switchSession', session.id)"
                >
                    <div class="session-info">
                        <div class="session-title">{{ session.title }}</div>
                        <div class="session-meta">{{ formatTime(session.last_update) }}</div>
                    </div>
                    <button 
                        class="session-delete" 
                        @click.stop="$emit('deleteSession', session.id)"
                        title="删除对话"
                    >✕</button>
                </div>
                <div v-if="sessions.length === 0" class="session-empty">暂无历史对话</div>
            </div>
        </div>

        <div class="sidebar-divider"></div>

        <div class="mode-section">
            <div class="mode-title">工作模式</div>
            <button 
                :class="['mode-btn', { active: currentMode === 'chat' }]"
                :title="collapsed ? '对话模式' : ''"
                @click="$emit('setMode', 'chat')"
            >
                💬 <span>对话模式</span>
            </button>
            <button 
                :class="['mode-btn', { active: currentMode === 'bug' }]"
                :title="collapsed ? 'BUG 模式' : ''"
                @click="$emit('setMode', 'bug')"
            >
                🐞 <span>BUG 模式</span>
            </button>
        </div>

        <div class="sidebar-divider"></div>

        <button class="sidebar-action" :title="collapsed ? '查看所有 BUG' : ''" @click="$emit('listBugs')">
            📋 <span>查看所有 BUG</span>
        </button>
        <button class="sidebar-action" :title="collapsed ? '搜索 BUG' : ''" @click="$emit('searchBugs')">
            🔍 <span>搜索 BUG</span>
        </button>
        <button class="sidebar-action" :title="collapsed ? '清空对话上下文' : ''" @click="$emit('clearChatContext')">
            🧠 <span>清空对话上下文</span>
        </button>

        <div class="sidebar-divider"></div>

        <button class="sidebar-action" :title="collapsed ? '清空对话' : ''" @click="$emit('clearOutput')">
            🗑️ <span>清空对话</span>
        </button>
        <button class="sidebar-action" :title="collapsed ? '新建 BUG' : ''" @click="$emit('newRecord')">
            🆕 <span>新建 BUG</span>
        </button>

        <!-- 底部填充 -->
        <div class="sidebar-spacer"></div>

        <!-- 主题切换 -->
        <div class="sidebar-divider"></div>
        <button class="sidebar-action theme-toggle" :title="collapsed ? themeLabel : ''" @click="toggleTheme">
            {{ themeIcon }} <span>{{ themeLabel }}</span>
        </button>
    </div>
</template>

<script>
import { useTheme } from '../composables/useTheme.js'

export default {
    name: 'Sidebar',
    props: {
        currentMode: { type: String, default: 'chat' },
        sessions: { type: Array, default: () => [] },
        currentSessionId: { type: String, default: '' }
    },
    setup() {
        const { themeIcon, themeLabel, toggleTheme } = useTheme()
        return { themeIcon, themeLabel, toggleTheme }
    },
    data() {
        return {
            collapsed: false
        }
    },
    methods: {
        formatTime(isoStr) {
            if (!isoStr) return ''
            try {
                const d = new Date(isoStr)
                const now = new Date()
                const isToday = d.toDateString() === now.toDateString()
                if (isToday) {
                    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
                }
                return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
            } catch {
                return ''
            }
        }
    }
}
</script>

<style scoped>
.sidebar {
    width: var(--sidebar-width);
    background: var(--bg-elevated);
    border-right: 1px solid var(--border-secondary);
    display: flex;
    flex-direction: column;
    padding: var(--space-md);
    transition: width var(--transition-slow), background var(--transition-normal), border-color var(--transition-normal);
    position: relative;
}

.sidebar-header {
    margin-bottom: var(--space-sm);
}

.sidebar-title {
    font-size: var(--font-md);
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
}

.sidebar-subtitle {
    font-size: 10px;
    color: var(--text-secondary);
    margin-top: 2px;
    white-space: nowrap;
}

.sidebar.collapsed .sidebar-header {
    display: none;
}

.sidebar.collapsed {
    width: var(--sidebar-collapsed-width);
    padding: var(--space-md) var(--space-sm);
}

.sidebar-toggle {
    position: absolute;
    right: -12px;
    top: 16px;
    width: 24px;
    height: 24px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-secondary);
    border-radius: var(--radius-full);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-sm);
    color: var(--text-tertiary);
    z-index: 10;
    transition: transform var(--transition-slow), background var(--transition-fast), box-shadow var(--transition-fast);
    box-shadow: var(--shadow-sm);
}

.sidebar-toggle:hover {
    box-shadow: var(--shadow-md);
    color: var(--primary);
}

.sidebar.collapsed .sidebar-toggle {
    transform: rotate(180deg);
}

.sidebar.collapsed .mode-title,
.sidebar.collapsed .mode-btn span,
.sidebar.collapsed .sidebar-action span {
    display: none;
}

.sidebar.collapsed .mode-btn,
.sidebar.collapsed .sidebar-action {
    justify-content: center;
    padding: 10px;
}

.mode-section {
    margin-bottom: var(--space-xl);
}

.mode-title {
    font-size: var(--font-xs);
    color: var(--text-tertiary);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.mode-btn {
    width: 100%;
    padding: var(--space-sm) 10px;
    border: 1px solid var(--border-primary);
    background: linear-gradient(to bottom, var(--bg-elevated), var(--bg-container));
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    transition: all var(--transition-fast);
    white-space: nowrap;
    box-shadow: var(--shadow-sm);
}

.mode-btn:hover {
    background: var(--primary-light);
    border-color: var(--primary-border);
    color: var(--primary);
    box-shadow: var(--shadow-md);
}

.mode-btn.active {
    background: var(--primary);
    border-color: var(--primary);
    color: var(--text-inverse);
    box-shadow: 0 2px 8px rgba(22, 119, 255, 0.35);
}

.sidebar-divider {
    height: 1px;
    background: var(--border-secondary);
    margin: var(--space-lg) 0;
    transition: background var(--transition-normal);
}

/* 新建对话按钮 */
.new-chat-btn {
    width: 100%;
    padding: var(--space-sm) 10px;
    border: 1px dashed var(--primary-border);
    background: var(--primary-light);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13px;
    color: var(--primary);
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all var(--transition-fast);
    white-space: nowrap;
    font-weight: 500;
}

.new-chat-btn:hover {
    background: var(--primary);
    color: var(--text-inverse);
    border-style: solid;
    box-shadow: 0 2px 8px rgba(22, 119, 255, 0.35);
}

.sidebar.collapsed .new-chat-btn span {
    display: none;
}

.sidebar.collapsed .new-chat-btn {
    justify-content: center;
    padding: 10px;
}

/* 会话列表 */
.session-section {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.session-list {
    max-height: 200px;
    overflow-y: auto;
    overflow-x: hidden;
}

.session-list::-webkit-scrollbar {
    width: 3px;
}

.session-list::-webkit-scrollbar-thumb {
    background: var(--border-primary);
    border-radius: 3px;
}

.session-item {
    display: flex;
    align-items: center;
    padding: 8px 10px;
    border-radius: var(--radius-md);
    cursor: pointer;
    margin-bottom: 2px;
    transition: all var(--transition-fast);
    gap: 4px;
}

.session-item:hover {
    background: var(--primary-light);
}

.session-item.active {
    background: var(--primary-light);
    border-left: 3px solid var(--primary);
}

.session-info {
    flex: 1;
    min-width: 0;
}

.session-title {
    font-size: var(--font-sm);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.session-item.active .session-title {
    color: var(--primary);
    font-weight: 500;
}

.session-meta {
    font-size: 10px;
    color: var(--text-tertiary);
    margin-top: 2px;
}

.session-delete {
    opacity: 0;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-tertiary);
    font-size: 12px;
    padding: 2px 4px;
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
    flex-shrink: 0;
}

.session-item:hover .session-delete {
    opacity: 1;
}

.session-delete:hover {
    color: var(--danger);
    background: rgba(255, 77, 79, 0.1);
}

.session-empty {
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--font-xs);
    padding: var(--space-lg) 0;
}

.sidebar-action {
    width: 100%;
    padding: 6px 10px;
    border: none;
    background: transparent;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: var(--font-sm);
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 2px;
    transition: all var(--transition-fast);
    white-space: nowrap;
}

.sidebar-action:hover {
    background: var(--primary-light);
    color: var(--primary);
}

.sidebar-spacer {
    flex: 1;
}

.theme-toggle {
    color: var(--text-secondary);
}

.theme-toggle:hover {
    background: var(--primary-light);
    color: var(--primary);
}
</style>
