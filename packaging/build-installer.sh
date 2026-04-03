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

echo "========================================"
echo "构建 EasyDockCross 安装包"
echo "版本: $VERSION"
echo "========================================"

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

# 1. 创建 Python 虚拟环境并安装依赖
echo "[1/5] 安装 Python 依赖到构建目录 (uv)..."
uv venv "$BUILD_DIR/venv"
uv pip install -q -r "$PROJECT_ROOT/requirements.txt" --python "$BUILD_DIR/venv/bin/python"

# 2. 复制应用文件
echo "[2/5] 复制应用文件..."
cp -r "$PROJECT_ROOT/app" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/templates" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/static" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/presets" "$BUILD_DIR/"
cp -r "$PROJECT_ROOT/scripts" "$BUILD_DIR/"
cp "$PROJECT_ROOT/app.py" "$BUILD_DIR/"
cp "$PROJECT_ROOT/requirements.txt" "$BUILD_DIR/"
cp "$PROJECT_ROOT/docker-compose.yml" "$BUILD_DIR/"
cp "$PROJECT_ROOT/.env.example" "$BUILD_DIR/"
cp "$PROJECT_ROOT/VERSION" "$BUILD_DIR/"
cp "$PROJECT_ROOT/CHANGELOG.md" "$BUILD_DIR/" 2>/dev/null || true
cp "$PROJECT_ROOT/README.md" "$BUILD_DIR/" 2>/dev/null || true

# 3. 创建默认配置文件
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
INSTALL_PKG="easydockcross-${VERSION}-linux-x86_64"
TAR_FILE="$DIST_DIR/${INSTALL_PKG}.tar.gz"
(cd "$BUILD_DIR" && tar -czf "$TAR_FILE" .)

# 5. 生成自解压脚本
echo "[4/5] 生成自解压安装脚本..."
SH_FILE="$DIST_DIR/${INSTALL_PKG}.sh"

cat > "$SH_FILE" <<'HEADER'
#!/bin/bash
set -euo pipefail

VERSION="VERSION_PLACEHOLDER"
INSTALL_PREFIX="/opt/easydockcross"
DATA_DIR="/var/lib/easydockcross"
RUN_USER="easydockcross"
USE_SYSTEMD="yes"
SERVICE_PORT="5000"
SKIP_DOCKER_CHECK="no"

print_help() {
    cat <<EOF
EasyDockCross \${VERSION} 安装脚本
用法: sudo ./\$(basename "\$0") [选项]

选项:
  --prefix=PATH         安装目录 (默认: \$INSTALL_PREFIX)
  --data=PATH           数据目录 (默认: \$DATA_DIR)
  --user=NAME           运行用户 (默认: \$RUN_USER)
  --no-systemd          不注册 systemd 服务
  --port=PORT           服务端口 (默认: \$SERVICE_PORT)
  --skip-docker-check   跳过 Docker 检查
EOF
}

for arg in "\$@"; do
    case \$arg in
        --prefix=*) INSTALL="\${arg#*=}" ;;
        --data=*) DATA_DIR="\${arg#*=}" ;;
        --user=*) RUN_USER="\${arg#*=}" ;;
        --no-systemd) USE_SYSTEMD="no" ;;
        --port=*) SERVICE_PORT="\${arg#*=}" ;;
        --skip-docker-check) SKIP_DOCKER_CHECK="yes" ;;
        --help|-h) print_help; exit 0 ;;
    esac
done

echo "======================================"
echo "EasyDockCross \${VERSION} 安装程序"
echo "======================================"

# 1. 自解压
TMPDIR=\$(mktemp -d /tmp/easydockcross-install.XXXXXX)
echo "[1/6] 解压安装包到临时目录 \$TMPDIR..."
ARCHIVE_LINE=\$(awk '/^__ARCHIVE_BELOW__/ {print NR + 1; exit 0; }' "\$0")
tail -n+\$ARCHIVE_LINE "\$0" | tar -xzf - -C "\$TMPDIR"

# 2. 系统检测与 Docker 检查
if [[ "\$SKIP_DOCKER_CHECK" == "no" ]]; then
    echo "[2/6] 检查 Docker..."
    if ! command -v docker \u0026>/dev/null; then
        echo "警告: 未检测到 Docker。EasyDockCross 运行需要 Docker 20.10+。"
        echo "Ubuntu/Debian 安装命令: sudo apt-get install -y docker.io docker-compose-plugin"
        read -p "是否继续安装？(y/N) " -n 1 -r
        echo
        if [[ ! \$REPLY =~ ^[Yy]\$ ]]; then
            rm -rf "\$TMPDIR"
            exit 1
        fi
    fi
else
    echo "[2/6] 跳过 Docker 检查"
fi

# 3. 安装文件
echo "[3/6] 复制文件到 \$INSTALL_PREFIX ..."
mkdir -p "\$INSTALL_PREFIX"
cp -r "\$TMPDIR"/* "\$INSTALL_PREFIX/"
mkdir -p "\$DATA_DIR"

# 4. 创建用户与权限
echo "[4/6] 创建运行用户 \$RUN_USER ..."
if ! id -u "\$RUN_USER" \u003e/dev/null 2\u003e\u00261; then
    useradd -r -s /bin/false -d "\$DATA_DIR" "\$RUN_USER" || true
fi
chown -R "\$RUN_USER:\$RUN_USER" "\$DATA_DIR"
chmod 755 "\$INSTALL_PREFIX"

# 配置文件：写入数据目录和端口
ENV_FILE="\$INSTALL_PREFIX/.env"
cat \u003e "\$ENV_FILE" \u003c\u003cEOF
FLASK_ENV=production
DATA_DIR=\$DATA_DIR
PORT=\$SERVICE_PORT
DOCKER_SOCKET=unix:///var/run/docker.sock
EOF

# 5. 注册 systemd 服务
if [[ "\$USE_SYSTEMD" == "yes" ]] \u0026\u0026 command -v systemctl \u0026\u003e/dev/null; then
    echo "[5/6] 注册 systemd 服务..."
    cat \u003e "/etc/systemd/system/easydockcross.service" \u003c\u003cEOF
[Unit]
Description=EasyDockCross
After=network.target

[Service]
Type=simple
User=\$RUN_USER
WorkingDirectory=\$INSTALL_PREFIX
Environment=FLASK_ENV=production
Environment=DATA_DIR=\$DATA_DIR
Environment=PORT=\$SERVICE_PORT
Environment=PYTHONPATH=\$INSTALL_PREFIX
ExecStart=\$INSTALL_PREFIX/venv/bin/python \$INSTALL_PREFIX/app.py
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
rm -rf "\$TMPDIR"

echo "[6/6] 安装完成！"
echo "--------------------------------------"
echo "访问地址: http://localhost:\$SERVICE_PORT"
echo "数据目录: \$DATA_DIR"
echo "安装目录: \$INSTALL_PREFIX"
echo "服务管理: systemctl {start|stop|restart|status} easydockcross"
echo "--------------------------------------"

exit 0
__ARCHIVE_BELOW__
HEADER

# 替换版本号占位符
sed -i "s/VERSION_PLACEHOLDER/${VERSION}/g" "$SH_FILE"

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
