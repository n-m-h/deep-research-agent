#!/bin/bash
# 深度研究助手 - 一键启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "🚀 启动深度研究助手..."
echo ""

# 清理占用端口的进程
cleanup_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        echo "⚠️  端口 $port 被占用，尝试关闭..."
        lsof -i :$port | awk 'NR>1 {print $2}' | xargs kill -9 2>/dev/null
        sleep 1
    fi
}

cleanup_port 8000
cleanup_port 8080

# 激活虚拟环境并启动后端
echo "📦 启动后端服务..."
cd "$BACKEND_DIR"
source venv/bin/activate
python src/main.py &
BACKEND_PID=$!

sleep 3

# 检查后端是否启动成功
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 后端服务已启动: http://localhost:8000"
else
    echo "❌ 后端服务启动失败"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# 启动前端 HTTP 服务器
echo "🌐 启动前端服务..."
cd "$SCRIPT_DIR/frontend"
python -m http.server 8080 &
FRONTEND_PID=$!

sleep 2

echo "✅ 前端服务已启动: http://localhost:8080"
echo ""
echo "🎉 打开浏览器访问 http://localhost:8080 即可使用"
echo ""
echo "按 Ctrl+C 停止服务"

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; deactivate 2>/dev/null; exit" INT TERM

wait
