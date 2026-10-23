@echo off
setlocal
set "ROOT=%~dp0.."
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "TS=%%I"
set "DEST=%ROOT%\backups\%TS%"
mkdir "%DEST%" 2>nul

echo Copiando banco e metadados...
copy /Y "%ROOT%\data\app.db*" "%DEST%\" >nul
if exist "%ROOT%\data\feedback_profile.json" copy /Y "%ROOT%\data\feedback_profile.json" "%DEST%\" >nul

for /d %%D in ("%ROOT%\data\jobs\match-*") do (
    if not exist "%DEST%\jobs\%%~nxD\clips" mkdir "%DEST%\jobs\%%~nxD\clips" 2>nul
    copy /Y "%%D\*.json" "%DEST%\jobs\%%~nxD\" >nul
    if exist "%%D\clips" robocopy "%%D\clips" "%DEST%\jobs\%%~nxD\clips" *.mp4 *.jpg /NFL /NDL /NJH /NJS >nul
)

echo Backup criado em:
echo %DEST%
echo.
echo Copie essa pasta para um pendrive, HD externo ou nuvem.
pause
