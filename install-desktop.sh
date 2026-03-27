#!/bin/bash
# install-desktop.sh - 安装 AI Agent 桌面快捷方式到 Ubuntu 程序坞

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/ai-agent.desktop"
ICON_FILE="$APP_DIR/assets/icon.svg"

echo "🔧 安装 AI Agent 桌面快捷方式..."

# 确保目录存在
mkdir -p "$HOME/.local/share/applications"

# 生成 .desktop 文件
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=AI Agent
Comment=AI Bug Recording Assistant
Exec=bash $APP_DIR/start.sh
Icon=$ICON_FILE
Terminal=false
Type=Application
Categories=Development;Utility;
StartupWMClass=ai-agent
StartupNotify=true
EOF

# 设置可执行权限
chmod +x "$DESKTOP_FILE"
chmod +x "$APP_DIR/start.sh"

echo "✅ 安装完成！"
echo "📌 快捷方式: $DESKTOP_FILE"
echo ""
echo "现在可以在 Ubuntu 应用菜单中搜索 'AI Agent' 启动"
echo "右键点击图标可以 '添加到收藏夹' 固定到程序坞"
