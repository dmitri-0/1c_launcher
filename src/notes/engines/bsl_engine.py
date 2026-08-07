"""Движок BSL (1С): текст с подсветкой для тёмной темы.

Плюс навигатор: extract_bsl_methods() находит объявления Процедура/Функция
(как outline в VS Code) — панель показывает их в выпадающем списке.
"""

import re

from .base import PreviewEngine
from .highlighters import BslHighlighter

_METHOD_RE = re.compile(r"^\s*(Процедура|Функция)\s+([^\s(]+)")


def extract_bsl_methods(text: str):
    """Список объявлений методов BSL: [(номер_строки, 'Процедура', имя), ...].

    Эвристика (как outline): строка начинается с «Процедура»/«Функция» + имя.
    Комментарии («// Процедура…») и строки-литералы не матчатся.
    """
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = _METHOD_RE.match(line)
        if m:
            out.append((i, m.group(1), m.group(2)))
    return out


class BslEngine(PreviewEngine):
    name = "bsl"
    highlighter_cls = BslHighlighter

    def render(self, widget, text: str, name: str) -> None:
        widget.setPlainText(text)
