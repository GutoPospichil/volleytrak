# VolleyTrak 0.3.14 beta

## Correção: app não abria
- O atalho usa `pythonw.exe`, que não tem saída de console. O app fazia um `print` e encerrava silenciosamente antes de abrir a janela.
- Agora o `desktop.py` redireciona a saída para `data/desktop.log` (ou `%LOCALAPPDATA%\VolleyTrakData\desktop.log`) quando está sem console.
- Se ocorrer um erro na abertura, aparece uma janela de mensagem com o erro em vez de fechar sem explicação.
- A janela desktop e o servidor voltaram a abrir normalmente pelo atalho **VolleyTrak**.

## Base da 0.3.13
- Velocidade 0.5x a 2x no vídeo original, edição e clipe.
- ←/→ volta/avança 5s; Shift+←/→ troca de clipe; Espaço play/pause.
- Instalador único `VolleyTrakSetup.exe` (~341 MB) e portátil único (`~252 MB`).
- Arrastar e soltar, opções clicáveis e filtro de quadra vazia.

Baixe `VolleyTrakSetup.exe` e execute.