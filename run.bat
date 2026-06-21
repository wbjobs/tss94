@echo off
chcp 65001 > nul
echo ========================================
echo   微分方程拟合工具 - 启动脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查Python环境...
python --version
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.9+
    pause
    exit /b 1
)

echo.
echo [2/3] 安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo 警告: 依赖安装可能有问题，继续尝试启动...
)

echo.
echo [3/3] 启动服务...
echo.
echo 服务启动后，请在浏览器中访问: http://localhost:8000
echo 按 Ctrl+C 停止服务
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

pause
