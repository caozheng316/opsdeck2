@echo off
chcp 65001 >nul
title imgtool - 一键安装包

echo.
echo ========================================
echo   imgtool - 一键安装包
echo ========================================
echo.
echo 本工具将自动完成以下操作：
echo   1. 检查 Python 环境
echo   2. 安装 Pillow 库
echo   3. 安装右键菜单
echo.
echo ========================================
echo.

REM 检查 Python
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境
    echo.
    echo 请先安装 Python 3.6+ 并添加到 PATH
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/3] Python 环境检测通过
python --version
echo.

REM 安装 Pillow
echo [2/3] 正在安装 Pillow 库...
pip install Pillow -q
if errorlevel 1 (
    echo [警告] Pillow 安装失败，可能需要管理员权限
    echo 请手动运行：pip install Pillow
    echo.
) else (
    echo [2/3] Pillow 安装完成
)
echo.

REM 安装右键菜单
echo [3/3] 正在安装右键菜单...
call "%~dp0install_context_menu.bat"

echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 现在你可以：
echo.
echo   [压缩功能]
echo     - 右键单个图片 → "用 imgzip 压缩"
echo     - 右键文件夹 → "用 imgzip 压缩此文件夹图片"
echo.
echo   [拼接功能]
echo     - 文件夹空白处右键 → "用 imgjion 拼接图片"
echo.
echo ========================================
echo.
pause
