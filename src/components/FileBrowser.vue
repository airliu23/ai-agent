<template>
    <div class="file-browser-overlay" v-if="visible" @click.self="cancel">
        <div class="file-browser">
            <div class="fb-header">
                <h3>选择文件</h3>
                <button class="fb-close" @click="cancel">✕</button>
            </div>
            
            <div class="fb-toolbar">
                <button class="fb-nav-btn" @click="goUp" :disabled="!parentPath" title="上一级">
                    ⬆️
                </button>
                <button class="fb-nav-btn" @click="goHome" title="主目录">
                    🏠
                </button>
                <div class="fb-path">{{ currentPath }}</div>
            </div>
            
            <div class="fb-content">
                <div class="fb-list" ref="fileList">
                    <div v-if="loading" class="fb-loading">加载中...</div>
                    <div v-else-if="error" class="fb-error">{{ error }}</div>
                    <div v-else>
                        <div 
                            v-for="item in items" 
                            :key="item.path"
                            :class="['fb-item', { 'fb-item-selected': selectedFile?.path === item.path }]"
                            @click="selectItem(item)"
                            @dblclick="openItem(item)"
                        >
                            <span class="fb-item-icon">{{ getIcon(item) }}</span>
                            <span class="fb-item-name">{{ item.name }}</span>
                            <span class="fb-item-size">{{ item.size }}</span>
                        </div>
                    </div>
                </div>
                
                <div class="fb-preview">
                    <div v-if="selectedFile && selectedFile.isImage" class="fb-preview-image">
                        <img :src="getPreviewUrl(selectedFile.path)" :alt="selectedFile.name" />
                    </div>
                    <div v-else-if="selectedFile" class="fb-preview-info">
                        <div class="fb-preview-icon">{{ getIcon(selectedFile) }}</div>
                        <div class="fb-preview-name">{{ selectedFile.name }}</div>
                        <div class="fb-preview-size">{{ selectedFile.size }}</div>
                    </div>
                    <div v-else class="fb-preview-empty">
                        选择文件查看预览
                    </div>
                </div>
            </div>
            
            <div class="fb-footer">
                <div class="fb-selected-name">
                    {{ selectedFile ? selectedFile.name : '未选择文件' }}
                </div>
                <div class="fb-actions">
                    <button class="fb-btn fb-btn-cancel" @click="cancel">取消</button>
                    <button class="fb-btn fb-btn-confirm" @click="confirm" :disabled="!selectedFile || selectedFile.isDir">
                        选择
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'FileBrowser',
    props: {
        visible: { type: Boolean, default: false }
    },
    data() {
        return {
            currentPath: '',
            parentPath: null,
            items: [],
            selectedFile: null,
            loading: false,
            error: null
        }
    },
    watch: {
        visible(val) {
            if (val) {
                this.loadDirectory('~')
            }
        }
    },
    methods: {
        async loadDirectory(path) {
            this.loading = true
            this.error = null
            this.selectedFile = null
            
            try {
                const result = await window.pywebview.api.list_dir(path)
                if (result.success) {
                    this.currentPath = result.path
                    this.parentPath = result.parent
                    this.items = result.items
                } else {
                    this.error = result.error || '加载失败'
                }
            } catch (e) {
                this.error = '加载目录失败: ' + e.message
            } finally {
                this.loading = false
            }
        },
        getIcon(item) {
            if (item.isDir) return '📁'
            if (item.isImage) return '🖼️'
            const ext = item.name.split('.').pop()?.toLowerCase()
            const icons = {
                'pdf': '📕',
                'doc': '📘', 'docx': '📘',
                'xls': '📗', 'xlsx': '📗',
                'txt': '📄', 'md': '📄',
                'py': '🐍', 'js': '📜', 'ts': '📜',
                'json': '📋', 'xml': '📋',
                'zip': '📦', 'rar': '📦', 'tar': '📦', 'gz': '📦'
            }
            return icons[ext] || '📄'
        },
        getPreviewUrl(path) {
            return window.pywebview.api.get_thumbnail_url(path)
        },
        selectItem(item) {
            this.selectedFile = item
        },
        openItem(item) {
            if (item.isDir) {
                this.loadDirectory(item.path)
            } else {
                this.confirm()
            }
        },
        goUp() {
            if (this.parentPath) {
                this.loadDirectory(this.parentPath)
            }
        },
        goHome() {
            this.loadDirectory('~')
        },
        cancel() {
            this.$emit('cancel')
        },
        confirm() {
            if (this.selectedFile && !this.selectedFile.isDir) {
                this.$emit('select', {
                    path: this.selectedFile.path,
                    name: this.selectedFile.name,
                    size: this.selectedFile.size,
                    isImage: this.selectedFile.isImage
                })
            }
        }
    }
}
</script>

