# VolleyTrak 0.3.4 beta

- Novo botão **Gerar novamente (aprendizados)** na página da partida.
- A nova geração usa o perfil aprendido, o ranker e os clipes excluídos, sem rodar VballNet de novo.
- Clipes salvos são preservados.
- Trechos excluídos como **Corte errado / rally pela metade** podem voltar como **Recuperado**, com pré/pós-roll ajustado pelo submotivo.
- Opção **Reavaliar minutos sem clipes no mapa de calor** (marcada por padrão): procura rallies nos vãos do mapa e cria candidatos com o selo **Lacuna**.
- Nova ferramenta de **Corte manual** abaixo do vídeo:
  - clique num bloco/vão do mapa para posicionar e já marcar 15s;
  - marque início/fim, pré-visualize e crie o clipe;
  - o clipe manual vai direto para **Salvos** com o selo **Manual** e não é apagado na próxima geração.
- O resumo mostra o modo de áudio e o aprendizado aplicado (pré/pós-roll, velocidade, bola mínima e AUC do ranker).
- O limite de candidatos comuns subiu para 100 e os candidatos de lacuna/recuperados não são descartados por ele.

Baixe todas as partes do Portable ou do Setup e extraia a `.001` com 7-Zip.
Windows 10/11 x64, driver NVIDIA e ~8 GB livres.