"""Движки рендеринга типов содержимого.

Каждый движок — отдельный модуль (md, plain, json, bsl, image; в будущем pdf…).
Интерфейс: render(widget, text, name) — отрисовать в QTextEdit;
supports_editing() — можно ли редактировать как текст.
detect_engine(name, text) — определить движок по имени/содержимому;
get_engine(name) — получить движок (неизвестный → plain).
"""

from pathlib import Path

from .base import PreviewEngine
from .plain_engine import PlainTextEngine
from .md_engine import MarkdownEngine
from .json_engine import JsonEngine
from .bsl_engine import BslEngine
from .image_engine import ImageEngine

_ENGINES = {
    PlainTextEngine.name: PlainTextEngine(),
    MarkdownEngine.name: MarkdownEngine(),
    JsonEngine.name: JsonEngine(),
    BslEngine.name: BslEngine(),
    ImageEngine.name: ImageEngine(),
}

# Расширения файлов → движок (приоритет над эвристикой по содержимому)
_EXT_ENGINES = {
    ".md": MarkdownEngine.name,
    ".markdown": MarkdownEngine.name,
    ".json": JsonEngine.name,
    ".bsl": BslEngine.name,
    ".os": BslEngine.name,
    ".png": ImageEngine.name,
    ".jpg": ImageEngine.name,
    ".jpeg": ImageEngine.name,
    ".gif": ImageEngine.name,
    ".bmp": ImageEngine.name,
    ".webp": ImageEngine.name,
    ".ico": ImageEngine.name,
}


def get_engine(name: str) -> PreviewEngine:
    """Движок по имени; неизвестный/пустой — plain text."""
    return _ENGINES.get(name or "", _ENGINES[PlainTextEngine.name])


def detect_engine(name: str, text: str) -> str:
    """Определяет движок по имени заметки/файла и содержимому.

    Сначала — по расширению (md/json/bsl/image), затем эвристика по
    содержимому (Markdown-маркеры), иначе plain text.
    """
    ext = Path(name).suffix.lower()
    if ext in _EXT_ENGINES:
        return _EXT_ENGINES[ext]
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
    "JsonEngine",
    "BslEngine",
    "ImageEngine",
    "get_engine",
    "detect_engine",
]
