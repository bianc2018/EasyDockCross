# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EasyDockCross** (简单的交叉构建系统) is a Docker-based cross-compilation build web system. It provides a web interface for managing build tasks that run inside Docker containers, supporting cross-platform compilation for multiple programming languages.

### Core Features (Planned)
- User authentication (simple username/password with Flask-Login)
- Project management with YAML configuration
- Build task management and scheduling
- Docker-based builds for Go, Python, Java, Node.js, and C++
- C++ build tool support (cmake, xmake, make)
- Custom image management based on dockcross
- Dependency checking with auto-installation
- Real-time build logs via WebSocket

### Tech Stack
- **Backend**: Python 3.8+, Flask, SQLAlchemy, SQLite
- **Authentication**: Flask-Login + bcrypt
- **Docker Integration**: docker-py
- **Frontend**: Bootstrap 5, jQuery, Jinja2 templates
- **Configuration**: PyYAML

## Documentation Structure

All project documentation is in `docs/需求分析/`:

| Document | Purpose |
|----------|---------|
| `ALIGNMENT_需求分析.md` | Requirements alignment and clarification |
| `CONSENSUS_需求分析.md` | Agreed requirements and acceptance criteria |
| `DESIGN_需求分析.md` | System architecture and API design |
| `TASK_需求分析.md` | Task breakdown with dependencies and acceptance criteria |
| `APPROVAL_需求分析.md` | Approval checklist and final confirmation |

## Development Phases (MVP)

### Phase 1 - 基础框架
- **TASK-001**: 项目初始化
  - 创建 Flask 应用骨架
  - 配置文件管理
  - start.sh 一键启动脚本
  
- **TASK-011**: 依赖检查模块
  - 检查 Docker 安装
  - 自动安装引导
  - 预下载常用镜像

### Phase 2 - 数据层
- **TASK-002**: 数据库模型
  - User, Project, BuildTarget, BuildTask, BuildGroup, CustomImage, BuildArtifact
  - 数据库迁移脚本

### Phase 3 - 核心模块
- **TASK-003**: 认证模块
  - 简单登录/登出
  - 会话管理

- **TASK-004**: 项目管理
  - Wizard 式项目创建（6 步骤）
  - 源码管理（上传/Git/SVN）
  - 多目标构建配置

- **TASK-005**: 构建管理
  - 构建调度器（并发控制）
  - 构建日志实时推送
  - 产物管理

### Phase 4 - Docker 集成
- **TASK-006**: Docker 客户端
  - 容器生命周期管理
  - 日志流式读取
  - 产物收集

- **TASK-009**: C++ 构建支持
  - cmake/xmake/make 支持

### Phase 5 - 环境管理
- **TASK-010**: 自定义镜像管理
  - 双模式配置（简单/复杂）
  - Dockerfile 自动生成
  - 镜像构建与缓存

### Phase 6 - Web 界面
- **TASK-007**: Web 界面
  - 项目创建 Wizard
  - 构建状态监控
  - 环境管理页面
  - 实时日志查看

### Phase 7 - 打包发布
- **TASK-008**: 自解压安装脚本
  - `packaging/build-installer.sh` - 构建自解压 .sh 脚本
  - 脚本模板：解压逻辑、系统检测、自动安装
  - 支持多架构 (x86_64, arm64)
  - CI/CD 自动构建发布

## Key Architecture Decisions

### MVP 核心原则
- **零 Docker 门槛**: 用户无需了解 Docker，安装包自动处理依赖
- **离线部署**: 输出 Linux 安装包(.tar.gz)，内含完整运行环境
- **开箱即用**: 一键安装脚本，SQLite 零配置，预设环境镜像自动下载

### 部署架构
- **安装包分发**: 构建 tar.gz 安装包，内含 Python 虚拟环境、依赖、脚本
- **系统服务**: 可选 systemd 服务注册，开机自启
- **Docker 仅用于构建**: 仅用于创建/运行构建容器，用户无感知
- **单机构建**: 本地 SQLite + 本地文件存储，无外部依赖

