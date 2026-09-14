@echo off
set "SCRIPT_DIR=%~dp0"
set "OUTPUT_DIR=%SCRIPT_DIR%..\data"
set "LOCAL_PYSERIAL=C:\Users\kore\imu_logger\pyserial"

if exist "%LOCAL_PYSERIAL%" (
  set "PYTHONPATH=%LOCAL_PYSERIAL%;%PYTHONPATH%"
)

where python >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=python"
) else (
  set "PYTHON=C:\Users\kore\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

"%PYTHON%" "%SCRIPT_DIR%serial_logger.py" --port COM5 --baud 230400 --seconds 30 --output "%OUTPUT_DIR%"
pause
