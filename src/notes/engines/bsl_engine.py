"""Движок BSL (1С): текст с подсветкой для тёмной темы."""

from .base import PreviewEngine
from .highlighters import BslHighlighter


class BslEngine(PreviewEngine):
    name = "bsl"
    highlighter_cls = BslHighlighter

    def render(self, widget, text: str, name: str) -> None:
        widget.setPlainText(text)
