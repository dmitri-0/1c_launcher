"""Миксин «Заметки»: узел в дереве + панель preview/редактирования.

Поток:
- навигация по дереву заметок → в правой панели сразу показывается preview
  активной заметки (режим по умолчанию);
- F4 → режим редактирования (курсор в тексте, позиция запоминается в БД);
- F4 ещё раз / переключение заметки / закрытие окна → текст и позиция курсора
  сохраняются в notes.db.
"""

from PySide6.QtWidgets import QMenu, QInputDialog
from PySide6.QtCore import Qt, QModelIndex

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

    # ── выбор заметки → preview в панели ─────────────────────────────
    def _on_notes_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        self._save_current_note()
        note = self._note_from_index(current)
        if note is not None and not note.is_folder:
            self._active_note_id = note.id
            self.notes_panel.show_note(note)
            self.notes_panel.show()
        else:
            # папка/корень/не-заметки — панель скрываем
            self._active_note_id = None
            self.notes_panel.hide()

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

    def handle_f4(self) -> bool:
        """F4: в узле заметок — переключить preview/редактирование заметки.

        Возвращает True, если F4 «съеден» узлом заметок (не должен открыть
        конфигуратор). Папка/корень заметок — F4 не редактирует, но и не
        передаётся дальше.
        """
        item, note = self._selected_note_item()
        if item is None:
            return False
        if note is None or note.is_folder:
            return True
        self._toggle_notes_edit()
        return True

    # ── действия (возвращают True, если обработали) ──────────────────
    def handle_enter(self) -> bool:
        """Enter: заметка — показать preview/выбрать, папка/корень — раскрыть."""
        item, note = self._selected_note_item()
        if item is None:
            return False
        index = self.tree.currentIndex()
        if note is None or note.is_folder:
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
            return True
        self.open_note(note.id)
        return True

    def handle_delete(self) -> bool:
        """Del: заметку/папку — в корзину."""
        item, note = self._selected_note_item()
        if item is None or note is None:
            return False
        self.notes_manager.delete_to_trash(note.id)
        self._active_note_id = None
        self.notes_panel.hide()
        self.ensure_notes_node()
        self.statusBar.showMessage(f"🗑 «{note.name}» — в корзину", 3000)
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
        """Родитель для новой заметки: выбранная папка или родитель выбранной заметки."""
        item, note = self._selected_note_item()
        if item is None or note is None:
            return 0
        return note.id if note.is_folder else note.pid

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
            menu.addAction("✏️ Переименовать", self.rename_selected)
            menu.addAction("🗑 В корзину", self.handle_delete)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _on_notes_double_clicked(self, index):
        note = self._note_from_index(index)
        if note is not None and not note.is_folder:
            self.open_note(note.id)
