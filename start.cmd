@echo off
cd /d "%~dp0"
set "PATH=%~dp0bin;%PATH%"
title VolleyTrak

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo O servidor do VolleyTrak ja esta rodando.
    echo Abra: http://127.0.0.1:8000
    pause
    exit /b 0
)

echo ============================================
echo  VolleyTrak
echo  Abra: http://127.0.0.1:8000
echo  Feche esta janela para parar o servidor.
echo ============================================
echo.

set "PY=%~dp0portable-python\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
