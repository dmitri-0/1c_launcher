"""Редактор заметки: заголовок + тело (plain text).

F4 — переключить режим:
  preview — движок понимает формат и рендерит (пока Markdown), если формат
            не распознан — показывается как plain text;
  редактирование — сырой текст.

Тело хранится как plain text всегда (preview не меняет содержимое).
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt

from notes.notes_manager import guess_note_format


class NotesDialog(QDialog):
    """Диалог просмотра/редактирования заметки."""

    def __init__(self, parent=None, title: str = "", text: str = "", name: str = "",
                 fmt: str = None):
        super().__init__(parent)
        self.setWindowTitle("Заметка")
        self.resize(680, 500)

        self._raw = text
        self._name = name or title          # имя заметки — для автоопределения формата
        self._fmt = fmt                      # None = автоопределение при preview
        self._preview = False

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("Заголовок заметки")
        layout.addWidget(self.title_edit)

        self.body = QTextEdit()
        self.body.setPlainText(text)
        layout.addWidget(self.body, 1)

        hint = QLabel("F4 — preview (Markdown) / редактирование")
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self._f4 = QShortcut(QKeySequence("F4"), self)
        self._f4.activated.connect(self.toggle_preview)

    def _current_format(self) -> str:
        if self._fmt:
            return self._fmt
        title = self.title_edit.text().strip() or self._name
        return guess_note_format(title, self._raw)

    def toggle_preview(self):
        """Переключить preview (рендер по формату) / редактирование."""
        if not self._preview:
            self._raw = self.body.toPlainText()
            self._preview = True
            self.body.setReadOnly(True)
            if self._current_format() == "md":
                self.body.setMarkdown(self._raw)   # Markdown → форматированный вид
            else:
                self.body.setPlainText(self._raw)  # формат не распознан → plain text
            self.setWindowTitle("Заметка — preview (F4 — редактирование)")
        else:
            self._preview = False
            self.body.setReadOnly(False)
            self.body.setPlainText(self._raw)
            self.setWindowTitle("Заметка")

    def get_data(self):
        """Возвращает (заголовок, текст). Текст всегда сырой (plain)."""
        text = self._raw if self._preview else self.body.toPlainText()
        return self.title_edit.text().strip(), text
