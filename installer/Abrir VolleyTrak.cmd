@echo off
setlocal
cd /d "%~dp0"

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 goto open

start "VolleyTrak" cmd /c ""%~dp0start-portable.cmd""
echo Aguardando o servidor iniciar...
for /l %%I in (1,1,30) do (
    curl.exe -s -o NUL --max-time 1 http://127.0.0.1:8000/
    if not errorlevel 1 goto open
    timeout /t 1 /nobreak >nul
)

echo Nao foi possivel iniciar o VolleyTrak.
echo Execute start-portable.cmd e veja a mensagem de erro.
pause
exit /b 1

:open
start "" "http://127.0.0.1:8000"
exit /b 0
