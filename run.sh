#!/bin/bash

echo "========================================"
echo "  微分方程拟合工具 - 启动脚本"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/3] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.9+"
    exit 1
fi
python3 --version

echo ""
echo "[2/3] 安装依赖..."
pip3 install -r requirements.txt

echo ""
echo "[3/3] 启动服务..."
echo ""
echo "服务启动后，请在浏览器中访问: http://localhost:8000"
echo "按 Ctrl+C 停止服务"
echo ""

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
