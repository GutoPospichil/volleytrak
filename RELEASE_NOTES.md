# VolleyTrak 0.3.9 beta

## Duplicados após edição
- Ao alongar um clipe e cobrir parte de outro, o app detecta a sobreposição na hora.
- Mostra o trecho, o status (salvo/não verificado) e a porcentagem coberta.
- Pergunta se deseja marcar o clipe sobreposto como **Duplicado**.
- Se confirmar, o duplicado é excluído e o app segue para o próximo clipe.
- Duplicados ficam registrados no banco, mas com **peso 0 no ranker**: são redundância, não conteúdo ruim, e não devem ensinar o modelo a rejeitar rallies parecidos.
- Se cancelar, nada é apagado.
- Critério: sobreposição de pelo menos 2 segundos ou 50% do clipe menor.

## Base da 0.3.8
- Após editar e salvar um clipe não verificado, ele vai para Salvos e a revisão avança para o próximo.
- Editar um clipe já salvo fecha a janela após salvar.
- Aviso rápido com score gerado → editado.

Baixe todas as partes do Portable ou do Setup e extraia a `.001` com 7-Zip.
Windows 10/11 x64, driver NVIDIA e ~8 GB livres.