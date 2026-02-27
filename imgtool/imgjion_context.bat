@echo off
chcp 65001 >nul
title imgjion - 图片拼接工具

set "SCRIPT_DIR=%~dp0"

REM 检测是否有参数（拖拽文件）
if "%~1"=="" (
    REM 无参数：文件夹模式，扫描当前目录
    echo.
    echo ======================================
    echo   imgjion - 图片拼接工具（文件夹扫描模式）
    echo ======================================
    echo.
    echo 正在扫描当前文件夹：%CD%
    echo.
    python "%SCRIPT_DIR%imgjion.py" --folder "%CD%" -i
    echo.
    echo ======================================
    echo  处理完成！
    echo ======================================
    echo.
    pause
    exit /b
)

REM 有参数：文件模式（拖拽文件）
echo.
echo ======================================
echo   imgjion - 图片拼接工具
echo ======================================
echo.
echo 使用说明:
echo   1. 拖拽图片文件到本窗口
echo   2. 或者粘贴图片路径（多个用空格分隔）
echo   3. 按回车键开始拼接
echo   4. 输入 q 退出
echo.
echo ======================================
echo.

:loop
set "files="
set /p "files=请输入或拖拽图片路径："

if "%files%"=="" goto loop
if /i "%files%"=="q" goto end
if /i "%files%"=="quit" goto end

echo.
echo [正在处理...]
echo.

REM 调用 Python 脚本进行拼接（使用当前文件夹作为输出目录）
python "%SCRIPT_DIR%imgjion.py" %files% -o "%CD%"

echo.
echo ======================================
echo  [完成！] 输出文件已保存到当前文件夹
echo ======================================
echo.
goto loop

:end
echo.
echo 再见！
echo.
pause
