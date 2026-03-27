import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'ai-agent-theme'

// 全局共享状态
const theme = ref(localStorage.getItem(STORAGE_KEY) || 'auto')

export function useTheme() {
    const systemDark = ref(false)
    let mediaQuery = null

    const effectiveTheme = computed(() => {
        if (theme.value === 'auto') {
            return systemDark.value ? 'dark' : 'light'
        }
        return theme.value
    })

    function applyTheme(t) {
        document.documentElement.setAttribute('data-theme', t)
    }

    function setTheme(newTheme) {
        theme.value = newTheme
        localStorage.setItem(STORAGE_KEY, newTheme)
    }

    function toggleTheme() {
        const order = ['light', 'dark', 'auto']
        const currentIndex = order.indexOf(theme.value)
        const nextIndex = (currentIndex + 1) % order.length
        setTheme(order[nextIndex])
    }

    // 图标映射
    const themeIcon = computed(() => {
        switch (theme.value) {
            case 'light': return '☀️'
            case 'dark': return '🌙'
            case 'auto': return '🔄'
            default: return '☀️'
        }
    })

    const themeLabel = computed(() => {
        switch (theme.value) {
            case 'light': return '浅色'
            case 'dark': return '深色'
            case 'auto': return '自动'
            default: return '浅色'
        }
    })

    // 监听生效主题变化，应用到 DOM
    watch(effectiveTheme, (val) => {
        applyTheme(val)
    }, { immediate: true })

    onMounted(() => {
        mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
        systemDark.value = mediaQuery.matches

        const handler = (e) => { systemDark.value = e.matches }
        mediaQuery.addEventListener('change', handler)

        onUnmounted(() => {
            mediaQuery.removeEventListener('change', handler)
        })
    })

    return {
        theme,
        effectiveTheme,
        themeIcon,
        themeLabel,
        setTheme,
        toggleTheme
    }
}
