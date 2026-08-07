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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QToolButton, QComboBox,
)
from PySide6.QtGui import QTextCursor, QImage, QFont
from PySide6.QtCore import Qt, QEvent

from notes.engines import detect_engine, get_engine, PreviewEngine
from notes.notes_document import NoteTextDocument

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
                # Обработчик вернул "" (нет активной заметки / ошибка БД):
                # НЕ вставляем сырой image-объект — Qt вставил бы символ-заглушку
                # \ufffc, который «затирает» текст заметки (пустая заметка).
                return
        super().insertFromMimeData(source)


class NotesPanel(QWidget):
    """Правая панель: заголовок + тело (preview / редактирование) + zoom."""

    def __init__(self, parent=None, initial_zoom: int = 0):
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

        # Навигатор по методам BSL (как outline в VS Code): виден только
        # для bsl-контента; выбор — курсор к методу.
        self.methods_combo = QComboBox()
        self.methods_combo.setVisible(False)
        self.methods_combo.setMinimumWidth(160)
        self.methods_combo.setToolTip("Методы BSL: выберите — курсор перейдёт к методу")
        self.methods_combo.activated.connect(self._jump_to_method)
        header.addWidget(self.methods_combo, 1)

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
        # Документ с загрузчиком вложенных картинок (noteimg:<id> из notes.db)
        self._doc = NoteTextDocument(self.body)
        self.body.setDocument(self._doc)
        layout.addWidget(self.body, 1)

        self.hint = QLabel("F4 — редактирование / preview · Ctrl+колесо — zoom")
        self.hint.setStyleSheet("color: gray;")
        layout.addWidget(self.hint)

        self._note = None
        self._raw = ""
        self._name = ""
        self._edit = False
        self._binary = False
        self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, int(initial_zoom)))
        self._highlighter = None
        self._base_pt = self.body.font().pointSizeF() or 11.0
        self._method_lines: list = []  # номера строк методов (для навигатора)

    # ── вставка картинки из буфера ──────────────────────────────────
    @property
    def image_handler(self):
        """Прокси на body (NotesTextEdit): обработчик вставки картинки."""
        return self.body.image_handler

    @image_handler.setter
    def image_handler(self, handler):
        self.body.image_handler = handler

    # ── загрузчик вложенных картинок (для md-preview) ────────────────
    @property
    def resource_loader(self):
        """Прокси на документ: callable(image_id) -> bytes для noteimg:<id>."""
        return self._doc.loader

    @resource_loader.setter
    def resource_loader(self, loader):
        self._doc.loader = loader

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

    # ── показ заметки / файла каталога ─────────────────────────────
    def show_note(self, note):
        """Показать заметку в режиме preview (по умолчанию).

        ВАЖНО: выходим из режима редактирования ДО рендера, иначе enter_preview()
        зафиксирует в _raw текст предыдущей заметки (которая могла быть в режиме
        правки) и он попадёт в новую заметку.
        """
        self._note = note
        self._name = note.name
        self._raw = note.note
        self._binary = False
        self.title_label.setText(note.name)
        self._edit = False
        self._render_preview()

    def show_content(self, name: str, text: str, binary: bool = False, engine_name: str = None):
        """Показать произвольное содержимое (файл каталога) в preview.

        binary=True — бинарный файл: только заглушка, редактирование недоступно.
        engine_name — явный движок (например, 'image' с text=путь к файлу);
        иначе движок определяется по имени/содержимому.
        """
        self._note = None
        self._name = name
        self._raw = text
        self._binary = binary
        self.title_label.setText(name)
        self._edit = False
        if binary:
            self.body.setReadOnly(True)
            self.body.setPlainText(
                "[Бинарный файл — F4 или контекстное меню: открыть внешним приложением]"
            )
        else:
            self._render_preview(engine=get_engine(engine_name) if engine_name else None)

    def clear(self):
        """Пустое состояние (ничего не выбрано)."""
        self._note = None
        self._raw = ""
        self._name = ""
        self._edit = False
        self._binary = False
        self.title_label.setText("Заметка")
        self.body.clear()
        self.body.setReadOnly(True)

    # ── режимы ──────────────────────────────────────────────────────
    def _render_preview(self, engine: PreviewEngine = None):
        """Рендер по движку: базовый шрифт масштабируется ДО рендера,
        чтобы все блоки (код/заголовки) менялись пропорционально."""
        self._edit = False
        self.body.setReadOnly(True)
        if engine is None:
            engine = get_engine(detect_engine(self._name, self._raw))
        self._apply_zoom_font()
        engine.render(self.body, self._raw, self._name)
        self._apply_highlighter(engine)
        self._update_methods_navigator()

    # ── навигатор по методам BSL ────────────────────────────────────
    def _update_methods_navigator(self):
        """Для bsl-контента заполняет выпадающий список методов; иначе прячет."""
        from notes.engines.bsl_engine import extract_bsl_methods

        self._method_lines = []
        self.methods_combo.clear()
        if detect_engine(self._name, self._raw) != "bsl":
            self.methods_combo.setVisible(False)
            return
        methods = extract_bsl_methods(self._raw)
        self._method_lines = [line for line, _, _ in methods]
        for line, kind, name in methods:
            self.methods_combo.addItem(f"{line:>4}  {kind} {name}()")
        if methods:
            self.methods_combo.setVisible(True)
            self.methods_combo.setCurrentIndex(-1)
        else:
            self.methods_combo.setVisible(False)

    def _jump_to_method(self, combo_index: int):
        """Переместить курсор к методу из навигатора (номер строки — 1-based)."""
        if not (0 <= combo_index < len(self._method_lines)):
            return
        line = self._method_lines[combo_index]
        cursor = self.body.textCursor()
        cursor.movePosition(QTextCursor.Start)
        for _ in range(max(0, line - 1)):
            cursor.movePosition(QTextCursor.Down)
        self.body.setTextCursor(cursor)
        self.body.ensureCursorVisible()

    def _apply_highlighter(self, engine: PreviewEngine):
        """Подсветка синтаксиса для движков с highlighter_cls (bsl/json);
        для остальных — отключаем."""
        hl_cls = getattr(engine, "highlighter_cls", None)
        if hl_cls is None:
            if self._highlighter is not None:
                self._highlighter.setDocument(None)
                self._highlighter = None
            return
        if self._highlighter is None or not isinstance(self._highlighter, hl_cls):
            # отцепить старый хайлайтер до создания нового — иначе оба висят
            # на документе (двойная работа + утечка по сигналам)
            if self._highlighter is not None:
                self._highlighter.setDocument(None)
            self._highlighter = hl_cls(self._doc)
        self._highlighter.setDocument(self._doc)
        self._highlighter.rehighlight()

    def enter_preview(self):
        """Выйти в preview (зафиксировав правки из режима редактирования)."""
        if self._edit:
            self._raw = self.body.toPlainText()
        self._render_preview()

    def enter_edit(self, caret: int = 0):
        """Режим редактирования: сырой текст, курсор восстанавливается."""
        if self._binary:
            return  # бинарный контент нельзя редактировать как текст
        self._edit = True
        self.body.setReadOnly(False)
        self._apply_zoom_font()
        self.body.setPlainText(self._raw)
        cursor = self.body.textCursor()
        cursor.setPosition(min(max(caret, 0), len(self._raw)))
        self.body.setTextCursor(cursor)
        self._update_methods_navigator()  # навигатор работает и в редактировании

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
