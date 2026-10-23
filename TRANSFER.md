# Transferir o VolleyTrak para outro PC

O pacote gerado por `scripts\make-transfer.cmd` contém código, banco, clipes,
modelos, ffmpeg e o proxy do segundo set. Ele **não copia o .venv** e não copia
os vídeos originais que estão fora da pasta do projeto.

## Requisitos no PC novo

- Windows 10/11 64-bit
- Python 3.11 64-bit
- Driver NVIDIA atualizado (não é necessário instalar CUDA Toolkit; o PyTorch já traz o runtime)
- Internet para instalar as dependências Python na primeira vez
- Espaço em disco: cerca de 8–12 GB, dependendo dos vídeos originais

## Passo a passo

1. Copie a pasta `VolleyTrak-Transfer-...` para o PC novo.
2. Renomeie/mova para **exatamente** `D:\volleytrak`.
   - Os caminhos de clipes e jobs ficam gravados no banco. Se usar outro caminho,
     rode `scripts\relocate.py` depois de instalar o Python.
3. Instale o Python 3.11 marcando “Add Python to PATH”.
4. Abra o PowerShell em `D:\volleytrak` e rode:

   ```powershell
   .\scripts\setup.ps1 -Cv
   ```

   Isso cria o `.venv` e instala PyTorch CUDA, Ultralytics, Transformers,
   ONNX Runtime e as demais dependências.
5. Confira a GPU:

   ```powershell
   nvidia-smi
   ```

6. Abra `Abrir VolleyTrak.cmd` ou `start.cmd`.
7. Crie o atalho na Área de Trabalho:
   - destino: `D:\volleytrak\Abrir VolleyTrak.cmd`
   - pasta de trabalho: `D:\volleytrak`

## Vídeos originais

O pacote inclui `data\videos\segundo-set-proxy.mp4`, usado pela partida 3.
Os vídeos originais da pasta `D:\Videos Volei` não são copiados. Os clipes e
vídeos anotados já existentes funcionam sem eles; para tocar o vídeo original
ou reprocessar, copie os arquivos para o mesmo caminho no PC novo:

- `D:\Videos Volei\Set 1.mp4`
- `D:\Videos Volei\Primeiro Set Jogo de Vôlei Bonfim X Country Club Valinhos Sub-13 (Liga Regional de Vôlei).mp4`
- `D:\Videos Volei\Segundo Set Jogo de Vôlei Bonfim X Country Club Valinhos Sub-13 (Liga Regional de Vôlei.mp4`

Se os caminhos forem diferentes, ajuste o banco:

```powershell
.\.venv\Scripts\python.exe scripts\relocate.py `
  --old-root "D:\volleytrak" --new-root "E:\volleytrak" `
  --old-videos "D:\Videos Volei" --new-videos "E:\Videos Volei"
```

## O que está incluído

- `app.db` (partidas, clipes, notas, feedback, estrelas)
- `data/jobs/match-*` (clipes, miniaturas, JSON, detecções, anotados)
- `data/models` (YOLO, D-FINE e VballNet)
- `data/videos/segundo-set-proxy.mp4`
- `bin/ffmpeg.exe` e `bin/ffprobe.exe`
- código, scripts, launcher e README

## Backup e segurança

- `scripts\backup-data.cmd` cria um backup de banco + clipes + metadados.
- Copie o backup para pendrive, HD externo ou nuvem.
- O launcher é visível; não há script oculto nem inicialização automática.
- Para início automático no login, crie um atalho **visível** na pasta Iniciar
  apontando para `Abrir VolleyTrak.cmd`; isso pode ser questionado pelo antivírus.

## Versão realmente portable

Esta transferência é “semi-portable”: o código e os dados vão juntos, mas o
Python/dependências são instalados no PC novo. Uma versão 100% portable exigiria
embarcar Python + PyTorch/CUDA + modelos + ffmpeg, o que fica muito grande e
dependente do driver/GPU. Para revisão fora de casa, é mais prático gerar um
pacote só com clipes, banco e um visualizador estático.
