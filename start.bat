@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo BTS Express ishga tushmoqda...
start "" http://localhost:8000
where python >nul 2>nul && (python server.py) || (py server.py)
pause
