# CONSENSUS_需求分析.md

## 1. 需求概述

### 1.1 项目名称
EasyDockCross - 简单的交叉构建系统

### 1.2 项目目标
构建一个基于Docker的简单交叉构建Web系统，支持多种编程语言在多操作系统平台上的交叉编译，提供Web界面进行构建任务管理和监控。

### 1.3 核心价值
- 简化跨平台项目构建流程
- 通过Docker容器隔离构建环境
- 提供友好的Web界面管理构建任务
- 支持主流编程语言的交叉编译

## 2. 明确的需求描述

### 2.1 功能需求

#### 核心功能（Must Have）

**F1: 用户认证**
- 支持简单的用户名密码认证
- 用户登录后才能访问系统功能
- 会话管理

**F2: 项目管理**
- 创建、编辑、删除项目
- 项目配置支持Web界面和配置文件两种方式
- 配置文件格式：YAML
- 项目配置包括：项目名称、源代码仓库、构建命令、目标平台等

**F3: 构建任务管理**
- 提交构建任务
- 查看构建任务列表
- 查看构建任务详情
- 取消构建任务

**F4: 构建执行**
- 基于Docker容器执行构建
- 支持主流编程语言：Go、Python、Java、Node.js、C++
- 支持C++项目构建工具：cmake、xmake、make
- 支持多操作系统目标平台：Linux、Windows、macOS
- 实时显示构建进度
- 捕获和显示构建错误信息

**F5: 构建结果管理**
- 查看构建结果（成功/失败）
- 下载构建产物
- 查看构建日志

**F6: Web界面**
- 登录页面
- 项目列表页面
- 项目详情/配置页面
- 构建任务列表页面
- 构建任务详情页面（包含进度和日志）

**F7: 自定义镜像管理（新增）**
- 支持基于dockcross镜像创建自定义构建镜像
- 支持添加自定义依赖到镜像中
- 支持打包新的镜像
- 项目配置可以指定使用的镜像
- 支持挂载运行构建
- 镜像管理界面（创建、查看、删除镜像）

**F8: 依赖检查和自动安装（新增）**
- 第一次启动时检查系统依赖
- 支持自动安装Docker等系统依赖
- 无法自动安装的依赖提供提示引导
- 显示依赖安装进度和结果
- 依赖检查界面

#### 次要功能（Should Have）

**F9: 构建历史**
- 查看项目的构建历史记录
- 按时间、状态筛选构建记录

**F10: 配置导入导出**
- 导出项目配置为YAML文件
- 从YAML文件导入项目配置

### 2.2 非功能需求

#### 性能需求
- Web界面响应时间 < 2秒
- 支持并发构建任务数：至少3个
- 构建日志实时更新延迟 < 1秒

#### 安全需求
- 用户密码加密存储（使用bcrypt或类似算法）
- 防止SQL注入
- 防止XSS攻击
- Docker容器隔离，确保构建环境安全

#### 可用性需求
- 系统可用性 > 95%
- 提供基本的错误提示信息
- 构建失败时显示明确的错误原因

#### 兼容性需求
- 支持主流浏览器：Chrome、Firefox、Edge、Safari
- 支持Docker版本：Docker 20.10+
- 支持Python版本：Python 3.8+

#### 可维护性需求
- 代码结构清晰，模块化设计
- 提供基本的日志记录
- 提供简单的部署文档

## 3. 技术实现方案

### 3.1 技术栈

#### 后端技术栈
- **Web框架**: Flask（轻量级，适合快速开发）
- **Python版本**: Python 3.8+
- **Docker SDK**: docker-py（Python Docker SDK）
- **数据存储**: SQLite（轻量级，无需额外数据库）
- **认证**: Flask-Login + bcrypt
- **配置管理**: PyYAML
- **前端模板**: Jinja2
- **静态资源**: Bootstrap 5（UI框架）+ jQuery

#### 构建环境
- **容器运行时**: Docker
- **基础镜像**: 根据不同语言使用官方镜像
  - Go: golang:latest
  - Python: python:3.x
  - Java: openjdk:latest
  - Node.js: node:latest

