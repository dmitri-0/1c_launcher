"""Движок JSON: текст с подсветкой (панель подсветки — highlighter_cls)."""

from .base import PreviewEngine
from .highlighters import JsonHighlighter


class JsonEngine(PreviewEngine):
    name = "json"
    highlighter_cls = JsonHighlighter

    def render(self, widget, text: str, name: str) -> None:
        widget.setPlainText(text)
