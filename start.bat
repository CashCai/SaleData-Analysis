@echo off
chcp 65001 >nul
title 家电销售数据可视化看板

echo ===================================
echo   家电销售数据可视化看板
echo ===================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 创建虚拟环境（首次运行）
if not exist "venv\" (
    echo [首次运行] 正在创建虚拟环境...
    python -m venv venv
    echo [进度] 正在安装依赖包...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: 启动应用
echo [启动] 正在启动看板...
start http://localhost:8501
python -m streamlit run main.py

pause
