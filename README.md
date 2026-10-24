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


## Opções atuais de exclusão

- **Tempo morto / bola no chão**: pausa, bola parada ou ponto encerrado.
- **Fora de rally (aquecimento/treino)**: conteúdo que não é um ponto de partida.
- **Corte errado / rally pela metade**: começo/fim errados, inclusive rally incompleto.
- **Duplicado**: o mesmo rally já está em outro clipe.
- **Outro**: use a observação para explicar.

Tempo morto e bola no chão agora têm o mesmo peso; corte errado e rally pela metade também. O histórico antigo é convertido para essas categorias.


## Jogo com apito x sem apito

No cadastro/upload do vídeo escolha:

- **Jogo com apito**: usa apitos como candidatos principais e complementa com bola/contatos nos trechos sem apito.
- **Jogo sem apito**: não procura apito; monta rallies por contatos e bola. Indicado para treinos, vídeos sem áudio ou quadras com vários jogos/apitos simultâneos.

No modo com apito, o apito não é mais o único gatilho: janelas de contato são adicionadas nos vãos, com deduplicação e limite de duração.

## Submotivo de corte errado

Ao escolher **Corte errado / rally pela metade**, escolha também:

- **Clipe começa depois do saque**
- **Clipe acaba antes do ponto**
- **As duas coisas**

Isso ajusta o pré-roll/pós-roll sem precisar escrever a observação.

## Gerar novamente com aprendizados

Depois de salvar os clipes bons e excluir os ruins, use **Gerar novamente (aprendizados)** na página da partida:

- o perfil aprendido é recalculado (pré-roll, pós-roll, velocidade ativa e bola mínima);
- o ranker é treinado novamente com os clipes salvos e excluídos;
- clipes salvos são preservados;
- trechos excluídos por **Corte errado / rally pela metade** podem voltar como **Recuperado**, com o pré/pós-roll ajustado pelo submotivo;
- os demais motivos (tempo morto, fora de rally, duplicado, outro) continuam bloqueando o trecho.

Não é preciso rodar VballNet de novo: a geração usa as detecções de bola, áudio e contatos já existentes.

## Reavaliar minutos sem clipes

A opção **Reavaliar minutos sem clipes no mapa de calor** (marcada por padrão) procura rallies nos vãos de pelo menos 1 minuto:

- usa contatos e bola dentro dos vãos, com limites um pouco mais flexíveis;
- adiciona no máximo alguns candidatos por vão para não inundar a revisão;
- os candidatos aparecem com o selo **Lacuna**.

Se ainda faltar algum lance, use o corte manual.

## Corte manual

Na página da partida, abaixo do vídeo, há a ferramenta **Corte manual**:

1. clique num bloco do mapa de calor ou num vão para posicionar o vídeo (o trecho de 15s já vem marcado);
2. ajuste com **Marcar início** e **Marcar fim** enquanto assiste;
3. use **Pré-visualizar** para conferir;
4. clique em **Criar clipe manual**.

O clipe manual é salvo direto na aba **Salvos**, com o selo **Manual**, e entra no highlight. Ele não é apagado na próxima geração. Para refazer, exclua o clipe manual normalmente.

> Observação: o corte manual usa o ffmpeg local; o vídeo original não é alterado.

## Banco de aprendizado e revisão rápida

O app já guardava os feedbacks no SQLite. Agora existe uma tabela dedicada, `learning_examples`, e a página **Aprendizado** em `/aprendizado`.

Cada clipe salvo ou excluído vira uma linha com:

- label **bom/ruim**;
- motivo, submotivo e observação;
- features de bola, contatos, áudio, duração e score;
- peso do exemplo;
- partida, trecho e data.

Pesos atuais: estrela = 2, salvo = 1, duplicado = 0 (não entra no ranker), corte errado = 0.8, tempo morto/fora de rally = 1.2. O ranker treina com essa tabela, então cada revisão é reaproveitada em todas as próximas gerações.

Na página **Aprendizado** você pode:

- ver quantos exemplos bons/ruins existem e os motivos mais comuns;
- baixar o banco em **CSV** ou **JSON** (sem vídeos, só metadados e features);
- treinar o ranker na hora, sem gerar clipes.

O CSV é útil para juntar o aprendizado de vários testadores depois. Nesta versão ele é só exportação; importação automática fica para a próxima etapa.

### Revisão rápida

Para reduzir o tempo de conferência:

- botão **Revisão rápida** abre o primeiro clipe não verificado;
- **S** salva, **D** exclui, **←/→** navegam, **Espaço** dá play/pause;
- **Avançar após salvar/excluir** abre o próximo automaticamente;
- **Ordenar não verificados → Mais incertos primeiro** prioriza os clipes em que o ranker tem menos certeza;
- salvar/excluir atualiza a lista na hora, sem recarregar a página;
- a nota dos salvos é recalculada quando você clicar em **Calcular notas**, não a cada salvamento.

### Próximo passo recomendado

O banco sozinho não elimina a revisão manual, mas permite evoluir para **aprendizado ativo**:

1. o modelo separa casos óbvios (alta confiança) dos incertos;
2. você revisa primeiro apenas os incertos;
3. casos óbvios podem ser triados automaticamente com possibilidade de desfazer;
4. com mais exemplos, trocar a regressão logística por um modelo com mais features/boosting.

Também é possível importar o CSV de outros testadores para somar o banco antes de treinar.

## Editar o corte do clipe

Na página da partida, cada card tem um botão **✎** e o player do clipe tem **Editar corte**. Também é possível apertar **E** com o clipe aberto.

Na janela de edição:

- o vídeo original é aberto no ponto do clipe;
- ajuste **Início** e **Fim** em segundos ou use os botões de **-2s / -1s / -0.5s / +0.5s / +1s / +2s**;
- **Usar tempo atual** define o início ou o fim no ponto em que o vídeo está;
- **Pré-visualizar** toca exatamente o trecho marcado;
- **Salvar como clipe bom após editar** (marcado por padrão) salva o clipe corrigido. Clipes já salvos continuam salvos.

Ao salvar, o app recorta o vídeo original de novo, atualiza a miniatura, o tempo e o score, preserva o clipe antigo como histórico e registra o ajuste no aprendizado.

### O que o aprendizado faz com a edição

- o corte editado entra no banco como exemplo **bom**, com peso maior;
- o corte anterior entra como sinal de **corte errado** ou **tempo morto**, conforme o ajuste:
  - começou depois do saque → aumenta o pré-roll;
  - terminou antes do ponto → aumenta o pós-roll;
  - as duas coisas → aumenta os dois;
  - cortou excesso → trata como tempo morto;
- a página **Aprendizado → Edições manuais** mostra o **score gerado**, a **qualidade original → editada** e o quanto o início/fim mudou.

O score gerado é o score do candidato que apareceu na revisão. A qualidade original/editada usa a mesma fórmula nos dois cortes, para comparar de forma justa o efeito do ajuste. O mapa de calor é atualizado ao recarregar a página.

### Sobreposição depois da edição

Quando você alonga um clipe e ele passa a cobrir parte de outro clipe, o app avisa na hora:

- mostra o trecho sobreposto, o status (salvo/não verificado) e a porcentagem coberta;
- pergunta se deseja marcar como **duplicado**;
- se confirmar, o outro clipe é excluído com motivo **Duplicado**, entra no aprendizado com peso menor e o app segue para o próximo da revisão.

Se preferir revisar manualmente, basta cancelar. A detecção usa sobreposição de pelo menos 2 segundos ou 50% do clipe menor.