### 构建系统
- **多目标并行构建**: 支持同时构建多个目标（Linux/Windows/macOS × x86/arm）
- **并发限制**: 最多 3 个并发构建任务
- **产物类型**: 支持二进制文件和 Docker 镜像
- **触发方式**: 手动触发、Webhook、定时任务（cron）

### 环境管理
- **双模式配置**:
  - 简单模式: 表单填写依赖、工具、环境变量
  - 复杂模式: 直接编辑 YAML 配置
- **自动生成 Dockerfile**: 基于 YAML 配置自动生成
- **基于 dockcross**: 预设常用交叉编译环境

### 源码管理
- **支持多种来源**: 本地上传（zip/tar）、Git、SVN
- **自动拉取**: 构建时自动拉取最新代码

## Common Commands (To Be Implemented)

Once code is implemented, the following commands will be relevant:

```bash
# Setup
pip install -r requirements.txt

# Development
python app.py                    # Run Flask dev server
flask db init                    # Initialize database

# Testing (when added)
pytest                           # Run all tests
pytest tests/test_auth.py        # Run specific test module

# Docker build
docker-compose up -d             # Start with Docker Compose
./scripts/build.sh               # Build Docker image
./scripts/deploy.sh              # Deploy script
```

## Data Models

### Core Models

**User**: id, username, password_hash, created_at, is_admin

**Project**:
- id, name, description, created_at, updated_at
- source_type: git/svn/upload
- source_url, source_branch, source_credentials
- triggers: JSON (手动/webhook/定时)

**BuildTarget**（新增，多目标构建）:
- id, project_id, name
- output_type: binary/docker
- os, distro, arch
- image: 使用的环境镜像
- build_command, env_vars
- artifacts_path

**BuildTask**:
- id, project_id, target_id, build_group_id
- status: pending/running/success/failed/cancelled
- container_id, start_time, end_time
- output_log, error_log

**BuildGroup**（新增，一次构建包含多个目标）:
- id, project_id, trigger_type
- status, created_at, completed_at

**CustomImage**（环境管理）:
- id, name, description, base_image
- config_yaml: 简单/复杂模式配置
- generated_dockerfile: 自动生成的 Dockerfile
- status: building/ready/failed
- image_id, build_log, created_at, updated_at

**BuildArtifact**:
- id, build_task_id, file_path, file_size, download_url

## Project Creation Flow (Wizard)

```
步骤 1: 项目基本信息
  └─ 名称、描述

步骤 2: 源码来源
  ├─ 本地上传 (zip/tar)
  ├─ Git 仓库 (https/ssh)
  └─ SVN 仓库

步骤 3: 构建目标（可添加多个）
  ├─ 产物类型: binary / docker
  ├─ 目标系统: Linux(Debian/Ubuntu/Alpine) / Windows / macOS
  └─ 目标架构: x86_64 / arm64 / armv7

步骤 4: 环境配置
  ├─ 自动推荐（基于语言和目标）
  ├─ 选择预设环境
  └─ 自定义环境（跳转环境管理）

步骤 5: 构建指令
  ├─ 统一配置（所有目标相同）
  └─ 单独配置（每个目标不同）

步骤 6: 触发方式
  ├─ 手动触发
  ├─ Webhook (git push)
  └─ 定时触发 (cron)
```

## Environment Management

### 双模式配置

**简单模式**: 表单填写
- 系统依赖包（带自动补全）
- 开发工具（常用工具预设）
- 环境变量
- 预构建脚本

**复杂模式**: YAML 编辑
- 直接编辑原始配置
- 完全自定义
- 支持高级特性

### 自动生成 Dockerfile
基于配置和目标平台自动生成：
```dockerfile
FROM easydockcross/go-linux-x86_64:latest
RUN apt-get update && apt-get install -y libssl-dev libffi-dev
# ... 根据配置生成
```

## Core Modules

### 1. 构建调度器 (BuildScheduler)
- 任务队列管理
- 并发控制（最多 3 个）
- 多目标并行执行
- 构建状态追踪

### 2. 环境管理器 (ImageManager)
- 预设镜像管理
- 自定义镜像构建
- Dockerfile 生成
- 镜像缓存管理

