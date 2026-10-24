# VolleyTrak 0.3.6 beta

## Editar corte do clipe
- Botão **✎** no card e **Editar corte** no player; atalho **E**.
- Janela de edição com o vídeo original, início/fim em segundos e botões de ajuste rápido:
  - **-2s / -1s / -0.5s / +0.5s / +1s / +2s**;
  - **Usar tempo atual** como início ou fim;
  - **Pré-visualizar** o trecho marcado.
- **Salvar como clipe bom após editar** (marcado por padrão).
- O clipe é recortado de novo, com miniatura, tempo e score atualizados.
- Clipes já salvos continuam salvos.
- O vídeo e a miniatura usam cache desativado para a edição aparecer na hora.

## Edição como aprendizado
- O corte editado entra no banco como exemplo **bom**, com peso maior.
- O corte anterior é registrado como **corte errado** ou **tempo morto**, conforme o ajuste:
  - começou depois do saque → aumenta pré-roll;
  - terminou antes do ponto → aumenta pós-roll;
  - as duas coisas → aumenta os dois;
  - cortou excesso → tempo morto.
- O perfil global e o perfil da partida são recalculados.
- Nova tabela `clip_edits` guarda o histórico de ajustes.

## Análise na página Aprendizado
- Nova seção **Edições manuais**.
- Mostra quantidade de edições, quantas melhoraram, Δ médio de qualidade e deslocamento médio de início/fim.
- Tabela com **score gerado**, **qualidade original → editada**, ajuste em segundos, motivo e data.
- O score gerado é o candidato da revisão; a qualidade original/editada usa a mesma fórmula para comparar o efeito do corte.

## Base da 0.3.5
- Banco de aprendizado `learning_examples` com CSV/JSON.
- Revisão rápida com atalhos, auto-avançar e ordenação por incerteza.
- Perfil global recalculado a partir de todos os feedbacks.

Baixe todas as partes do Portable ou do Setup e extraia a `.001` com 7-Zip.
Windows 10/11 x64, driver NVIDIA e ~8 GB livres.