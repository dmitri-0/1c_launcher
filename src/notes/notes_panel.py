"""Панель заметки: preview активной заметки (режим по умолчанию) + редактирование.

Режимы:
- preview — движок определяет формат и рендерит (пока Markdown), иначе plain text;
- редактирование (F4) — курсор в тексте, можно править; сырой текст не теряется.

Координацию с БД (сохранение текста и позиции курсора) делает NotesMixin.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PySide6.QtGui import QTextCursor

from notes.notes_manager import Note, guess_note_format


class NotesPanel(QWidget):
    """Правая панель: заголовок + тело заметки (preview / редактирование)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.title_label = QLabel("Заметка")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self.title_label)

        self.body = QTextEdit()
        self.body.setReadOnly(True)   # по умолчанию — preview
        layout.addWidget(self.body, 1)

        self.hint = QLabel("F4 — редактирование / preview")
        self.hint.setStyleSheet("color: gray;")
        layout.addWidget(self.hint)

        self._note: Note = None
        self._raw = ""
        self._name = ""
        self._edit = False

    # ── показ заметки ───────────────────────────────────────────────
    def show_note(self, note: Note):
        """Показать заметку в режиме preview (по умолчанию).

        ВАЖНО: выходим из режима редактирования ДО рендера, иначе enter_preview()
        зафиксирует в _raw текст предыдущей заметки (которая могла быть в режиме
        правки) и он попадёт в новую заметку.
        """
        self._note = note
        self._name = note.name
        self._raw = note.note
        self.title_label.setText(note.name)
        self._edit = False
        self.enter_preview()

    def clear(self):
        """Пустое состояние (ничего не выбрано)."""
        self._note = None
        self._raw = ""
        self._name = ""
        self._edit = False
        self.title_label.setText("Заметка")
        self.body.clear()
        self.body.setReadOnly(True)

    # ── режимы ──────────────────────────────────────────────────────
    def enter_preview(self):
        """Режим preview: рендер по формату (md → Markdown, иначе plain text).

        Перед рендером фиксируем правки из режима редактирования в _raw.
        """
        if self._edit:
            self._raw = self.body.toPlainText()
        self._edit = False
        self.body.setReadOnly(True)
        if guess_note_format(self._name, self._raw) == "md":
            self.body.setMarkdown(self._raw)
        else:
            self.body.setPlainText(self._raw)

    def enter_edit(self, caret: int = 0):
        """Режим редактирования: сырой текст, курсор восстанавливается."""
        self._edit = True
        self.body.setReadOnly(False)
        self.body.setPlainText(self._raw)
        cursor = self.body.textCursor()
        cursor.setPosition(min(max(caret, 0), len(self._raw)))
        self.body.setTextCursor(cursor)

    def is_edit_mode(self) -> bool:
        return self._edit

    # ── данные ──────────────────────────────────────────────────────
    def get_text(self) -> str:
        """Сырой текст (в preview — сохранённый, в редактировании — текущий)."""
        return self.body.toPlainText() if self._edit else self._raw

    def current_caret(self) -> int:
        """Позиция курсора; в preview возвращает 0 (не трогаем сохранённую)."""
        if not self._edit:
            return 0
        return self.body.textCursor().position()

    def focus_editor(self):
        self.body.setFocus()
