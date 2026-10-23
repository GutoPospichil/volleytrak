# VolleyTrak

Ferramenta local para gerar clipes de rally de vídeos de vôlei, com revisão humana e aprendizado por feedback.

O foco atual é a **geração automática de clipes**. O vídeo anotado, estatísticas e outras funções no estilo Balltime ficam para o futuro.

## Download

A versão de teste fica em **GitHub Releases**:

- **Portable**: baixe todas as partes `VolleyTrakPortable.7z.001`, `.002`, ... para a mesma pasta, abra a `.001` no [7-Zip](https://www.7-zip.org/) e extraia.
- **Instalador**: baixe todas as partes `VolleyTrakSetup.7z.001`, `.002`, ... e extraia; depois execute `VolleyTrakSetup.exe`.
- Se houver partes, **não renomeie** e mantenha todas juntas.

O pacote portable não precisa instalar Python. O instalador também não; os dois incluem Python, PyTorch/CUDA, modelos e ffmpeg.

Requisitos:

- Windows 10/11 64-bit
- Driver NVIDIA atualizado (sem ele o processamento roda em CPU e fica muito lento)
- Cerca de 8 GB livres
- 7-Zip para extrair os arquivos divididos

## Como usar

1. Abra `Abrir VolleyTrak.cmd` (portable) ou o atalho criado pelo instalador.
2. Adicione uma partida por upload ou por caminho local.
3. Calibre os quatro cantos da quadra.
4. Clique em **Processar clipes**: roda VballNet, áudio, contatos, rallies e corte.
5. Revise os clipes:
   - **Salvar**: vai para a aba Salvos.
   - **Estrela**: marca um clipe excelente; em clipe novo, salva automaticamente.
   - **Excluir**: pede o motivo (tempo morto, bola no chão, corte errado etc.).
6. Clique no horário `mm:ss` do clipe para abrir o **vídeo original** no início daquele rally.
7. Exporte o highlight com os clipes salvos.

Os dados ficam em `%LOCALAPPDATA%\VolleyTrakData` (instalador) ou em `data\` (portable). Clipes, banco e feedback não vão para o GitHub.

## O que o feedback faz

- Guarda motivo/observação/estrela e features do clipe.
- Ajusta o perfil de corte (pré/pós-roll, velocidade ativa e bola mínima).
- Treina um ranker simples de clipes; ele é aplicado com peso moderado para não eliminar candidatos bons.
- Clipes excluídos não são recriados; clipes salvos são preservados.

O ranker atual é inicial e melhora com mais avaliações. Use os motivos com sinceridade; eles são mais úteis que uma nota isolada.

## Desenvolvimento

Requisitos: Python 3.11, ffmpeg e driver NVIDIA.

```powershell
cd D:\volleytrak
.\scripts\setup.ps1 -Cv
.\scripts\download-models.cmd
.\scripts\run.ps1
```

Modelos usados:

- YOLOv8n (pessoas)
- D-FINE volleyball person/ball (Apache-2.0, Hugging Face)
- VballNet (ONNX, vôlei)
- ffmpeg para cortes e áudio

## Limitações conhecidas

- Os clipes são **candidatos**; ainda pode haver tempo morto, warm-up ou pessoa passando na frente.
- VballNet pode perder bolas rápidas ou seguir bola parada.
- A calibração influencia a velocidade e a travessia da rede.
- Contatos ainda são heurísticos.
- Sem fine-tune da bola por frame e sem OCR de jogadores nesta versão.

## Privacidade

- O app roda localmente.
- Nenhum vídeo é enviado para servidor.
- O feedback fica no banco local.
- Pessoas menores de idade: cuidado ao compartilhar clipes; use consentimento dos responsáveis.

## Créditos

Projeto pessoal em desenvolvimento. Dependências e modelos mantêm suas licenças originais; verifique antes de redistribuir comercialmente.


## Mapa de clipes e rally pela metade

- O mapa mostra a cobertura dos clipes na timeline; blocos vazios são minutos sem clipes.
- Clique em um bloco ou em um vão para abrir o vídeo original naquele ponto.
- Ao excluir um clipe que começa no meio ou termina antes do ponto, escolha **Rally pela metade**.
- Esse motivo, depois de alguns exemplos, aumenta o pré/pós-roll para tentar pegar o rally completo.
