from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _log_path() -> Path:
    portable = ROOT / "data"
    if portable.is_dir():
        return portable / "desktop.log"
    local = Path(os.getenv("LOCALAPPDATA", str(ROOT))) / "VolleyTrakData"
    local.mkdir(parents=True, exist_ok=True)
    return local / "desktop.log"


# pythonw.exe nao tem stdout/stderr. Sem isso, qualquer print/erro fecha o app.
if sys.stdout is None or sys.stderr is None:
    try:
        _log = open(_log_path(), "a", encoding="utf-8", buffering=1)
        sys.stdout = _log
        sys.stderr = _log
    except Exception:
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
            sys.stderr = sys.stdout
        except Exception:
            pass


def configure_data_dir() -> Path:
    if not os.getenv("VOLLEYTRAK_DATA"):
        portable = ROOT / "data"
        local = Path(os.getenv("LOCALAPPDATA", str(ROOT))) / "VolleyTrakData"
        os.environ["VOLLEYTRAK_DATA"] = str(portable if portable.is_dir() else local)
    return Path(os.environ["VOLLEYTRAK_DATA"])


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def is_volleytrak(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/openapi.json", timeout=1.0
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
        return (data.get("info") or {}).get("title") == "VolleyTrak"
    except Exception:
        return False


def wait_for_server(port: int, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/", timeout=1.0
            ) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


class DesktopApi:
    def choose_folder(self) -> str:
        try:
            import webview

            if not webview.windows:
                return ""
            result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
            if not result:
                return ""
            if isinstance(result, (list, tuple)):
                return str(result[0])
            return str(result)
        except Exception as exc:
            print(f"erro ao escolher pasta: {exc}", flush=True)
            return ""


def show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "VolleyTrak", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    os.chdir(ROOT)
    data_dir = configure_data_dir()

    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    port = args.port
    server = None
    server_thread = None

    if not port:
        if is_volleytrak(8000):
            port = 8000
            print("VolleyTrak ja esta rodando em 8000; abrindo janela.", flush=True)
        elif not port_open(8000):
            port = 8000
        else:
            port = free_port()

    if port != 8000 or not is_volleytrak(port):
        import uvicorn
        from app.main import app

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()
        if not wait_for_server(port):
            show_error("Nao foi possivel iniciar o servidor do VolleyTrak.")
            return 1

    url = f"http://127.0.0.1:{port}"
    print(f"VolleyTrak em {url}", flush=True)

    if args.browser:
        webbrowser.open(url)
        try:
            while server_thread is not None and server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        if server is not None:
            server.should_exit = True
            server_thread.join(timeout=5)
        return 0

    try:
        import webview
    except Exception as exc:
        show_error(
            "A janela do aplicativo nao esta disponivel.\n"
            f"{exc}\n\nO VolleyTrak sera aberto no navegador."
        )
        webbrowser.open(url)
        if server is not None:
            try:
                while server_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            server.should_exit = True
            server_thread.join(timeout=5)
        return 0

    icon_candidates = [
        ROOT / "VolleyTrak.ico",
        ROOT / "installer" / "VolleyTrak.ico",
        ROOT / "app" / "static" / "favicon.ico",
    ]
    icon = next((str(path) for path in icon_candidates if path.is_file()), None)
    storage = data_dir / "webview"
    storage.mkdir(parents=True, exist_ok=True)

    window = webview.create_window(
        "VolleyTrak",
        url,
        width=1440,
        height=900,
        min_size=(1080, 700),
        background_color="#0b0f14",
        confirm_close=False,
        js_api=DesktopApi(),
    )
    try:
        webview.start(
            icon=icon,
            private_mode=False,
            storage_path=str(storage),
        )
    except Exception as exc:
        show_error(
            "Nao foi possivel abrir a janela do aplicativo.\n"
            f"{exc}\n\nO VolleyTrak sera aberto no navegador."
        )
        webbrowser.open(url)
        if server is not None:
            try:
                while server_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    finally:
        if server is not None:
            server.should_exit = True
            server_thread.join(timeout=8)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback

        traceback.print_exc()
        try:
            show_error(
                "O VolleyTrak encontrou um erro ao abrir.\n\n"
                + traceback.format_exc(limit=4)
            )
        except Exception:
            pass
        raise SystemExit(1)
