@echo off
setlocal

cd /d "%~dp0\.."

set "VENV_DIR=.venv"
set "DATA_DIR=data"
set "FLASK_ENV=development"
set "PYTHONPATH=%CD%"

echo ========================================
echo EasyDockCross 开发环境启动脚本 (Windows)
echo ========================================

REM 检查 uv
uv --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 uv。请安装 uv:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    exit /b 1
)

if not exist "%VENV_DIR%" (
    echo 创建 Python 虚拟环境 (uv)...
    uv venv "%VENV_DIR%"
)

echo 安装依赖 (uv)...
uv pip install -q -r requirements.txt --python "%VENV_DIR%\Scripts\python.exe"

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\cache" mkdir "%DATA_DIR%\cache"
if not exist "%DATA_DIR%\artifacts" mkdir "%DATA_DIR%\artifacts"
if not exist "%DATA_DIR%\uploads" mkdir "%DATA_DIR%\uploads"
if not exist "%DATA_DIR%\logs" mkdir "%DATA_DIR%\logs"

echo 启动 Flask 开发服务器...
echo 数据目录: %DATA_DIR%
echo 访问地址: http://127.0.0.1:5000
echo ========================================

"%VENV_DIR%\Scripts\python.exe" app.py
