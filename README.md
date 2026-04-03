# EasyDockCross

简单的 Docker 交叉构建系统。通过 Web 界面管理多平台编译任务，无需深入了解 Docker。

## 核心功能

- **用户认证**：基于 bcrypt 的账号密码登录，支持管理员与普通用户
- **项目管理**：Wizard 式创建项目，支持 Git / SVN / 本地上传源码
- **多目标构建**：同时构建 Linux / Windows / macOS × x86_64 / arm64 / armv7
- **构建调度器**：最大 3 并发，2 小时超时，支持取消与实时日志
- **自定义镜像**：表单化配置生成 Dockerfile，支持 C++ 构建工具（cmake / xmake / make）
- **产物管理**：构建产物自动收集，支持浏览器下载
- **环境检查**：自动检测 Docker / Python，提供一键安装向导

## 技术栈

- Python 3.11 + Flask + SQLAlchemy + SQLite
- Bootstrap 5 + jQuery 前端
- docker-py + dockcross 镜像生态
- uv 虚拟环境管理

## 快速开始

### 方式一：自解压安装脚本（推荐）

```bash
wget https://github.com/bianc2018/EasyDockCross/releases/download/v0.0.2.0/easydockcross-0.0.2.0-linux-x86_64.sh
chmod +x easydockcross-0.0.2.0-linux-x86_64.sh
sudo ./easydockcross-0.0.2.0-linux-x86_64.sh
```

安装完成后访问 http://localhost:5000，使用自动生成的 `admin` 账号登录。

### 方式二：源码运行（开发）

```bash
git clone https://github.com/bianc2018/EasyDockCross.git
cd EasyDockCross
uv venv
uv pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python app.py
```

## 测试

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -v --cov=app --cov-report=term-missing
```

## 目录结构

```
EasyDockCross/
├── app/              # Flask 后端
├── templates/        # Jinja2 模板
├── static/           # 静态资源
├── presets/          # 构建预设模板
├── packaging/        # 安装包构建脚本
├── tests/            # pytest 测试
└── docs/             # 需求分析与设计文档
```

## 文档

- [CLAUDE.md](./CLAUDE.md) — 项目规范与开发指南
- [TESTING.md](./TESTING.md) — 测试指南
- [CHANGELOG.md](./CHANGELOG.md) — 版本变更记录
- [docs/TODOS.md](./docs/TODOS.md) — 后续规划

## License

MIT
