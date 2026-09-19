@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\kore\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

"%PYTHON%" "%~dp0build_motion_report.py" --latest "%~dp0..\data" --open

echo.
echo Motion report finished. Press any key to close.
pause >nul
