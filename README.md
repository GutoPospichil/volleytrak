# VolleyTrak

Ferramenta local para gerar clipes de rally de vídeos de vôlei, com revisão humana e aprendizado por feedback.

O foco atual é a **geração automática de clipes**. O vídeo anotado, estatísticas e outras funções no estilo Balltime ficam para o futuro.

## Download

A versão de teste fica em **GitHub Releases**:

- **Instalador único**: baixe `VolleyTrakSetup.exe` e execute.
- **Portátil único**: baixe `VolleyTrakPortable.7z`, extraia com o [7-Zip](https://www.7-zip.org/) e abra `Abrir VolleyTrak (desktop).cmd`.

O instalador e o portátil já incluem Python, modelos e ffmpeg. Não precisa instalar Python nem driver NVIDIA.

Requisitos:

- Windows 10/11 64-bit
- Cerca de 1 GB livres
- O instalador é **não assinado**: o Windows pode mostrar o aviso do SmartScreen. Clique em **Mais informações → Executar assim mesmo**.

## Como usar

1. Abra o VolleyTrak pelo atalho do instalador ou pelo `Abrir VolleyTrak (desktop).cmd` do portátil.
2. Adicione uma partida por upload, arrastando o vídeo para a tela inicial, ou por caminho local.
3. Calibre os quatro cantos da quadra.
4. Clique em **Processar clipes**: roda VballNet, áudio, contatos, atividade da quadra e corte.
5. Revise os clipes:
   - **Salvar**: vai para a aba Salvos.
   - **Estrela**: marca um clipe excelente; em clipe novo, salva automaticamente.
   - **Excluir**: pede o motivo (tempo morto, bola no chão, corte errado etc.).
6. Clique no horário `mm:ss` do clipe para abrir o **vídeo original** no início daquele rally.
7. Exporte o highlight com os clipes salvos.

Os dados ficam em `%LOCALAPPDATA%\VolleyTrakData` (instalador) ou em `data\` (portátil). Clipes, banco e feedback não vão para o GitHub.

## Reprocessar sem apito

Se o apito do jogo estiver difícil de detectar e os clipes ficarem com tempo morto:

1. abra a partida;
2. clique em **Reprocessar sem apito**;
3. confirme.

O VolleyTrak ignora o áudio e refaz os clipes usando bola, contatos e atividade visual. Se as detecções de bola/contatos já existirem, elas são reaproveitadas, então o reprocessamento é bem mais rápido.

- Os clipes **salvos são preservados**.
- Os clipes **não verificados são refeitos**.
- As exclusões anteriores continuam valendo.
- Quando a partida está em modo sem apito, aparece o botão **Reprocessar com apito** para voltar ao modo original.

## Clipes salvos

A aba **Clipes salvos** mostra todos os clipes salvos de todas as partidas, agrupados por partida.

- **Assistir** reproduz o clipe dentro do app;
- **Abrir pasta** abre a pasta dos clipes daquela partida no Explorer;
- **Baixar clipe** salva uma cópia do clipe;
- **Remover dos salvos** devolve o clipe para os não verificados da partida;
- a busca filtra por partida, adversário ou data.

## Excluir o vídeo original e manter os clipes

Na aba **Clipes salvos**, cada partida tem o botão **Excluir vídeo original**. O mesmo botão aparece na página da partida como **Excluir vídeo**.

- o arquivo do vídeo original é apagado do disco;
- os clipes salvos, miniaturas, highlight e feedback continuam;
- os clipes não verificados também continuam e podem ser revisados ou salvos;
- a partida fica marcada como **Vídeo removido**;
- sem o vídeo, não é possível reprocessar nem editar cortes daquela partida.

Se o vídeo for um arquivo local fora da pasta do VolleyTrak, o app avisa e pede uma confirmação extra antes de apagar o original.

## Onde salvar os clipes

Abra **Configurações** no topo do app:

- escolha a pasta base com **Escolher pasta** (seletor nativo no app desktop) ou digite o caminho completo;
- clique em **Salvar configuração**;
- novos clipes vão para `<pasta escolhida>\match-<id>`;
- clipes já existentes não são movidos;
- ao editar um clipe antigo, o arquivo novo fica na pasta do original;
- **Abrir pasta** abre o Explorer na pasta configurada;
- a página da partida também tem **Abrir pasta** e **Configurar pasta**.

Sem configuração, o app continua usando a pasta interna de dados do VolleyTrak.

## O que o feedback faz

- Guarda motivo/observação/estrela e features do clipe.
- Ajusta o perfil de corte (pré/pós-roll, velocidade ativa e bola mínima).
- Treina um ranker simples de clipes; ele é aplicado com peso moderado para não eliminar candidatos bons.
- Clipes excluídos não são recriados; clipes salvos são preservados.
- Duplicatas não ensinam conteúdo ruim ao ranker.

O ranker atual é inicial e melhora com mais avaliações. Use os motivos com sinceridade; eles são mais úteis que uma nota isolada.

## Desenvolvimento

Requisitos: Python 3.11 e ffmpeg.

```powershell
cd D:\volleytrak
.\scripts\setup.ps1
.\scripts\download-models.cmd
.\scripts\run.ps1
```

Modelos usados:

- VballNet (ONNX, vôlei)
- ffmpeg para cortes e áudio

## Limitações conhecidas

- Os clipes são **candidatos**; ainda pode haver tempo morto, warm-up ou pessoa passando na frente.
- VballNet pode perder bolas rápidas ou seguir bola parada.
- A calibração influencia a velocidade e a travessia da rede.
- Contatos ainda são heurísticos.
- O modo sem apito prioriza recall: podem aparecer mais candidatos para revisão.

## Privacidade

- O app roda localmente.
- Nenhum vídeo é enviado para servidor.
- O feedback fica no banco local.
- Pessoas menores de idade: cuidado ao compartilhar clipes; use consentimento dos responsáveis.
