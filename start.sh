#!/bin/bash
# 一键启动小说工作站（后端 + 前端）
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

BACKEND_PORT=9000
FRONTEND_PORT=5173

echo "═══════════════════════════════════"
echo "  小说工作站 一键启动"
echo "═══════════════════════════════════"

# ── 先停掉旧进程 ──
echo ""
echo "🔍 检查旧进程..."

kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "   ⚠️  端口 $port 被 PID $pid 占用，杀掉..."
        kill $pid 2>/dev/null
        sleep 1
    fi
}

kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# ── 启动后端 ──
echo ""
echo "🚀 启动后端 (127.0.0.1:$BACKEND_PORT)..."
cd "$BACKEND_DIR"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT &
BACKEND_PID=$!
echo "   后端 PID: $BACKEND_PID"

# ── 等后端就绪 ──
echo "   等待后端就绪..."
for i in $(seq 1 20); do
    if curl -s http://127.0.0.1:$BACKEND_PORT/api/v1/projects > /dev/null 2>&1; then
        echo "   ✅ 后端就绪"
        break
    fi
    sleep 0.5
done

# ── 启动前端 ──
echo ""
echo "🎨 启动前端 (localhost:$FRONTEND_PORT)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "   前端 PID: $FRONTEND_PID"

# ── 等前端就绪 ──
echo "   等待前端就绪..."
for i in $(seq 1 20); do
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        echo "   ✅ 前端就绪"
        break
    fi
    sleep 0.5
done

echo ""
echo "═══════════════════════════════════"
echo "  ✅ 全部就绪"
echo "  后端: http://127.0.0.1:$BACKEND_PORT"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "═══════════════════════════════════"

# ── 等待任意子进程退出 ──
wait