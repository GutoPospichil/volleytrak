# VolleyTrak 0.3.12 beta

## Instalação muito mais fácil
- Agora o instalador é um **arquivo único** `VolleyTrakSetup.exe` (~341 MB), sem partes `.7z` e sem precisar de 7-Zip.
- O portátil também é um **arquivo único** `VolleyTrakPortable.7z` (~252 MB).
- O runtime foi enxugado: removi PyTorch/Ultralytics/Transformers que não eram usados no fluxo de clipes. O app ficou cerca de 8x menor.
- O instalador cria o atalho **VolleyTrak** com ícone e abre a janela desktop (pywebview/WebView2).
- Windows 10/11 x64, WebView2, ~3 GB livres. Não é necessário Python, 7-Zip nem driver NVIDIA para os clipes.
- O instalador não é assinado; o SmartScreen pode pedir confirmação.

## Arrastar e soltar
- Na tela inicial, arraste um vídeo para **“Arraste um vídeo para cá”**.
- O app importa, cria a partida e abre a página automaticamente.
- Também funciona clicando na área para escolher o arquivo.
- A opção **Com apito / Sem apito** fica ao lado da área de drop.

## Interface com opções clicáveis
- **Com apito / Sem apito** em cartões no envio e no vídeo local.
- **Motivo** e **detalhe do corte** em chips clicáveis.
- **Tempo / Mais incertos / Maior score** em chips.
- **Modo de referência** da calibração em cartões.
- **Equipe** do jogador e **Tipo** do evento em chips.
- Logo VT no topo, favicon, ícones do instalador e manifest PWA.

## Fluxo de clipes
- Processar clipes / Gerar novamente (aprendizados).
- Filtro de quadra vazia/parada por movimento dentro da quadra.
- Edição de corte, duplicados após edição e aprendizado.
- O botão legado **Processar** (pipeline de pessoas) foi removido da interface; o fluxo é focado em clipes.

Baixe `VolleyTrakSetup.exe` e execute. Para portátil, baixe `VolleyTrakPortable.7z` e extraia.