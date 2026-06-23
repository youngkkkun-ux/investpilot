#!/bin/bash
# InvestPilot 一键启动脚本

cd "$(dirname "$0")"

# 安装依赖（首次运行）
if ! python3 -c "import fastapi" &>/dev/null; then
    echo ">>> 安装依赖..."
    pip install -r requirements.txt
fi

# 启动后端（同时托管前端静态文件）
echo ""
echo "═══════════════════════════════════════"
echo "  InvestPilot 启动中..."
echo "  访问地址：http://localhost:8000"
echo "═══════════════════════════════════════"
echo ""

cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