### 3.2 系统架构

#### 整体架构
```
┌─────────────────────────────────────────────────┐
│                   用户浏览器                      │
└────────────────────┬────────────────────────────┘
                     │ HTTP/HTTPS
┌────────────────────▼────────────────────────────┐
│              Flask Web应用                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ 认证模块 │  │ 项目管理 │  │ 构建管理 │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Web界面  │  │ API接口  │  │ 日志系统 │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────┬────────────────────────────┘
                     │ Docker API
┌────────────────────▼────────────────────────────┐
│              Docker引擎                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Go容器   │  │ Python容器│  │ Java容器│      │
│  └──────────┘  └──────────┘  └──────────┘      │
│  ┌──────────┐  ┌──────────┐                     │
│  │ Node容器 │  │ ...      │                     │
│  └──────────┘  └──────────┘                     │
└─────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              本地文件系统                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ SQLite   │  │ 构建产物 │  │ 项目配置 │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────┘
```

#### 核心组件

**C1: Flask应用主程序**
- 路由管理
- 请求处理
- 响应返回

**C2: 认证模块**
- 用户登录/登出
- 会话管理
- 密码加密/验证

**C3: 项目管理模块**
- 项目CRUD操作
- 项目配置解析（YAML）
- 项目配置验证

**C4: 构建管理模块**
- 构建任务创建
- 构建任务调度
- 构建状态管理
- 构建日志收集

**C5: Docker集成模块**
- Docker容器创建/启动/停止
- 容器日志流式读取
- 容器资源管理

**C6: 数据访问层**
- SQLite数据库操作
- 数据模型定义

**C7: Web界面**
- HTML模板
- 静态资源
- AJAX交互

### 3.3 数据模型

#### 用户表（users）
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 项目表（projects）
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    repository_url VARCHAR(500),
    language VARCHAR(20) NOT NULL,
    build_command TEXT NOT NULL,
    target_platform VARCHAR(20) NOT NULL,
    config_yaml TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 构建任务表（build_tasks）
