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

if not exist "%VENV_DIR%" (
    echo 创建 Python 虚拟环境...
    python -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

echo 安装依赖...
pip install -q --upgrade pip
pip install -q -r requirements.txt

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\cache" mkdir "%DATA_DIR%\cache"
if not exist "%DATA_DIR%\artifacts" mkdir "%DATA_DIR%\artifacts"
if not exist "%DATA_DIR%\uploads" mkdir "%DATA_DIR%\uploads"
if not exist "%DATA_DIR%\logs" mkdir "%DATA_DIR%\logs"

echo 启动 Flask 开发服务器...
echo 数据目录: %DATA_DIR%
echo 访问地址: http://127.0.0.1:5000
echo ========================================

python app.py
