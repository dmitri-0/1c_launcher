"""Панель заметки: preview активного содержимого (режим по умолчанию) + редактирование.

Режимы:
- preview — движок рендеринга (по имени/содержимому: md/plain и др.) показывает
  содержимое; если тип не редактируется как текст — только просмотр;
- редактирование (F4) — курсор в тексте, можно править; сырой текст не теряется.

Zoom: кнопки [−][0][+] и Ctrl+колесо. При preview масштабируется базовый шрифт
ДО рендера движком, поэтому все «блоки» (код, заголовки) масштабируются
пропорционально.

Вставка картинки из буфера (в режиме текста): если задан image_handler,
картинка сохраняется вовне, а в текст вставляется placeholder (md-синтаксис),
который preview-движок md показывает как изображение.
"""

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QToolButton,
)
from PySide6.QtGui import QTextCursor, QImage, QFont
from PySide6.QtCore import Qt, QEvent

from notes.engines import detect_engine, get_engine

# Шаг zoom в пунктах за одну ступень
_ZOOM_STEP_PT = 2.0
_ZOOM_MIN = -8   # 8 ступеней вниз
_ZOOM_MAX = 12   # 12 ступеней вверх


class NotesTextEdit(QTextEdit):
    """QTextEdit, который вставляет картинку из буфера как placeholder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_handler = None  # callable(QImage) -> placeholder str | ""

    def insertFromMimeData(self, source):
        if self.image_handler is not None and source.hasImage():
            image = QImage(source.imageData())
            if not image.isNull():
                placeholder = self.image_handler(image)
                if placeholder:
                    self.textCursor().insertText(placeholder)
                    return
        super().insertFromMimeData(source)


class NotesPanel(QWidget):
    """Правая панель: заголовок + тело (preview / редактирование) + zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── шапка: заголовок + кнопки zoom ──
        header = QHBoxLayout()
        header.setSpacing(4)
        self.title_label = QLabel("Заметка")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        header.addWidget(self.title_label, 1)

        self._zoom_out_btn = QToolButton()
        self._zoom_out_btn.setText("−")
        self._zoom_out_btn.setToolTip("Уменьшить (Ctrl+колесо вниз)")
        self._zoom_reset_btn = QToolButton()
        self._zoom_reset_btn.setText("0")
        self._zoom_reset_btn.setToolTip("Сбросить zoom")
        self._zoom_in_btn = QToolButton()
        self._zoom_in_btn.setText("+")
        self._zoom_in_btn.setToolTip("Увеличить (Ctrl+колесо вверх)")
        for btn in (self._zoom_out_btn, self._zoom_reset_btn, self._zoom_in_btn):
            btn.setFixedWidth(26)
            btn.setAutoRaise(True)
        self._zoom_out_btn.clicked.connect(lambda: self.change_zoom(-1))
        self._zoom_reset_btn.clicked.connect(lambda: self.change_zoom(0, reset=True))
        self._zoom_in_btn.clicked.connect(lambda: self.change_zoom(1))
        header.addWidget(self._zoom_out_btn)
        header.addWidget(self._zoom_reset_btn)
        header.addWidget(self._zoom_in_btn)
        layout.addLayout(header)

        self.body = NotesTextEdit()
        self.body.setReadOnly(True)   # по умолчанию — preview
        self.body.installEventFilter(self)
        layout.addWidget(self.body, 1)

        self.hint = QLabel("F4 — редактирование / preview · Ctrl+колесо — zoom")
        self.hint.setStyleSheet("color: gray;")
        layout.addWidget(self.hint)

        self._note = None
        self._raw = ""
        self._name = ""
        self._edit = False
        self._zoom = 0
        self._base_pt = self.body.font().pointSizeF() or 11.0

    # ── вставка картинки из буфера ──────────────────────────────────
    @property
    def image_handler(self):
        """Прокси на body (NotesTextEdit): обработчик вставки картинки."""
        return self.body.image_handler

    @image_handler.setter
    def image_handler(self, handler):
        self.body.image_handler = handler

    # ── zoom ─────────────────────────────────────────────────────────
    def change_zoom(self, steps: int = 0, reset: bool = False):
        """Изменить zoom (ступени). reset=True — вернуть к 100%."""
        if reset:
            self._zoom = 0
        else:
            self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom + steps))
        if self._edit:
            self._apply_zoom_font()          # в редактировании достаточно шрифта
        else:
            self._render_preview()           # в preview — пере-рендер с новым шрифтом

    def _apply_zoom_font(self):
        font = QFont(self.body.font())
        font.setPointSizeF(max(6.0, self._base_pt + self._zoom * _ZOOM_STEP_PT))
        self.body.setFont(font)

    def eventFilter(self, obj, event):
        """Ctrl+колесо над текстом — zoom (не влияет на preview/редактирование)."""
        if obj is self.body and event.type() == QEvent.Wheel and (event.modifiers() & Qt.ControlModifier):
            delta = event.angleDelta().y()
            if delta > 0:
                self.change_zoom(1)
            elif delta < 0:
                self.change_zoom(-1)
            event.accept()
            return True
        return super().eventFilter(obj, event)

    # ── показ заметки ───────────────────────────────────────────────
    def show_note(self, note):
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
        self._render_preview()

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
    def _render_preview(self):
        """Рендер по движку: базовый шрифт масштабируется ДО рендера,
        чтобы все блоки (код/заголовки) менялись пропорционально."""
        self._edit = False
        self.body.setReadOnly(True)
        engine = get_engine(detect_engine(self._name, self._raw))
        self._apply_zoom_font()
        engine.render(self.body, self._raw, self._name)

    def enter_preview(self):
        """Выйти в preview (зафиксировав правки из режима редактирования)."""
        if self._edit:
            self._raw = self.body.toPlainText()
        self._render_preview()

    def enter_edit(self, caret: int = 0):
        """Режим редактирования: сырой текст, курсор восстанавливается."""
        self._edit = True
        self.body.setReadOnly(False)
        self._apply_zoom_font()
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
