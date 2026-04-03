# Changelog

All notable changes to EasyDockCross will be documented in this file.

## [0.0.2.0] - 2026-04-03

### Added
- 完整 MVP 功能实现：用户认证、项目管理（含 Wizard）、构建调度（并发/超时/日志）、Docker 构建客户端、自定义镜像管理、C++ 构建工具支持、Web 前端界面
- 打包与发布：多架构（x86_64 / arm64）自解压安装脚本 `packaging/build-installer.sh` 与 GitHub Actions CI/CD 自动发布
- 初始测试框架：pytest + pytest-cov，覆盖认证、项目 CRUD、工具函数等核心路径
- GitHub Actions 自动化测试工作流

### Changed
- 默认使用 `uv` 替代 `venv+pip` 进行 Python 环境管理

### Fixed
- 修复代码审查发现的安全与并发问题：认证 Open Redirect、Git/SVN 参数注入、镜像构建重复提交竞态、N+1 查询、NameError 风险

## [0.0.0.1] - 2026-04-03

### Added
- 添加 CLAUDE.md，定义 MVP 架构和部署方案
- 项目文档结构完善（需求分析、任务分解、架构设计）
