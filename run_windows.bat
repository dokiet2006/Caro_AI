@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python main.py gui
) else (
    py -3 main.py gui
)
if errorlevel 1 pause
