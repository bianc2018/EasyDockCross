#!/usr/bin/env bash
set -euo pipefail

# EasyDockCross 开发环境一键启动脚本

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

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 安装依赖
echo "安装依赖..."
pip install -q --upgrade pip
pip install -q -r "$PROJECT_ROOT/requirements.txt"

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

exec python "$PROJECT_ROOT/app.py"
