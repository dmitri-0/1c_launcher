"""Движки рендеринга типов содержимого.

Каждый движок — отдельный модуль (md, plain; в будущем json, bsl, image, pdf…).
Интерфейс: render(widget, text, name) — отрисовать в QTextEdit.
detect_engine(name, text) — определить движок по имени/содержимому;
get_engine(name) — получить движок (неизвестный → plain).
"""

from typing import Optional

from .base import PreviewEngine
from .plain_engine import PlainTextEngine
from .md_engine import MarkdownEngine

_ENGINES = {
    PlainTextEngine.name: PlainTextEngine(),
    MarkdownEngine.name: MarkdownEngine(),
}


def get_engine(name: str) -> PreviewEngine:
    """Движок по имени; неизвестный/пустой — plain text."""
    return _ENGINES.get(name or "", _ENGINES[PlainTextEngine.name])


def detect_engine(name: str, text: str) -> str:
    """Определяет движок по имени заметки/файла и содержимому.

    Пока понимаем Markdown (по расширению .md/.markdown или маркерам),
    остальное — plain text. В будущем здесь добавятся json/bsl/image/pdf.
    """
    if name.lower().endswith(".md") or name.lower().endswith(".markdown"):
        return MarkdownEngine.name
    for line in text[:4000].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(marker) for marker in MarkdownEngine.MARKERS):
            return MarkdownEngine.name
        break  # проверяем только первую непустую строку
    return PlainTextEngine.name


__all__ = [
    "PreviewEngine",
    "PlainTextEngine",
    "MarkdownEngine",
    "get_engine",
    "detect_engine",
]