```sql
CREATE TABLE build_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    container_id VARCHAR(100),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    output_log TEXT,
    error_log TEXT,
    artifacts_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

#### 镜像表（images）（新增）
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    base_image VARCHAR(200) NOT NULL,
    description TEXT,
    dependencies TEXT,
    dockerfile TEXT,
    image_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 依赖检查表（dependency_checks）（新增）
```sql
CREATE TABLE dependency_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dependency_name VARCHAR(50) NOT NULL,
    dependency_type VARCHAR(20) NOT NULL,
    is_installed BOOLEAN DEFAULT FALSE,
    version VARCHAR(50),
    check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_install_supported BOOLEAN DEFAULT FALSE,
    install_command TEXT
);
```

### 3.4 接口规范

#### 认证接口
- `POST /login` - 用户登录
- `POST /logout` - 用户登出
- `GET /` - 首页（重定向到登录或项目列表）

#### 项目接口
- `GET /projects` - 项目列表
- `GET /projects/<id>` - 项目详情
- `GET /projects/new` - 创建项目页面
- `POST /projects` - 创建项目
- `GET /projects/<id>/edit` - 编辑项目页面
- `POST /projects/<id>` - 更新项目
- `POST /projects/<id>/delete` - 删除项目
- `POST /projects/<id>/import` - 导入配置
- `GET /projects/<id>/export` - 导出配置

#### 构建接口
- `GET /projects/<project_id>/builds` - 构建任务列表
- `GET /builds/<id>` - 构建任务详情
- `POST /projects/<project_id>/build` - 创建构建任务
- `POST /builds/<id>/cancel` - 取消构建任务
- `GET /builds/<id>/log` - 获取构建日志（流式）
- `GET /builds/<id>/download` - 下载构建产物

#### WebSocket接口
- `WS /builds/<id>/log` - 实时构建日志推送

## 4. 技术约束

### 4.1 部署约束
- 单机部署，单体应用
- 不依赖外部数据库（使用SQLite）
- 不依赖外部缓存（如Redis）
- 不依赖消息队列
- 提供Docker打包脚本

### 4.2 技术约束
- 使用Python 3.8+
- 使用Flask框架
- 使用SQLite作为数据存储
- 使用Docker作为构建环境
- 前端使用Bootstrap 5

### 4.3 资源约束
- 单机部署，资源有限
- 需要合理控制Docker容器资源使用
- 需要清理过期的构建产物和日志

## 5. 集成方案

### 5.1 Docker集成
- 使用docker-py SDK与Docker引擎通信
- 为每个构建任务创建独立的容器
- 容器使用卷挂载共享构建产物
- 容器执行完成后自动清理
- 支持基于dockcross镜像创建自定义镜像
- 支持添加自定义依赖到镜像中
- 支持打包新的镜像
- 项目配置可以指定使用的镜像
- 支持挂载运行构建

### 5.2 依赖检查和自动安装（新增）
- 第一次启动时检查系统依赖
- 支持自动安装Docker等系统依赖
- 无法自动安装的依赖提供提示引导
- 显示依赖安装进度和结果
- 支持Windows、Linux、macOS平台的依赖检查

### 5.3 Git集成（可选）
- 支持从Git仓库拉取源代码
- 支持指定分支或标签
- 使用subprocess调用git命令

### 5.4 文件存储集成
- 构建产物存储在本地文件系统
- 使用时间戳+任务ID命名构建产物目录
- 提供Web下载接口

## 6. 任务边界限制

### 6.1 功能边界
**包含**:
- 用户认证（简单用户名密码）
- 项目管理（CRUD）
- 构建任务管理
- 构建执行（基于Docker）
- 构建结果查看和下载
- 基础的Web界面
- **C++项目构建支持（cmake、xmake、make）**
- **自定义镜像管理（基于dockcross）**
- **依赖检查和自动安装**

**不包含**:
- 多租户支持
- 复杂的权限管理
- CI/CD流水线集成
- 构建缓存机制
- 分布式构建
- 高级监控和告警
- 第三方认证集成

### 6.2 技术边界
- 仅支持单机部署
- 不支持集群部署
- 不支持负载均衡
- 不支持高可用

### 6.3 性能边界
- 并发构建任务数限制为3个
- 单个构建任务超时时间：2小时
- 构建日志最大保留时间：30天
- 构建产物最大保留时间：30天

## 7. 验收标准

### 7.1 功能验收标准

**F1: 用户认证**
- [ ] 用户可以使用用户名密码登录
- [ ] 登录成功后跳转到项目列表页面
- [ ] 未登录用户访问受保护页面时重定向到登录页
- [ ] 用户可以登出

**F2: 项目管理**
- [ ] 用户可以创建新项目
- [ ] 用户可以查看项目列表
- [ ] 用户可以编辑项目配置
- [ ] 用户可以删除项目
- [ ] 用户可以通过Web界面配置项目
- [ ] 用户可以导入YAML配置文件
- [ ] 用户可以导出项目配置为YAML文件

**F3: 构建任务管理**
- [ ] 用户可以为项目创建构建任务
- [ ] 用户可以查看构建任务列表
- [ ] 用户可以查看构建任务详情
- [ ] 用户可以取消正在运行的构建任务

**F4: 构建执行**
- [ ] 系统可以为Go项目创建构建容器并执行构建
- [ ] 系统可以为Python项目创建构建容器并执行构建
- [ ] 系统可以为Java项目创建构建容器并执行构建
- [ ] 系统可以为Node.js项目创建构建容器并执行构建
- [ ] 系统可以为C++项目创建构建容器并执行构建
- [ ] C++项目支持cmake构建工具
- [ ] C++项目支持xmake构建工具
- [ ] C++项目支持make构建工具
- [ ] 构建过程中可以实时显示构建进度
- [ ] 构建失败时可以显示错误信息

**F5: 构建结果管理**
- [ ] 用户可以查看构建结果（成功/失败）
- [ ] 用户可以下载构建产物
- [ ] 用户可以查看完整的构建日志

**F6: Web界面**
- [ ] 登录页面正常显示和工作
- [ ] 项目列表页面正常显示
- [ ] 项目详情页面正常显示
- [ ] 构建任务列表页面正常显示
- [ ] 构建任务详情页面正常显示，包含进度和日志

**F7: 自定义镜像管理（新增）**
- [ ] 用户可以基于dockcross镜像创建自定义构建镜像
- [ ] 用户可以添加自定义依赖到镜像中
- [ ] 用户可以打包新的镜像
- [ ] 用户可以在项目配置中指定使用的镜像
- [ ] 用户可以查看已创建的镜像列表
- [ ] 用户可以删除自定义镜像
- [ ] 镜像管理界面正常工作

**F8: 依赖检查和自动安装（新增）**
- [ ] 第一次启动时自动检查系统依赖
- [ ] 系统可以自动安装Docker等系统依赖
- [ ] 无法自动安装的依赖提供清晰的提示引导
- [ ] 显示依赖安装进度和结果
- [ ] 依赖检查界面正常工作
- [ ] 支持Windows、Linux、macOS平台的依赖检查

### 7.2 非功能验收标准

**性能验收**
- [ ] Web界面响应时间 < 2秒
- [ ] 可以同时运行至少3个构建任务
- [ ] 构建日志实时更新延迟 < 1秒

**安全验收**
- [ ] 用户密码使用bcrypt加密存储
- [ ] 防止SQL注入攻击
- [ ] 防止XSS攻击
- [ ] Docker容器之间相互隔离

**可用性验收**
- [ ] 系统可以稳定运行24小时以上
- [ ] 提供清晰的错误提示信息
- [ ] 构建失败时显示明确的错误原因

**兼容性验收**
- [ ] 在Chrome浏览器上正常工作
- [ ] 在Firefox浏览器上正常工作
- [ ] 在Edge浏览器上正常工作
- [ ] 在Safari浏览器上正常工作
- [ ] 在Docker 20.10+版本上正常工作
- [ ] 在Python 3.8+版本上正常工作

### 7.3 部署验收标准
- [ ] 可以使用提供的Docker打包脚本将应用打包为Docker镜像
- [ ] Docker镜像可以成功运行
- [ ] 应用在Docker容器中正常工作
- [ ] 提供清晰的部署文档

## 8. 风险和假设

### 8.1 风险
- Docker API的兼容性问题可能影响构建稳定性
- 不同语言的构建环境配置复杂度较高
- SQLite在高并发场景下可能成为性能瓶颈
- 单机部署限制了系统的扩展性

### 8.2 假设
- 用户具有基本的Docker使用知识
- 用户可以提供可用的构建命令
- 目标平台的交叉编译工具链在Docker镜像中可用
- 系统部署环境可以访问Docker Hub（拉取基础镜像）

### 8.3 依赖
- Docker引擎已安装并运行
- Python 3.8+已安装
- 足够的磁盘空间存储构建产物和日志
- 网络连接可以访问Docker Hub

## 9. 项目里程碑

### 9.1 第一阶段：基础框架搭建
- Flask应用初始化
- 数据库模型设计
- 基础路由和页面
- 用户认证功能

### 9.2 第二阶段：核心功能实现
- 项目管理功能
- Docker集成
- 构建任务管理
- 构建执行功能

### 9.3 第三阶段：Web界面完善
- 构建进度实时显示
- 构建日志查看
- 构建产物下载
- 配置导入导出

### 9.4 第四阶段：测试和优化
- 功能测试
- 性能测试
- 安全测试
- 部署文档编写

### 9.5 第五阶段：打包和发布
- Docker镜像打包
- 部署脚本编写
- 用户文档编写
- 项目发布

---

**文档状态**: 已完成
**创建时间**: 2026-03-25
**更新时间**: 2026-03-25
