@echo off
chcp 65001 >nul
title imgjion

set "SCRIPT_DIR=%~dp0"

if "%~1"=="" (
    echo.
    echo [Scanning] %CD%
    echo.
    python "%SCRIPT_DIR%imgjion.py" --folder "%CD%" -i
    echo.
    pause
    exit /b
)

:loop
set /p "files=Path:"
if "%files%"=="" goto loop
if /i "%files%"=="q" exit /b
echo.
python "%SCRIPT_DIR%imgjion.py" %files% -o "%CD%"
echo.
goto loop
