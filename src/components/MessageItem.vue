<template>
    <div :class="['message', type]">
        <div class="message-inner">
            <div class="message-bubble" v-html="renderedContent"></div>
            <!-- hover 操作栏 -->
            <div class="message-actions" v-if="type !== 'system'">
                <button class="action-btn" @click="handleCopy" :title="copyLabel">
                    {{ copyIcon }}
                </button>
                <button class="action-btn action-delete" @click="$emit('delete')" title="删除">
                    🗑
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({
    html: false,
    breaks: true,
    linkify: true,
    typographer: true
})

// 自定义代码块渲染
md.renderer.rules.fence = (tokens, idx) => {
    const token = tokens[idx]
    const code = token.content
    const lang = token.info || 'text'
    const codeId = 'code-' + Math.random().toString(36).substr(2, 9)
    const escapedCode = code.trim()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
    
    return `<div class="code-block">
        <div class="code-header">
            <span class="code-lang">${lang}</span>
            <button class="copy-btn" data-code-id="${codeId}" title="复制">⧉</button>
        </div>
        <pre><code id="${codeId}">${escapedCode}</code></pre>
    </div>`
}

export default {
    name: 'MessageItem',
    props: {
        type: { type: String, required: true },
        content: { type: String, required: true }
    },
    emits: ['copy', 'delete'],
    data() {
        return {
            copied: false
        }
    },
    computed: {
        renderedContent() {
            if (this.type === 'user') {
                return this.escapeHtml(this.content).replace(/\n/g, '<br>')
            }
            let html = md.render(String(this.content))
            return DOMPurify.sanitize(html, {
                ADD_TAGS: ['button'],
                ADD_ATTR: ['onclick', 'title', 'data-code-id']
            })
        },
        copyIcon() {
            return this.copied ? '✓' : '📋'
        },
        copyLabel() {
            return this.copied ? '已复制' : '复制'
        }
    },
    mounted() {
        this.setupCopyButtons()
    },
    updated() {
        this.setupCopyButtons()
    },
    methods: {
        escapeHtml(text) {
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
        },
        async handleCopy() {
            try {
                await navigator.clipboard.writeText(this.content)
                this.copied = true
                this.$emit('copy')
                setTimeout(() => { this.copied = false }, 2000)
            } catch (e) {
                console.error('复制失败', e)
            }
        },
        setupCopyButtons() {
            this.$el.querySelectorAll('.copy-btn').forEach(btn => {
                btn.onclick = async () => {
                    const codeId = btn.getAttribute('data-code-id')
                    const codeEl = document.getElementById(codeId)
                    if (!codeEl) return
                    
                    try {
                        await navigator.clipboard.writeText(codeEl.textContent)
                        btn.textContent = '✓'
                        btn.classList.add('copied')
                        setTimeout(() => {
                            btn.textContent = '⧉'
                            btn.classList.remove('copied')
                        }, 2000)
                    } catch (err) {
                        btn.textContent = '✗'
                        setTimeout(() => { btn.textContent = '⧉' }, 2000)
                    }
                }
            })
        }
    }
}
</script>

<style scoped>
.message {
    margin-bottom: var(--space-sm);
    width: 100%;
    max-width: var(--message-max-width);
    display: flex;
    flex-direction: column;
}

.message.user { align-items: flex-end; }
.message.ai { align-items: flex-start; }
.message.system { align-items: center; }

.message-inner {
    position: relative;
    max-width: 100%;
}

.message.user .message-inner { max-width: 75%; }
.message.ai .message-inner { max-width: 95%; }
.message.system .message-inner { max-width: 60%; }

.message-bubble {
    padding: var(--space-sm) 10px;
    border-radius: var(--radius-md);
    line-height: 1.4;
    font-size: var(--font-md);
    min-width: 100px;
    word-wrap: break-word;
    transition: background var(--transition-normal);
}

.message.user .message-bubble {
    background: var(--primary-light);
    color: var(--text-primary);
    border: 1px solid var(--primary-border);
    border-bottom-right-radius: var(--radius-sm);
    box-shadow: var(--shadow-sm);
}

.message.ai .message-bubble {
    background: transparent;
    color: var(--text-primary);
    border: none;
    border-bottom-left-radius: var(--radius-sm);
}

.message.system .message-bubble {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    text-align: center;
    font-size: 13px;
}

