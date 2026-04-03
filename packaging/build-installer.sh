#!/usr/bin/env bash
set -euo pipefail

# EasyDockCross 自解压安装包构建脚本（默认使用 uv）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/dist/build"
DIST_DIR="$PROJECT_ROOT/dist"
VERSION_FILE="$PROJECT_ROOT/VERSION"

VERSION="$(cat "$VERSION_FILE" | tr -d '[:space:]')"
if [[ -z "$VERSION" ]]; then
    VERSION="0.0.0.1"
fi

# 自动检测架构
HOST_ARCH="$(uname -m)"
if [[ "$HOST_ARCH" == "amd64" || "$HOST_ARCH" == "x86_64" ]]; then
    HOST_ARCH="x86_64"
elif [[ "$HOST_ARCH" == "aarch64" || "$HOST_ARCH" == "arm64" ]]; then
    HOST_ARCH="arm64"
fi

# 允许 ARCH 环境变量覆盖目标架构
TARGET_ARCH="${ARCH:-$HOST_ARCH}"

echo "========================================"
echo "构建 EasyDockCross 安装包"
echo "版本: $VERSION"
echo "目标架构: $TARGET_ARCH"
echo "========================================"

if [[ "$TARGET_ARCH" != "$HOST_ARCH" ]]; then
    echo "警告: 目标架构 ($TARGET_ARCH) 与当前主机架构 ($HOST_ARCH) 不一致。"
    echo "      Python 虚拟环境无法跨架构运行，将构建仅含源码的包。"
    echo "      推荐在对应架构的机器上运行本脚本，或使用 CI matrix 构建。"
    CROSS_ARCH=1
fi

# 检查 uv
if ! command -v uv >/dev/null 2>&1; then
    echo "错误: 未找到 uv。请安装 uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 清理并创建构建目录
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

# 1. 创建 Python 虚拟环境并安装依赖（仅本机架构）
if [[ "${CROSS_ARCH:-0}" == "1" ]]; then
    echo "[1/5] 跨架构构建，跳过本地 venv 创建..."
else
    echo "[1/5] 安装 Python 依赖到构建目录 (uv)..."
    uv venv "$BUILD_DIR/venv"
    uv pip install -q -r "$PROJECT_ROOT/requirements.txt" --python "$BUILD_DIR/venv/bin/python"
fi

# 2. 复制应用文件
echo "[2/5] 复制应用文件..."
mkdir -p "$BUILD_DIR/bin"
cp -r "$PROJECT_ROOT/app" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/templates" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/static" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/presets" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/scripts" "$BUILD_DIR/"
cp "$PROJECT_ROOT/app.py" "$BUILD_DIR/"
cp "$PROJECT_ROOT/requirements.txt" "$BUILD_DIR/"
cp "$PROJECT_ROOT/docker-compose.yml" "$BUILD_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/.env.example" "$BUILD_DIR/"
cp "$PROJECT_ROOT/VERSION" "$BUILD_DIR/"
cp "$PROJECT_ROOT/CHANGELOG.md" "$BUILD_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/README.md" "$BUILD_DIR/" 2>/dev/null || true

# 创建启动脚本
cat > "$BUILD_DIR/bin/start.sh" <<'STARTEOF'
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PREFIX="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="${INSTALL_PREFIX}"
if [[ -f "${INSTALL_PREFIX}/venv/bin/python" ]]; then
    exec "${INSTALL_PREFIX}/venv/bin/python" "${INSTALL_PREFIX}/app.py" "$@"
else
    python3 "${INSTALL_PREFIX}/app.py" "$@"
fi
STARTEOF
chmod +x "$BUILD_DIR/bin/start.sh"

# 3. 创建默认配置文件
mkdir -p "$BUILD_DIR/config"
cat > "$BUILD_DIR/config/default.conf" <<EOF
# EasyDockCross 默认配置
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
FLASK_ENV=production
DATA_DIR=/var/lib/easydockcross
DOCKER_SOCKET=unix:///var/run/docker.sock
MAX_CONCURRENT_BUILDS=3
BUILD_TIMEOUT_SECONDS=7200
EOF

