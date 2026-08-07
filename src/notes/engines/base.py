"""Базовый интерфейс движка рендеринга.

Движок знает, как показать содержимое в QTextEdit (preview), и умеет ли тип
редактироваться как текст. Бинарные типы (картинки, pdf) редактируются
внешним редактором — движок для них помечает supports_editing() = False.
"""

from PySide6.QtWidgets import QTextEdit


class PreviewEngine:
    """Базовый движок: plain text."""

    name = "plain"

    def render(self, widget: QTextEdit, text: str, name: str) -> None:
        """Отрисовать содержимое в виджете preview."""
        widget.setPlainText(text)

    def supports_editing(self) -> bool:
        """Можно ли редактировать как текст напрямую (как заметку)."""
        return True
