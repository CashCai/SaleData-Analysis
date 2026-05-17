#!/bin/bash
echo "==================================="
echo "  家电销售数据可视化看板"
echo "==================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3，请先安装"
    exit 1
fi

# 创建虚拟环境（首次运行）
if [ ! -d "venv" ]; then
    echo "[首次运行] 正在创建虚拟环境..."
    python3 -m venv venv
    echo "[进度] 正在安装依赖包..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 启动
echo "[启动] 正在启动看板..."
open http://localhost:8501 2>/dev/null || xdg-open http://localhost:8501 2>/dev/null
streamlit run main.py
