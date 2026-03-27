<template>
    <Transition name="dialog-fade">
        <div class="dialog-overlay" v-if="visible" @click.self="handleCancel">
            <div class="dialog-card">
                <div class="dialog-icon">{{ icon }}</div>
                <div class="dialog-title">{{ title }}</div>
                <div class="dialog-desc">{{ description }}</div>
                <div class="dialog-actions">
                    <button class="dialog-btn btn-cancel" @click="handleCancel">取消</button>
                    <button class="dialog-btn btn-confirm" @click="handleConfirm">{{ confirmText }}</button>
                </div>
            </div>
        </div>
    </Transition>
</template>

<script>
export default {
    name: 'ConfirmDialog',
    props: {
        visible: { type: Boolean, default: false },
        title: { type: String, default: '确认操作' },
        description: { type: String, default: '确定要执行此操作吗？' },
        icon: { type: String, default: '⚠️' },
        confirmText: { type: String, default: '确定' }
    },
    emits: ['confirm', 'cancel'],
    methods: {
        handleConfirm() {
            this.$emit('confirm')
        },
        handleCancel() {
            this.$emit('cancel')
        }
    }
}
</script>

<style scoped>
.dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(2px);
}

.dialog-card {
    background: var(--bg-elevated);
    border-radius: var(--radius-lg);
    padding: var(--space-2xl);
    max-width: 380px;
    width: 90%;
    text-align: center;
    box-shadow: var(--shadow-lg);
    border: 1px solid var(--border-secondary);
}

.dialog-icon {
    font-size: 40px;
    margin-bottom: var(--space-md);
}

.dialog-title {
    font-size: var(--font-lg);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-sm);
}

.dialog-desc {
    font-size: var(--font-md);
    color: var(--text-secondary);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-xl);
}

.dialog-actions {
    display: flex;
    gap: var(--space-md);
    justify-content: center;
}

.dialog-btn {
    padding: var(--space-sm) var(--space-xl);
    border-radius: var(--radius-md);
    font-size: var(--font-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    border: 1px solid var(--border-primary);
    min-width: 80px;
}

.btn-cancel {
    background: var(--bg-elevated);
    color: var(--text-primary);
}

.btn-cancel:hover {
    background: var(--bg-container);
}

.btn-confirm {
    background: var(--danger);
    color: white;
    border-color: var(--danger);
}

.btn-confirm:hover {
    background: #ff7875;
    border-color: #ff7875;
}

/* 动画 */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
    transition: opacity var(--transition-normal);
}

.dialog-fade-enter-active .dialog-card,
.dialog-fade-leave-active .dialog-card {
    transition: transform var(--transition-normal), opacity var(--transition-normal);
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
    opacity: 0;
}

.dialog-fade-enter-from .dialog-card {
    transform: scale(0.9) translateY(10px);
    opacity: 0;
}

.dialog-fade-leave-to .dialog-card {
    transform: scale(0.95);
    opacity: 0;
}
</style>