<style scoped>
.file-browser-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.file-browser {
    background: #ffffff;
    border-radius: 12px;
    width: 800px;
    max-width: 90vw;
    height: 600px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.fb-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #e5e5e5;
    background: #ffffff;
}

.fb-header h3 {
    margin: 0;
    font-size: 18px;
    color: #1a1a1a;
}

.fb-close {
    background: none;
    border: none;
    font-size: 18px;
    cursor: pointer;
    color: #999;
    padding: 4px 8px;
    border-radius: 4px;
}

.fb-close:hover {
    background: #f5f5f5;
    color: #333;
}

.fb-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    border-bottom: 1px solid #eee;
    background: #f8f9fa;
}

.fb-nav-btn {
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 14px;
}

.fb-nav-btn:hover:not(:disabled) {
    background: #f0f0f0;
}

.fb-nav-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.fb-path {
    flex: 1;
    font-size: 13px;
    color: #666;
    padding: 6px 12px;
    background: #fff;
    border-radius: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.fb-content {
    flex: 1;
    display: flex;
    overflow: hidden;
    background: #fff;
}

.fb-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    border-right: 1px solid #eee;
    background: #fff;
}

.fb-loading, .fb-error {
    padding: 40px;
    text-align: center;
    color: #999;
}

.fb-error {
    color: #ff4d4f;
}

.fb-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s;
}

.fb-item:hover {
    background: #f5f5f5;
}

.fb-item-selected {
    background: #e6f4ff;
}

.fb-item-icon {
    font-size: 20px;
    width: 24px;
    text-align: center;
}

.fb-item-name {
    flex: 1;
    font-size: 13px;
    color: #1a1a1a;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.fb-item-size {
    font-size: 12px;
    color: #999;
}

.fb-preview {
    width: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f8f9fa;
    padding: 20px;
}

.fb-preview-image {
    max-width: 100%;
    max-height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.fb-preview-image img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.fb-preview-info {
    text-align: center;
}

.fb-preview-icon {
    font-size: 64px;
    margin-bottom: 16px;
}

.fb-preview-name {
    font-size: 13px;
    color: #1a1a1a;
    word-break: break-all;
    margin-bottom: 8px;
}

.fb-preview-size {
    font-size: 12px;
    color: #999;
}

.fb-preview-empty {
    color: #999;
    font-size: 13px;
}

.fb-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-top: 1px solid #e5e5e5;
    background: #f8f9fa;
}

.fb-selected-name {
    font-size: 13px;
    color: #666;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.fb-actions {
    display: flex;
    gap: 12px;
}

.fb-btn {
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
}

.fb-btn-cancel {
    background: #fff;
    border: 1px solid #ddd;
    color: #666;
}

.fb-btn-cancel:hover {
    background: #f5f5f5;
}

.fb-btn-confirm {
    background: #1677ff;
    border: none;
    color: white;
}

.fb-btn-confirm:hover:not(:disabled) {
    background: #4096ff;
}

.fb-btn-confirm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
</style>
