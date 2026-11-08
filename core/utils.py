"""Вспомогательные функции, общие для всех модулей SpaceLens."""

from __future__ import annotations

import os
import subprocess
import sys


def format_size(num_bytes: float) -> str:
    """Автоматический перевод байт в КБ/МБ/ГБ/ТБ."""
    n = float(num_bytes)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if abs(n) < 1024.0 or unit == "ТБ":
            if unit == "Б":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} ТБ"


def open_in_explorer(path: str) -> None:
    """Открыть папку в Проводнике (или выделить файл). Кроссплатформенно."""
    path = os.path.abspath(path)
    if sys.platform == "win32":
        if os.path.isdir(path):
            os.startfile(path)  # noqa: S606
        else:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        target = path if os.path.isdir(path) else os.path.dirname(path)
        subprocess.Popen(["xdg-open", target])