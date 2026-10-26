# VolleyTrak 0.3.17 beta

## Reprocessar sem apito

- Novo botão **Reprocessar sem apito** na própria página da partida.
- Ignora o áudio/apito e refaz os clipes usando bola, contatos e atividade visual.
- Reaproveita as detecções de bola, contatos e atividade já existentes: o reprocessamento fica bem mais rápido.
- Os clipes salvos são preservados e os não verificados são refeitos.
- As exclusões anteriores continuam valendo.
- No modo sem apito, os candidatos usam janelas de ~8s em volta dos contatos e um limite de bola mais tolerante, para não perder rallies quando a detecção da bola está fraca.
- Quando a partida está em modo sem apito, aparece **Reprocessar com apito** para voltar ao modo original.

Exemplo: a partida APAV Inclusão foi reprocessada sem apito e passou de 3 clipes salvos para 25 clipes (3 salvos + 22 novos candidatos).

## Janelas de CMD escondidas

- Processamento, cortes, thumbnails, áudio, highlight e cálculo de notas não abrem mais janelas de CMD.
- O app desktop continua usando `pythonw`, e todos os processos filhos (incluindo ffmpeg) rodam com console oculto.

## Base da 0.3.16

- Pasta dos clipes configurável e botão **Abrir pasta**.
- Botão global **Som/Mudo** com atalho **M**.
- Velocidade 0.5x–2x, setas de 5s e Shift+setas para navegar entre clipes.
- Instalador único e portátil único.

Baixe `VolleyTrakSetup.exe` e execute. O instalador é não assinado; o aviso do SmartScreen é esperado.
