@echo off
chcp 65001 >nul
title imgtool - 右键菜单卸载

echo.
echo ========================================
echo   imgtool - 右键菜单卸载
echo ========================================
echo.
echo 正在删除右键菜单...
echo.

REM 删除 imgzip 压缩菜单
reg delete "HKCU\SOFTWARE\Classes\SystemFileAssociations\.jpg\shell\imgzip" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Classes\SystemFileAssociations\.jpeg\shell\imgzip" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Classes\SystemFileAssociations\.png\shell\imgzip" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Classes\SystemFileAssociations\.webp\shell\imgzip" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Classes\Directory\shell\imgzip" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgzip" /f >nul 2>&1

REM 删除 imgjion 拼接菜单
reg delete "HKCU\SOFTWARE\Classes\Directory\Background\shell\imgjion" /f >nul 2>&1

echo.
echo ========================================
echo   卸载完成！
echo ========================================
echo.
echo 右键菜单已移除。
echo 如需重新安装，请运行 install_context_menu.bat
echo.
pause
