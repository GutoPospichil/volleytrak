# VolleyTrak 0.3.5 beta

## Banco de aprendizado
- Nova tabela local `learning_examples`: cada clipe salvo ou excluído vira um exemplo com label, motivo, features e peso.
- O histórico existente é importado automaticamente na primeira execução.
- Página **Aprendizado** com contagens, motivos, exemplos recentes e AUC do ranker.
- Exportação do banco em **CSV** ou **JSON** (sem vídeos), útil para juntar feedback de testadores.
- Botão **Atualizar modelos agora**: treina o ranker e recalcula o perfil global sem gerar clipes.
- O ranker agora usa pesos: estrela = 2, duplicado = 0.5, corte errado = 0.8, tempo morto/fora de rally = 1.2.
- O perfil global passou a ser recalculado a partir de todos os feedbacks (pré-roll 2.9 s, pós-roll 1.7 s, bola mínima 18%).

## Revisão rápida
- Botão **Revisão rápida** abre o primeiro clipe não verificado.
- Atalhos: **S** salvar, **D** excluir, **←/→** navegar, **Espaço** play/pause, **Esc** fechar.
- **Avançar após salvar/excluir** automático.
- Ordenação **Mais incertos primeiro** pelo score do ranker.
- Salvar/excluir atualiza a lista na hora, sem recarregar a página.
- A nota dos salvos é calculada sob demanda em **Calcular notas**, deixando a revisão mais rápida.

## Outros
- O modo de áudio e o aprendizado aplicado continuam visíveis na partida.
- O link **Aprendizado** aparece no topo do app.
- Esta versão não faz triagem automática de clipes: com a AUC atual (~0.64), a revisão dos incertos ainda é o caminho seguro.

Baixe todas as partes do Portable ou do Setup e extraia a `.001` com 7-Zip.
Windows 10/11 x64, driver NVIDIA e ~8 GB livres.