### 3. 源码管理器 (SourceManager)
- 文件上传处理
- Git/SVN 拉取
- 凭证管理
- 代码缓存

### 4. 日志服务 (LogService)
- WebSocket 实时推送
- 日志存储和检索
- 多构建目标日志隔离

## CLI Commands

安装后提供系统命令：

```bash
# 服务管理
easydockcross start          # 启动服务
easydockcross stop           # 停止服务
easydockcross restart        # 重启服务
easydockcross status         # 查看状态

# 管理命令
easydockcross config         # 编辑配置
easydockcross logs           # 查看日志
easydockcross doctor         # 诊断检查

# 高级管理（edc-admin）
edc-admin backup             # 备份数据
edc-admin restore            # 恢复数据
edc-admin upgrade            # 升级版本
edc-admin reset-password     # 重置管理员密码
```

## API Conventions

### Authentication
- `POST /api/login` / `POST /api/logout`

### Projects
- `GET /api/projects` / `POST /api/projects` - 列表/创建
- `GET /api/projects/:id` / `PUT /api/projects/:id` / `DELETE /api/projects/:id`

### Build Targets
- `GET /api/projects/:id/targets` / `POST /api/projects/:id/targets`
- `PUT /api/targets/:id` / `DELETE /api/targets/:id`

### Build Tasks
- `POST /api/projects/:id/build` - 创建构建任务组
- `GET /api/builds/:group_id` - 获取构建组状态
- `GET /api/builds/:id/log` - 流式日志 (SSE/WebSocket)
- `POST /api/builds/:id/cancel` - 取消构建

### Build Artifacts
- `GET /api/builds/:id/artifacts` - 产物列表
- `GET /api/artifacts/:id/download` - 下载产物

### Environment (Custom Images)
- `GET /api/images` / `POST /api/images` - 环境列表/创建
- `GET /api/images/:id` / `PUT /api/images/:id` / `DELETE /api/images/:id`
- `POST /api/images/:id/build` - 构建环境镜像
- `GET /api/images/:id/build-log` - 构建日志
- `POST /api/images/preview` - 预览 Dockerfile

## Directory Structure

### 开发目录
```
EasyDockCross/
├── app/                      # Flask 应用
│   ├── __init__.py
│   ├── app.py               # 应用工厂
│   ├── config.py            # 配置
│   ├── models.py            # 数据模型
│   ├── auth.py              # 认证模块
│   ├── project.py           # 项目管理
│   ├── build.py             # 构建管理
│   ├── image_manager.py     # 环境管理
│   ├── docker_client.py     # Docker 客户端
│   └── utils.py             # 工具函数
├── templates/               # Jinja2 模板
├── static/                  # 静态资源
├── presets/                 # 预设配置
│   ├── environments/        # 环境预设
│   └── dockerfiles/         # 基础 Dockerfile
├── packaging/               # 打包脚本
│   ├── build-package.sh     # 构建安装包
│   └── install-template.sh  # 安装脚本模板
├── scripts/                 # 开发脚本
│   └── dev-start.sh         # 开发启动
├── requirements.txt
└── CLAUDE.md
```

### 输出产物（自解压安装脚本）
```
easydockcross-1.0.0-linux-x86_64.sh    # 自解压安装脚本
```

脚本内部结构：
```
├─ 自解压头（shell 脚本）
│   ├─ 解压逻辑
│   ├─ 系统检测
│   ├─ 依赖检查/安装引导
│   ├─ 自动安装流程
│   └─ 清理临时文件
│
└─ 内嵌 tar 包
   ├─ venv/                # Python 虚拟环境
   ├─ app/                 # 应用代码
   ├─ presets/             # 预设环境配置
   ├─ bin/                 # 可执行脚本
   └─ config/              # 默认配置
```

## Packaging

### 构建自解压安装脚本

```bash
# 开发环境构建设置包
./packaging/build-installer.sh

# 输出
dist/
├── easydockcross-1.0.0-linux-x86_64.sh
└── easydockcross-1.0.0-linux-arm64.sh
```

### 安装脚本功能

