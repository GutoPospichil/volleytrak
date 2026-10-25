# VolleyTrak 0.3.11 beta

## Marca
- Logo VT VolleyTrak no topo, favicon, ícone do instalador e ícones PWA.
- Manifest PWA em `/static/manifest.webmanifest`; o navegador pode oferecer **Instalar VolleyTrak**.
- Atalhos do Windows usam o ícone do VolleyTrak.

## VolleyTrak como aplicativo desktop
- Nova janela nativa via WebView2 (pywebview), sem barra de navegador.
- O atalho **VolleyTrak** da área de trabalho abre o app, inicia o servidor Python junto e fecha o servidor quando a janela fecha.
- A interface continua sendo a mesma HTML/CSS/JS; o processamento pesado segue em Python/OpenCV/ONNX.
- Fallback **VolleyTrak (navegador)** e **VolleyTrak (janela web)** para abrir no Chrome/Edge.
- Dependência `pywebview` incluída no Python portátil.

## Base da 0.3.10
- Filtro de quadra vazia/parada por movimento dentro da quadra.
- Opção **Ignorar quadra vazia/parada** marcada por padrão.
- Duplicados após edição e edição com aprendizado.

Baixe todas as partes do Portable ou do Setup e extraia a `.001` com 7-Zip.
Windows 10/11 x64, WebView2 (já vem com o Windows/Edge), driver NVIDIA e ~8 GB livres.