# 4. 打包成 tar.gz
echo "[3/5] 打包应用..."
INSTALL_PKG="easydockcross-${VERSION}-linux-${TARGET_ARCH}"
TAR_FILE="$DIST_DIR/${INSTALL_PKG}.tar.gz"
(cd "$BUILD_DIR" && tar -czf "$TAR_FILE" .)

# 5. 生成自解压脚本
echo "[4/5] 生成自解压安装脚本..."
SH_FILE="$DIST_DIR/${INSTALL_PKG}.sh"

cat > "$SH_FILE" <<'HEADER'
#!/bin/bash
set -euo pipefail

VERSION="VERSION_PLACEHOLDER"
TARGET_ARCH="ARCH_PLACEHOLDER"
INSTALL_PREFIX="/opt/easydockcross"
DATA_DIR="/var/lib/easydockcross"
RUN_USER="easydockcross"
USE_SYSTEMD="yes"
SERVICE_PORT="5000"
SKIP_DOCKER_CHECK="no"

print_help() {
    cat <<EOF
EasyDockCross ${VERSION} (${TARGET_ARCH}) 安装脚本
用法: sudo ./$(basename "$0") [选项]

选项:
  --prefix=PATH         安装目录 (默认: $INSTALL_PREFIX)
  --data=PATH           数据目录 (默认: $DATA_DIR)
  --user=NAME           运行用户 (默认: $RUN_USER)
  --no-systemd          不注册 systemd 服务
  --port=PORT           服务端口 (默认: $SERVICE_PORT)
  --skip-docker-check   跳过 Docker 检查
EOF
}

for arg in "$@"; do
    case $arg in
        --prefix=*) INSTALL_PREFIX="${arg#*=}" ;;
        --data=*) DATA_DIR="${arg#*=}" ;;
        --user=*) RUN_USER="${arg#*=}" ;;
        --no-systemd) USE_SYSTEMD="no" ;;
        --port=*) SERVICE_PORT="${arg#*=}" ;;
        --skip-docker-check) SKIP_DOCKER_CHECK="yes" ;;
        --help|-h) print_help; exit 0 ;;
    esac
done

HOST_ARCH=$(uname -m)
if [[ "$HOST_ARCH" == "amd64" || "$HOST_ARCH" == "x86_64" ]]; then
    HOST_ARCH="x86_64"
elif [[ "$HOST_ARCH" == "aarch64" || "$HOST_ARCH" == "arm64" ]]; then
    HOST_ARCH="arm64"
fi

echo "======================================"
echo "EasyDockCross ${VERSION} (${TARGET_ARCH}) 安装程序"
echo "======================================"

if [[ "$HOST_ARCH" != "$TARGET_ARCH" ]]; then
    echo "警告: 安装包目标架构 ($TARGET_ARCH) 与当前系统架构 ($HOST_ARCH) 不一致。"
    echo "      安装脚本将尝试在本地构建 Python 虚拟环境。"
fi

# 1. 自解压
TMPDIR=$(mktemp -d /tmp/easydockcross-install.XXXXXX)
echo "[1/6] 解压安装包到临时目录 $TMPDIR..."
ARCHIVE_LINE=$(awk '/^__ARCHIVE_BELOW__/ {print NR + 1; exit 0; }' "$0")
tail -n+$ARCHIVE_LINE "$0" | tar -xzf - -C "$TMPDIR"

# 2. 系统检测与 Docker 检查
if [[ "$SKIP_DOCKER_CHECK" == "no" ]]; then
    echo "[2/6] 检查 Docker..."
    if ! command -v docker &>/dev/null; then
        echo "警告: 未检测到 Docker。EasyDockCross 运行需要 Docker 20.10+。"
        echo "Ubuntu/Debian 安装命令: sudo apt-get install -y docker.io docker-compose-plugin"
        read -p "是否继续安装？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$TMPDIR"
            exit 1
        fi
    fi
