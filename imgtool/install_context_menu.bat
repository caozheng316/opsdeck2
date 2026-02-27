@echo off
chcp 65001 >nul
title imgtool - 右键菜单安装

set "SCRIPT_DIR=%~dp0"

echo.
echo ========================================
echo   imgtool - 右键菜单安装
echo ========================================
echo.
echo 当前路径：%SCRIPT_DIR%
echo.
echo 正在安装右键菜单...
echo.

REM ========== imgzip 压缩功能 ==========
echo [1/2] 安装 imgzip 图片压缩...
reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.jpg\shell\imgzip" /ve /t REG_SZ /d "用 imgzip 压缩" /f >nul
reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.jpg\shell\imgzip\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgzip.bat\" \"%%1\"" /f >nul

reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.jpeg\shell\imgzip" /ve /t REG_SZ /d "用 imgzip 压缩" /f >nul
reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.jpeg\shell\imgzip\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgzip.bat\" \"%%1\"" /f >nul

reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.png\shell\imgzip" /ve /t REG_SZ /d "用 imgzip 压缩" /f >nul
reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.png\shell\imgzip\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgzip.bat\" \"%%1\"" /f >nul

reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.webp\shell\imgzip" /ve /t REG_SZ /d "用 imgzip 压缩" /f >nul
reg add "HKCU\SOFTWARE\Classes\SystemFileAssociations\.webp\shell\imgzip\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgzip.bat\" \"%%1\"" /f >nul

reg add "HKCU\SOFTWARE\Classes\Directory\shell\imgzip" /ve /t REG_SZ /d "用 imgzip 压缩此文件夹图片" /f >nul
reg add "HKCU\SOFTWARE\Classes\Directory\shell\imgzip\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgzip.bat\" \"%%V\" -r" /f >nul

reg add "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgzip" /ve /t REG_SZ /d "用 imgzip 压缩此文件夹图片" /f >nul
reg add "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgzip\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgzip.bat\" \"%%V\" -r" /f >nul

REM ========== imgjion 拼接功能 ==========
echo [2/2] 安装 imgjion 图片拼接...
reg add "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgjion" /ve /t REG_SZ /d "用 imgjion 拼接图片" /f >nul
reg add "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgjion\Icon" /ve /t REG_SZ /d "imageres.dll,-5304" /f >nul
reg add "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgjion\command" /ve /t REG_SZ /d "\"%SCRIPT_DIR%imgjion_drop.bat\"" /f >nul

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
echo   输出文件名规则:
echo     详情_01.jpg + 详情_02.jpg → 详情_拼接.jpg
echo.
echo ========================================
echo.
pause
