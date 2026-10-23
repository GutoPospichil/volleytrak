@echo off
cd /d "%~dp0"
set "PATH=%~dp0bin;%PATH%"
if not defined VOLLEYTRAK_DATA set "VOLLEYTRAK_DATA=%LOCALAPPDATA%\VolleyTrakData"
title VolleyTrak
echo ============================================
echo  VolleyTrak
echo  Abra: http://127.0.0.1:8000
echo  Feche esta janela para parar o servidor.
echo ============================================
echo.
"%~dp0portable-python\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