else
    echo "[2/6] 跳过 Docker 检查"
fi

# 3. 安装文件
echo "[3/6] 复制文件到 $INSTALL_PREFIX ..."
mkdir -p "$INSTALL_PREFIX"
cp -r "$TMPDIR"/* "$INSTALL_PREFIX/"
mkdir -p "$DATA_DIR"

# 3.5 跨架构或缺失 venv 时自动创建
if [[ ! -f "$INSTALL_PREFIX/venv/bin/python" ]]; then
    echo "[3.5/6] 创建 Python 虚拟环境..."
    if command -v uv &>/dev/null; then
        uv venv "$INSTALL_PREFIX/venv"
        uv pip install -q -r "$INSTALL_PREFIX/requirements.txt" --python "$INSTALL_PREFIX/venv/bin/python"
    elif python3 -m venv --help &>/dev/null; then
        python3 -m venv "$INSTALL_PREFIX/venv"
        "$INSTALL_PREFIX/venv/bin/pip" install -q -r "$INSTALL_PREFIX/requirements.txt"
    else
        echo "错误: 未找到 uv 或 python3 -m venv，无法创建虚拟环境。"
        rm -rf "$TMPDIR"
        exit 1
    fi
fi

# 4. 创建用户与权限
echo "[4/6] 创建运行用户 $RUN_USER ..."
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    useradd -r -s /bin/false -d "$DATA_DIR" "$RUN_USER" || true
fi
chown -R "$RUN_USER:$RUN_USER" "$DATA_DIR"
chmod 755 "$INSTALL_PREFIX"

# 配置文件：写入数据目录和端口
ENV_FILE="$INSTALL_PREFIX/.env"
cat > "$ENV_FILE" <<EOF
FLASK_ENV=production
DATA_DIR=$DATA_DIR
PORT=$SERVICE_PORT
DOCKER_SOCKET=unix:///var/run/docker.sock
EOF

# 5. 注册 systemd 服务
if [[ "$USE_SYSTEMD" == "yes" ]] && command -v systemctl &>/dev/null; then
    echo "[5/6] 注册 systemd 服务..."
    cat > "/etc/systemd/system/easydockcross.service" <<EOF
[Unit]
Description=EasyDockCross
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$INSTALL_PREFIX
Environment=FLASK_ENV=production
Environment=DATA_DIR=$DATA_DIR
Environment=PORT=$SERVICE_PORT
Environment=PYTHONPATH=$INSTALL_PREFIX
ExecStart=$INSTALL_PREFIX/venv/bin/python $INSTALL_PREFIX/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable easydockcross.service
    systemctl start easydockcross.service || true
else
    echo "[5/6] 跳过 systemd 注册"
fi

# 6. 清理
rm -rf "$TMPDIR"

echo "[6/6] 安装完成！"
echo "--------------------------------------"
echo "访问地址: http://localhost:$SERVICE_PORT"
echo "数据目录: $DATA_DIR"
echo "安装目录: $INSTALL_PREFIX"
echo "服务管理: systemctl {start|stop|restart|status} easydockcross"
echo "--------------------------------------"

exit 0
__ARCHIVE_BELOW__
HEADER

# 替换占位符
sed -i "s/VERSION_PLACEHOLDER/${VERSION}/g" "$SH_FILE"
sed -i "s/ARCH_PLACEHOLDER/${TARGET_ARCH}/g" "$SH_FILE"

# 追加 tar.gz 数据
cat "$TAR_FILE" >> "$SH_FILE"
chmod +x "$SH_FILE"

# 清理临时文件
rm -rf "$BUILD_DIR"

echo "[5/5] 构建完成！"
echo "输出文件:"
echo "  $SH_FILE"
echo "  $TAR_FILE"
echo "========================================"
