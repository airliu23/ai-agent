<template>
    <div class="typing-indicator">
        <div class="typing-bubble">
            <div class="typing-dots">
                <span class="dot"></span>
                <span class="dot"></span>
                <span class="dot"></span>
            </div>
            <span class="typing-text">AI 正在思考...</span>
        </div>
    </div>
</template>

<script>
export default {
    name: 'TypingIndicator'
}
</script>

<style scoped>
.typing-indicator {
    width: 100%;
    max-width: var(--message-max-width);
    display: flex;
    justify-content: flex-start;
    margin-bottom: var(--space-sm);
}

.typing-bubble {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    color: var(--text-tertiary);
    font-size: var(--font-sm);
}

.typing-dots {
    display: flex;
    gap: 4px;
    align-items: center;
}

.dot {
    width: 6px;
    height: 6px;
    border-radius: var(--radius-full);
    background: var(--primary);
    animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }

@keyframes bounce {
    0%, 80%, 100% {
        transform: scale(0.6);
        opacity: 0.4;
    }
    40% {
        transform: scale(1);
        opacity: 1;
    }
}

.typing-text {
    animation: fadeInOut 2s infinite;
}

@keyframes fadeInOut {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}
</style>