自解压脚本包含：
- 嵌入式 tar 包（应用 + venv + 配置）
- 解压逻辑（解压到临时目录）
- 系统检测（发行版、架构、Docker）
- 自动安装（文件复制、权限设置、服务注册）
- 启动服务
- 清理临时文件

### 安装命令行选项

```bash
sudo ./easydockcross-1.0.0-linux-x86_64.sh [选项]
  --prefix=/opt/easydockcross    # 安装目录
  --data=/var/lib/easydockcross  # 数据目录
  --user=easydockcross           # 运行用户
  --no-systemd                   # 不注册系统服务
  --port=5000                    # 服务端口
  --skip-docker-check            # 跳过 Docker 检查
```

### 安装流程

```
┌─────────────────────────────────────────┐
│  1. 用户运行 .sh 脚本                    │
│     sudo ./easydockcross-xxx.sh         │
├─────────────────────────────────────────┤
│  2. 脚本自解压到 /tmp                    │
├─────────────────────────────────────────┤
│  3. 系统检测                             │
│     - 检查 Linux 发行版                  │
│     - 检查 Docker 状态                   │
│     - 如未安装，提示或自动安装            │
├─────────────────────────────────────────┤
│  4. 安装文件                             │
│     - 复制到 /opt/easydockcross          │
│     - 创建 /var/lib/easydockcross        │
│     - 设置权限                           │
├─────────────────────────────────────────┤
│  5. 注册服务（可选）                      │
│     - 创建 systemd service               │
│     - 创建命令软链接                      │
├─────────────────────────────────────────┤
│  6. 启动服务                             │
│     - systemctl start easydockcross      │
│     - 或前台运行模式                      │
├─────────────────────────────────────────┤
│  7. 清理临时文件                          │
│     - 删除 /tmp 解压内容                  │
├─────────────────────────────────────────┤
│  8. 输出完成信息                          │
│     - 访问地址                            │
│     - 管理命令                            │
│     - 日志路径                            │
└─────────────────────────────────────────┘
```

## Important Constraints

- **Python 3.8+** required
- **Docker 20.10+** required on host
- **No external database** - must use SQLite
- **Single machine deployment only**
- **Concurrent builds limited to 3**
- **Build timeout**: 2 hours per task
- **Log retention**: 30 days
- **Artifact retention**: 30 days

## Quick Start (MVP 目标)

### 方式一：自解压安装脚本（推荐）

```bash
# 1. 下载安装脚本
wget https://github.com/user/easydockcross/releases/download/v1.0.0/easydockcross-1.0.0-linux-x86_64.sh

# 2. 运行安装（自动解压、部署、配置）
chmod +x easydockcross-1.0.0-linux-x86_64.sh
sudo ./easydockcross-1.0.0-linux-x86_64.sh

# 3. 浏览器打开 http://localhost:5000
```

安装脚本自动完成：
- 检测系统环境（Linux 发行版、架构）
- 检查并安装 Docker（如未安装）
- 创建安装目录 `/opt/easydockcross`
- 创建数据目录 `/var/lib/easydockcross`
- 创建系统用户和服务
- 启动服务

### 方式二：源码安装（开发）

```bash
git clone <repo> && cd EasyDockCross
pip install -r requirements.txt
python app.py
```

### 安装脚本功能

`install.sh` 自动处理：
- 检测系统环境（Linux 发行版、架构）
- 检查 Docker 安装（如未安装提示引导）
- 创建安装目录 `/opt/easydockcross`
- 创建数据目录 `/var/lib/easydockcross`
- 创建系统用户 `easydockcross`
- 注册 systemd 服务（可选）
- 创建命令软链接 `/usr/local/bin/easydockcross`

## Security Requirements

- Passwords must use bcrypt hashing
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via template escaping
- Docker containers run as non-root user
- Container resource limits (CPU/memory)

## Language Note（语言规范）

**所有与本工程相关的会话、回复及文档必须使用中文输出。**

This project uses Chinese for documentation and UI text. Maintain Chinese language in:
- User-facing messages and UI
- Documentation comments
- Log messages visible to users
- Error messages
- All Claude Code responses and communications about this project
