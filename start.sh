#!/bin/bash
# start.sh - 启动 AI Agent (Electron + Vue 版本)

cd "$(dirname "$0")"

# 检查 Node.js 是否安装
if ! command -v node &> /dev/null; then
    echo "❌ 未找到 Node.js，请先安装 Node.js"
    exit 1
fi

# 激活 Python 虚拟环境
if [ -f ~/python-venv/bin/activate ]; then
    source ~/python-venv/bin/activate
fi

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python3"
    exit 1
fi

# 检查是否已安装 npm 依赖
if [ ! -d "node_modules" ]; then
    echo "📦 首次运行，正在安装 npm 依赖..."
    npm install
fi

# 检查 Flask 是否安装
python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 正在安装 Python 依赖..."
    pip install flask flask-cors
fi

# 构建并启动（Electron 会自动管理 Python 后端）
npm run start
