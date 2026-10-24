# VolleyTrak 0.3.10 beta

## Filtro de quadra vazia/parada
- O pipeline mede o movimento dentro da quadra em ~1 amostra por segundo.
- Usa os 4 pontos da calibração para criar uma máscara da quadra.
- Clipes com movimento médio abaixo de **4** são descartados.
- O resultado fica em `activity.json` e é reaproveitado nas próximas gerações.
- Primeira análise leva cerca de 80 segundos para uma partida de 52 minutos.
- Nova opção **Ignorar quadra vazia/parada**, marcada por padrão ao gerar novamente.
- Se o arquivo de atividade não existir, ele é calculado automaticamente na geração.
- Clipes salvos e manuais são preservados.

## Base da 0.3.9
- Duplicados após edição: o app detecta sobreposição, pergunta e marca como duplicado.
- Duplicados não entram no ranker (peso 0), para não ensinar conteúdo ruim.
- Após editar e salvar um clipe não verificado, a revisão avança para o próximo.

## Limitação
- O filtro remove quadra vazia e todos parados. Tempo morto com jogadores se movimentando, comemoração ou banco agitado ainda pode passar; nesses casos o motivo **Tempo morto** continua correto.

Baixe todas as partes do Portable ou do Setup e extraia a `.001` com 7-Zip.
Windows 10/11 x64, driver NVIDIA e ~8 GB livres.