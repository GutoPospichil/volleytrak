from __future__ import annotations

import subprocess
import sys


def hidden_kwargs() -> dict:
    """Return process-creation flags that keep console windows hidden.

    VolleyTrak runs under ``pythonw.exe``, but console programs such as
    ffmpeg still create a new console window when started without these
    flags. That is why clip generation used to flash CMD windows.
    """

    if sys.platform != "win32":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def run_hidden(command, **kwargs):
    """Run a command without opening a console window on Windows."""

    kwargs.update(hidden_kwargs())
    return subprocess.run(command, **kwargs)


def popen_hidden(command, **kwargs):
    """Start a command without opening a console window on Windows."""

    kwargs.update(hidden_kwargs())
    return subprocess.Popen(command, **kwargs)
