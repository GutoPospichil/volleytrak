@echo off
setlocal
set "ROOT=%~dp0.."
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%I"
set "DEST=D:\VolleyTrak-Transfer-%TS%"

echo Criando pacote de transferencia em:
echo %DEST%
echo.
echo O .venv NAO sera copiado; ele deve ser recriado no computador novo.
echo O proxy do segundo set, modelos, banco, jobs e clipes serao copiados.

robocopy "%ROOT%" "%DEST%" /E /XD "%ROOT%\.venv" "%ROOT%\backups" "%ROOT%\transfer" "%ROOT%\__pycache__" "%ROOT%\.git" /XF *.pyc /NFL /NDL /NJH /NJS /NP
if errorlevel 8 (
    echo.
    echo Falha ao copiar os arquivos.
    pause
    exit /b 1
)

echo.
echo Pacote criado em:
echo %DEST%
echo.
echo Leia TRANSFER.md antes de abrir no computador novo.
pause