/* hover 操作栏 */
.message-actions {
    position: absolute;
    top: -4px;
    right: 0;
    display: flex;
    gap: 2px;
    opacity: 0;
    transform: translateY(-4px);
    transition: all var(--transition-fast);
    background: var(--bg-elevated);
    border: 1px solid var(--border-secondary);
    border-radius: var(--radius-md);
    padding: 2px;
    box-shadow: var(--shadow-md);
}

.message.ai .message-actions {
    right: auto;
    left: 0;
}

.message-inner:hover .message-actions {
    opacity: 1;
    transform: translateY(-8px);
}

.action-btn {
    width: 26px;
    height: 26px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-tertiary);
    transition: all var(--transition-fast);
}

.action-btn:hover {
    background: var(--primary-light);
    color: var(--primary);
}

.action-delete:hover {
    background: var(--danger-light);
    color: var(--danger);
}
</style>

<style>
/* 代码块样式 - 非 scoped */
.code-block {
    display: block;
    width: 100%;
    margin: var(--space-sm) 0;
    border-radius: var(--radius-md);
    overflow: hidden;
    background: var(--bg-code);
    border: 1px solid var(--border-light);
    transition: background var(--transition-normal), border-color var(--transition-normal);
}

.code-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 6px;
    background: transparent;
    border-bottom: none;
}

.code-lang {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    color: var(--text-tertiary);
    font-weight: 400;
    text-transform: capitalize;
}

.code-lang::before {
    content: "</>";
    font-family: "SF Mono", monospace;
    font-size: 8px;
    color: var(--text-disabled);
}

.copy-btn {
    width: 18px;
    height: 18px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    color: var(--text-disabled);
    transition: all var(--transition-fast);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
}

.copy-btn:hover { color: var(--text-tertiary); }
.copy-btn.copied { color: var(--success); }

.message-bubble pre {
    margin: 0;
    padding: 2px 6px 6px 6px;
    overflow-x: auto;
    background: transparent;
}

.message-bubble pre code {
    background: transparent;
    padding: 0;
    font-family: "SF Mono", "Monaco", "Inconsolata", "Consolas", monospace;
    font-size: var(--font-sm);
    line-height: 1.4;
    color: var(--text-primary);
    white-space: pre;
}

.message-bubble code:not(pre code) {
    background: var(--bg-code);
    padding: 2px 5px;
    border-radius: 3px;
    font-family: "SF Mono", "Monaco", "Inconsolata", "Consolas", monospace;
    font-size: var(--font-sm);
    color: var(--text-primary);
    border: 1px solid var(--border-light);
}

.message-bubble h1, .message-bubble h2, .message-bubble h3,
.message-bubble h4, .message-bubble h5, .message-bubble h6 {
    margin: var(--space-lg) 0 var(--space-sm) 0;
    font-weight: 600;
    line-height: var(--line-height-tight);
    color: var(--text-primary);
}

.message-bubble h1 { font-size: var(--font-xl); border-bottom: 1px solid var(--border-secondary); padding-bottom: 6px; margin-top: var(--space-xl); }
.message-bubble h2 { font-size: 17px; border-bottom: 1px solid var(--border-secondary); padding-bottom: 4px; margin-top: 18px; }
.message-bubble h3 { font-size: 15px; margin-top: var(--space-md); }
.message-bubble h4 { font-size: var(--font-md); margin-top: var(--space-md); }

.message-bubble ul, .message-bubble ol { margin: var(--space-sm) 0; padding-left: 20px; }
.message-bubble li { margin: var(--space-xs) 0; line-height: var(--line-height-normal); }
.message-bubble ul li { list-style-type: disc; }
.message-bubble ol li { list-style-type: decimal; }

.message-bubble strong { font-weight: 600; color: var(--text-primary); }
.message-bubble em { font-style: italic; }

.message-bubble blockquote {
    margin: var(--space-sm) 0;
    padding: 0 var(--space-md);
    border-left: 3px solid var(--primary-border);
    color: var(--text-secondary);
}

.message-bubble a { color: var(--primary); text-decoration: none; }
.message-bubble a:hover { text-decoration: underline; }

.message-bubble hr { height: 1px; background: var(--border-secondary); border: none; margin: var(--space-md) 0; }

.message-bubble table { border-collapse: collapse; margin: var(--space-sm) 0; width: 100%; font-size: 13px; }
.message-bubble th, .message-bubble td { border: 1px solid var(--border-primary); padding: 6px 10px; text-align: left; color: var(--text-primary); }
.message-bubble th { background: var(--bg-container); font-weight: 600; }

.message-bubble p { margin: 6px 0; line-height: var(--line-height-normal); color: var(--text-primary); }
</style>
