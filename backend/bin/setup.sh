#!/usr/bin/env bash
# setup.sh — AI Novel Workstation CLI 安装脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NOVEL_SCRIPT="${SCRIPT_DIR}/novel"
TARGET_BIN="/usr/local/bin/novel"

echo "== AI Novel Workstation CLI Setup =="
echo ""

# 检查依赖
echo "→ 检查 Python 环境..."
cd "$(dirname "$SCRIPT_DIR")"

if [ ! -d ".venv" ]; then
    echo "  ⚠ 未找到 .venv，正在创建..."
    python3 -m venv .venv
fi

.venv/bin/pip install -q requests 2>/dev/null

echo "  ✓ requests 已安装"

# 安装 CLI 脚本
echo ""
echo "→ 安装 novel CLI..."

chmod +x "${NOVEL_SCRIPT}"

if [ -w "/usr/local/bin" ]; then
    ln -sf "${NOVEL_SCRIPT}" "${TARGET_BIN}"
    echo "  ✓ 已链接: ${TARGET_BIN} → ${NOVEL_SCRIPT}"
    echo ""
    echo "现在可以直接使用: novel list"
elif [ -w "${HOME}/.local/bin" ]; then
    mkdir -p "${HOME}/.local/bin"
    ln -sf "${NOVEL_SCRIPT}" "${HOME}/.local/bin/novel"
    echo "  ✓ 已链接: ${HOME}/.local/bin/novel → ${NOVEL_SCRIPT}"
    echo "  请确保 ~/.local/bin 在你的 PATH 中"
else
    echo "  ⚠ 无法写入系统路径"
    echo "  手动链接方式:"
    echo "    ln -sf ${NOVEL_SCRIPT} /usr/local/bin/novel  (需要 sudo)"
echo "  或者直接使用后端 Python 运行:"
echo "    backend/.venv/bin/python backend/bin/novel <cmd>"
fi

echo ""
echo "=== Setup 完成 ==="
echo "验证安装: novel list"