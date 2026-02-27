@echo off
chcp 65001 >nul
title zipimg - 图片压缩工具

REM 检查是否直接拖拽文件到 bat 上
if "%~1"=="" goto interactive

REM 有参数说明是拖拽文件启动，直接处理
cd /d "%~dp0"
python "%~dp0imgzip.py" %*
goto end

:interactive
REM 交互模式
cd /d "%~dp0"
python "%~dp0imgzip.py"

:end
