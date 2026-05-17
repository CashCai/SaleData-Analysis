@echo off
chcp 65001 >nul
title 家电销售数据可视化看板

echo ===================================
echo   家电销售数据可视化看板
echo ===================================
echo.

set "BASE_DIR=%~dp0"
set "PYTHON_DIR=%BASE_DIR%portable\python"

:: 检查便携版 Python 是否存在
if not exist "%PYTHON_DIR%\python.exe" (
    echo [错误] 便携版 Python 不存在或已损坏
    echo 请确保 portable\python\ 目录完整
    pause
    exit /b 1
)

:: 确保 data 目录存在
if not exist "%BASE_DIR%data" mkdir "%BASE_DIR%data"

:: 启动应用
echo [启动] 正在启动看板...
start http://localhost:8501
"%PYTHON_DIR%\python.exe" -m streamlit run "%BASE_DIR%main.py"

pause
