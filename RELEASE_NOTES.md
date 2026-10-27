# VolleyTrak 0.3.21 beta

## Pipeline de clipes mais robusto

- **Trajetória da bola tratada** com filtro de Kalman, rejeição de saltos impossíveis e interpolação de falhas curtas.
- **Contatos** passam a usar a trajetória tratada, reduzindo contatos falsos.
- **Máquina de estados do ponto**: saque → rally → fim do ponto.
  - usa apito quando disponível;
  - usa a posição do saque e a trajetória da bola quando não há apito;
  - evita pontos sobrepostos;
  - classifica o clipe como **rally** ou **ponto de saque (ace/erro)**.
- **Corte mais limpo**: 2–3s antes do saque e 1,5–3s depois do fim do ponto, com duração máxima de 20s.
- **Limite de bola adaptativo por partida**: partidas com detecção fraca não são mais descartadas por um limite fixo.
- **Atividade da quadra** agora é um sinal auxiliar; janelas de ponto não são descartadas por baixa atividade.
- O pipeline reaproveita a trajetória, contatos e atividade já calculados no reprocessamento.

## Resultado no teste

A partida APAV Inclusão foi reprocessada com o novo pipeline:

- 7 clipes salvos preservados;
- 17 novos candidatos;
- 24 clipes no total.

O primeiro processamento de uma partida nova ainda roda VballNet e atividade do zero. Reprocessamentos são mais rápidos.

## Base da 0.3.20

- Salvar **Rally** ou **Ace/erro de saque**, com pesos diferentes no aprendizado.
- Aba **Clipes salvos** com filtros, reprodução e abertura de pasta.
- Exclusão do vídeo original mantendo clipes.
- Janela de edição de corte maior.
- Reprocessamento sem apito.
- Janelas de CMD escondidas.
- Pasta dos clipes configurável.
- Som/Mudo global, velocidade 0.5x–2x e atalhos de 5s.

Baixe `VolleyTrakSetup.exe` e execute. O instalador é não assinado; o aviso do SmartScreen é esperado.
