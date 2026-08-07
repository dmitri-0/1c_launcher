"""Движок XML: красивое форматирование на preview.

Валидный XML переформатируется (ElementTree.indent); невалидный — как есть.
Подсветка — XmlHighlighter (теги/атрибуты/комментарии, тёмная тема).
Редактирование — по исходному тексту.
"""

import xml.etree.ElementTree as ET

from .base import PreviewEngine
from .highlighters import XmlHighlighter


def pretty_xml(text: str) -> str:
    """Переформатировать XML (отступ 2 пробела); при ошибке — исходный текст."""
    try:
        root = ET.fromstring(text)
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")
    except (ET.ParseError, RecursionError):
        return text


class XmlEngine(PreviewEngine):
    name = "xml"
    highlighter_cls = XmlHighlighter

    def render(self, widget, text: str, name: str) -> None:
        widget.setPlainText(pretty_xml(text))
