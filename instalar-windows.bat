@echo off
rem instalar-windows.bat: doble clic para instalar el editor en Windows.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
echo.
pause
