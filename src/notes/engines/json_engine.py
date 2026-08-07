"""Движок JSON: красивое форматирование на preview + подсветка (тёмная).

Редактирование — по исходному тексту; при preview валидный JSON
переформатируется (indent=2, ensure_ascii=False), невалидный — как есть.
"""

import json

from .base import PreviewEngine
from .highlighters import JsonHighlighter


def pretty_json(text: str) -> str:
    """Переформатировать JSON (indent=2); при ошибке парсинга — исходный текст."""
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except (ValueError, TypeError, RecursionError):
        return text


class JsonEngine(PreviewEngine):
    name = "json"
    highlighter_cls = JsonHighlighter

    def render(self, widget, text: str, name: str) -> None:
        widget.setPlainText(pretty_json(text))
