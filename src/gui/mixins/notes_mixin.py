"""Миксин «Заметки»: узел в дереве + панель preview/редактирования.

Поток:
- навигация по дереву заметок → в правой панели сразу показывается preview
  активной заметки (режим по умолчанию);
- F4 → режим редактирования (курсор в тексте, позиция запоминается в БД);
- F4 ещё раз / переключение заметки / закрытие окна → текст и позиция курсора
  сохраняются в notes.db.
"""

from datetime import datetime

from PySide6.QtWidgets import QMenu, QInputDialog
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QKeySequence, QShortcut

from config import NOTES_PANEL_WIDTH_PERCENT
from notes.notes_manager import NotesManager, Note
from notes.notes_tree_builder import NotesTreeBuilder, NOTES_ROOT_DATA


class NotesMixin:
    """Интеграция менеджера заметок в главное окно."""

    def init_notes(self):
        self.notes_mixin = self  # короткий алиас для обращений из других миксинов
        self.notes_manager = None
        self.notes_builder = None
        self._active_note_id = None
        try:
            self.notes_manager = NotesManager()
            self.notes_builder = NotesTreeBuilder(self.model, self.notes_manager)
            self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._on_notes_context_menu)
            self.tree.doubleClicked.connect(self._on_notes_double_clicked)
            self.tree.selectionModel().currentChanged.connect(self._on_notes_selection_changed)
            self.notes_panel.image_handler = self._save_note_image
            self._focus_switch = QShortcut(QKeySequence("Ctrl+Tab"), self)
            self._focus_switch.activated.connect(self._switch_focus)
        except Exception as e:
            # Битый/недоступный notes.db не должен ронять лаунчер при старте
            print(f"Заметки отключены: {e}")
            self.statusBar.showMessage(f"Заметки отключены: {e}", 5000)

    def load_bases(self):
        # Кооперативный override: BasesDataMixin перечитывает базы и очищает модель,
        # после чего пересобираем узел «Заметки».
        super().load_bases()
        self.ensure_notes_node()

    # ── дерево ───────────────────────────────────────────────────────
    def ensure_notes_node(self):
        """Пересобрать корневой узел «📝 Заметки» (удаляет старый, если есть)."""
        if self.notes_builder is None:
            return  # заметки отключены (не удалось инициализировать БД)
        root = self.model
        for i in range(root.rowCount()):
            item = root.item(i, 0)
            if item and item.data(Qt.UserRole) == NOTES_ROOT_DATA:
                root.removeRow(i)
                break
        root.appendRow([self.notes_builder.build_node()])

    def notes_root_item(self):
        for i in range(self.model.rowCount()):
            item = self.model.item(i, 0)
            if item and item.data(Qt.UserRole) == NOTES_ROOT_DATA:
                return item
        return None

    def _note_from_index(self, index: QModelIndex):
        """Note из индекса (поднимаясь к корню) или None."""
        if not index.isValid():
            return None
        item = self.model.itemFromIndex(index.siblingAtColumn(0) if index.column() != 0 else index)
        while item is not None:
            data = item.data(Qt.UserRole)
            if data == NOTES_ROOT_DATA:
                return None
            if isinstance(data, Note):
                return data
            item = item.parent()
        return None

    def _selected_note_item(self):
        """Возвращает (item, Note) для выбранного элемента заметок или (None, None)."""
        index = self.tree.currentIndex()
        if not index.isValid():
            return None, None
        item = self.model.itemFromIndex(index.siblingAtColumn(0) if index.column() != 0 else index)
        while item is not None:
            data = item.data(Qt.UserRole)
            if data == NOTES_ROOT_DATA:
                return item, None
            if isinstance(data, Note):
                return item, data
            item = item.parent()
        return None, None

    def _find_notes_item(self, note_id: int, parent=None):
        """Ищет элемент дерева с Note.id == note_id (рекурсивно)."""
        parent = parent if parent is not None else self.notes_root_item()
        if parent is None:
            return None
        for i in range(parent.rowCount()):
            item = parent.child(i, 0)
            if item is None:
                continue
            data = item.data(Qt.UserRole)
            if isinstance(data, Note) and data.id == note_id:
                return item
            found = self._find_notes_item(note_id, parent=item)
            if found is not None:
                return found
        return None

    def _save_note_image(self, image) -> str:
        """Сохранить вставленную из буфера картинку и вернуть placeholder (md).

        Файл кладётся рядом с notes.db: <db_dir>/images/note_<id>/img_<ts>.png.
        Preview-движок md рендерит placeholder как изображение.
        """
        if self.notes_manager is None or self._active_note_id is None:
            return ""
        try:
            db_dir = self.notes_manager.db_path.parent
            img_dir = db_dir / "notes_images" / f"note_{self._active_note_id}"
            img_dir.mkdir(parents=True, exist_ok=True)
            fname = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path = img_dir / fname
            image.save(str(path), "PNG")
            return f"![{fname}]({path.as_posix()})"
        except Exception as e:
            print(f"Не удалось сохранить картинку: {e}")
            return ""

    def _switch_focus(self):
        """Ctrl+Tab: переключение фокуса между деревом и панелью заметок."""
        if self.notes_manager is None:
            return
        if self.notes_panel.isHidden():
            return
        if self.tree.hasFocus() or self.splitter.hasFocus():
            self.notes_panel.focus_editor()
        else:
            self.tree.setFocus()

    # ── выбор заметки → preview в панели ─────────────────────────────
    def _show_notes_panel(self):
        """Показать панель заметок; если она была скрыта — пере-применить долю.

        QSplitter схлопывает скрытый ребёнок в 0, поэтому после hide() нужно
        снова выставить размеры ([notes] panel_width_percent из launcher.toml).
        Если панель уже видна (пользователь сам перетащил разделитель) —
        размеры не трогаем.
        """
        was_hidden = self.notes_panel.isHidden()
        self.notes_panel.show()
        if was_hidden:
            percent = max(20, min(95, int(NOTES_PANEL_WIDTH_PERCENT)))
            total = max(self.splitter.width(), 800)
            self.splitter.setSizes([int(total * (100 - percent) / 100), int(total * percent / 100)])

    def _on_notes_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        self._save_current_note()
        # Каталог файлов может держать панель в режиме правки — сохраняем его файл
        # ДО того, как панель переключится на заметку.
        save_file = getattr(self, "_save_active_file", None)
        if save_file is not None:
            save_file()
        note = self._note_from_index(current)
        if note is not None and not note.is_folder:
            self._active_note_id = note.id
            self.notes_panel.show_note(note)
            self._show_notes_panel()
        else:
            # папка/корень/не-заметки — панель скрываем, если её не занял каталог
            self._active_note_id = None
            if not self._catalog_wants_panel():
                self.notes_panel.hide()

    def _notes_wants_panel(self) -> bool:
        """True, если активна заметка (панель показывает заметку, не каталог)."""
        return self._active_note_id is not None

    def _catalog_wants_panel(self) -> bool:
        """True, если текущая выборка — файл каталога (панель покажет CatalogMixin)."""
        take = getattr(self, "_catalog_take_panel", None)
        return bool(take and take())

    def _save_current_note(self):
        """Сохранить текст и позицию курсора активной заметки (если изменились).

        Best-effort: ошибка БД не должна ронять closeEvent/переключение.
        """
        if self.notes_manager is None or self._active_note_id is None:
            return
        try:
            note = self.notes_manager.get(self._active_note_id)
            if note is None:
                return
            text = self.notes_panel.get_text()
            caret = self.notes_panel.current_caret() if self.notes_panel.is_edit_mode() else note.caret
            if text != note.note or caret != note.caret:
                self.notes_manager.update(note.id, note=text, caret=caret)
        except Exception as e:
            print(f"Не удалось сохранить заметку: {e}")

    def _toggle_notes_edit(self):
        """F4: preview ⇄ редактирование (позиция курсора — из БД / в БД)."""
        if self.notes_manager is None or self._active_note_id is None:
            return
        if self.notes_panel.is_edit_mode():
            self._save_current_note()
            self.notes_panel.enter_preview()
        else:
            note = self.notes_manager.get(self._active_note_id)
            if note is None or note.is_folder:
                return
            self.notes_panel.enter_edit(caret=note.caret if note else 0)
            self.notes_panel.focus_editor()

    # ── действия (кооперативные: вне узла заметок делегируем ShortcutsMixin) ──
    def handle_enter(self) -> bool:
        """Enter: заметка — показать preview; папка/корень — раскрыть.
        Вне узла заметок — super() → ShortcutsMixin (базы/процессы)."""
        item, note = self._selected_note_item()
        if item is None:
            return super().handle_enter()
        index = self.tree.currentIndex()
        if note is None or note.is_folder:
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
            return True
        self.open_note(note.id)
        return True

    def handle_delete(self) -> bool:
        """Del: заметку/папку — в корзину. Вне узла заметок — super() (базы/процессы)."""
        item, note = self._selected_note_item()
        if item is None or note is None:
            return super().handle_delete()
        self.notes_manager.delete_to_trash(note.id)
        self._active_note_id = None
        self.notes_panel.hide()
        self.ensure_notes_node()
        self.statusBar.showMessage(f"🗑 «{note.name}» — в корзину", 3000)
        return True

    def handle_f4(self) -> bool:
        """F4: в узле заметок — preview/редактирование заметки (папка/корень — съедаем).
        Вне узла заметок — super() → ShortcutsMixin → конфигуратор."""
        item, note = self._selected_note_item()
        if item is None:
            return super().handle_f4()
        if note is None or note.is_folder:
            return True
        self._toggle_notes_edit()
        return True

    # ── операции с заметками ─────────────────────────────────────────
    def open_note(self, note_id: int):
        """Выбрать заметку в дереве — в панели покажется её preview."""
        item = self._find_notes_item(note_id)
        if item is None:
            return
        index = item.index()
        self.tree.setCurrentIndex(index)
        self.tree.scrollTo(index)

    def _current_notes_parent_id(self) -> int:
        """Родитель для новой заметки: выбранная заметка/папка (вложение в неё)."""
        item, note = self._selected_note_item()
        if item is None or note is None:
            return 0
        return note.id

    def new_note(self):
        if self.notes_manager is None:
            return
        note_id = self.notes_manager.create("Новая заметка", pid=self._current_notes_parent_id(), type_=0)
        self.ensure_notes_node()
        self.open_note(note_id)
        # сразу в редактирование, курсор в начало
        self._toggle_notes_edit()

    def new_folder(self):
        if self.notes_manager is None:
            return
        folder_id = self.notes_manager.create("Новая папка", pid=self._current_notes_parent_id(), type_=1)
        self.ensure_notes_node()
        item = self._find_notes_item(folder_id)
        if item is not None:
            self.tree.setCurrentIndex(item.index())  # вернуть выбор (панель скроется)
        self.statusBar.showMessage("📁 Папка создана", 2000)

    def rename_selected(self):
        item, note = self._selected_note_item()
        if item is None or note is None:
            return
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Название:", text=note.name)
        if ok and new_name.strip():
            self.notes_manager.update(note.id, name=new_name.strip())
            self.ensure_notes_node()
            self.open_note(note.id)  # вернуть выбор, панель покажет preview

    # ── контекстное меню и даблклик ──────────────────────────────────
    def _on_notes_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        self.tree.setCurrentIndex(index)
        item, note = self._selected_note_item()
        if item is None:
            return

        menu = QMenu(self)
        if note is None or note.is_folder:
            menu.addAction("📝 Новая заметка", self.new_note)
            menu.addAction("📁 Новая папка", self.new_folder)
        if note is not None:
            if not note.is_folder:
                menu.addAction("📄 Открыть", lambda: self.open_note(note.id))
                menu.addSeparator()
                menu.addAction("📝 Дочерняя заметка", self.new_note)
                menu.addAction("📁 Дочерняя папка", self.new_folder)
                menu.addSeparator()
            menu.addAction("✏️ Переименовать", self.rename_selected)
            menu.addAction("🗑 В корзину", self.handle_delete)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _on_notes_double_clicked(self, index):
        note = self._note_from_index(index)
        if note is not None and not note.is_folder:
            self.open_note(note.id)
