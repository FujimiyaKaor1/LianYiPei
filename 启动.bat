@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   链易配 - 启动
echo ========================================
echo.

if not exist .env (
    echo [提示] 未找到 .env，请先配置 .env 文件
    echo 可复制 .env.example 为 .env 并修改数据库密码
    pause
    exit /b 1
)

echo [1/3] 检查数据库...
python scripts/create_db.py 2>nul
if errorlevel 1 (
    echo 数据库创建失败，请检查 MySQL 是否启动
    pause
    exit /b 1
)

echo.
echo [2/3] 初始化数据（若已有数据会跳过）...
python scripts/seed_all_data.py

echo.
echo [3/3] 启动应用...
echo 访问: http://localhost:5000
echo 管理员: admin / admin123
echo ========================================
python run.py

pause
