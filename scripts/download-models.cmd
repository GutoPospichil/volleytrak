@echo off
set "DIR=%~dp0..\data\models\volleyball-dfine"
if not exist "%DIR%" mkdir "%DIR%"
echo Baixando modelo D-FINE de volei para %DIR%
curl.exe -L --fail -o "%DIR%\config.json" "https://huggingface.co/grdesignbuild/volleyball-person-ball-detector/resolve/main/config.json"
if errorlevel 1 goto error
curl.exe -L --fail -o "%DIR%\preprocessor_config.json" "https://huggingface.co/grdesignbuild/volleyball-person-ball-detector/resolve/main/preprocessor_config.json"
if errorlevel 1 goto error
curl.exe -L --fail -o "%DIR%\model.safetensors" "https://huggingface.co/grdesignbuild/volleyball-person-ball-detector/resolve/main/model.safetensors"
if errorlevel 1 goto error
set "VBDIR=%~dp0..\data\models\vballnet"
if not exist "%VBDIR%" mkdir "%VBDIR%"
echo Baixando VballNet (bola 30 fps) para %VBDIR%
curl.exe -L --fail -o "%VBDIR%\VballNetV1a_seq9_grayscale_gru_best.onnx" "https://huggingface.co/spaces/asigatchov/volleyball-tracking/resolve/main/models/VballNetV1a_seq9_grayscale_gru_best.onnx?download=true"
if errorlevel 1 goto error
echo Modelos baixados.
exit /b 0

:error
echo Falha ao baixar o modelo. Verifique a internet e tente novamente.
exit /b 1
