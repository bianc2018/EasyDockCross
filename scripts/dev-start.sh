#!/usr/bin/env bash
set -euo pipefail

# EasyDockCross 开发环境一键启动脚本（默认使用 uv）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/.venv"
DATA_DIR="$PROJECT_ROOT/data"

export FLASK_ENV="development"
export DATA_DIR="$DATA_DIR"
export PYTHONPATH="$PROJECT_ROOT"

echo "========================================"
echo "EasyDockCross 开发环境启动脚本"
echo "========================================"

# 检查 uv
if ! command -v uv >/dev/null 2>&1; then
    echo "错误: 未找到 uv。请安装 uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo "创建 Python 虚拟环境 (uv)..."
    uv venv "$VENV_DIR"
fi

# 安装依赖
echo "安装依赖 (uv)..."
uv pip install -q -r "$PROJECT_ROOT/requirements.txt" --python "$VENV_DIR/bin/python"

# 确保数据目录存在
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/cache"
mkdir -p "$DATA_DIR/artifacts"
mkdir -p "$DATA_DIR/uploads"
mkdir -p "$DATA_DIR/logs"

echo "启动 Flask 开发服务器..."
echo "数据目录: $DATA_DIR"
echo "访问地址: http://127.0.0.1:5000"
echo "========================================"

exec "$VENV_DIR/bin/python" "$PROJECT_ROOT/app.py"
