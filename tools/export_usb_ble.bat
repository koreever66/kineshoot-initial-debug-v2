@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\kore\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "PYTHONPATH=C:\Users\kore\imu_logger\pyserial;%PYTHONPATH%"
set "OUTPUT=%~dp0data"
set "PORT=%~1"
if "%PORT%"=="" set "PORT=COM6"

"%PYTHON%" "%~dp0flash_export.py" ^
  --port %PORT% ^
  --baud 230400 ^
  --output "%OUTPUT%" ^
  --delete-after-download ^
  --session-dir ^
  --hardware-revision H2 ^
  --mount-position bench_handheld ^
  --power-source usb_computer ^
  --trigger-source ble_command

echo.
echo USB-powered BLE/App capture export finished. Press any key to close.
pause >nul

