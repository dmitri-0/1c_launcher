"""Миксин «Заметки»: узел в дереве, редактор, контекстное меню, клавиши.

Интеграция:
- init_notes() — создаёт NotesManager и NotesTreeBuilder, вешает сигналы дерева;
- ensure_notes_node() — пересобирает корневой узел «📝 Заметки» (идемпотентно);
- load_bases() — кооперативный override: после перестройки дерева баз (модель
  очищается TreeBuilder.build_tree) узел заметок пересобирается;
- handle_enter() / handle_delete() — вызываются из ShortcutsMixin, возвращают True,
  если выборка была по узлу заметок.
"""

from PySide6.QtWidgets import QMenu, QInputDialog
from PySide6.QtCore import Qt

from notes.notes_manager import NotesManager, Note
from notes.notes_dialog import NotesDialog
from notes.notes_tree_builder import NotesTreeBuilder, NOTES_ROOT_DATA


class NotesMixin:
    """Интеграция менеджера заметок в главное окно."""

    def init_notes(self):
        self.notes_mixin = self  # короткий алиас для обращений из других миксинов
        self.notes_manager = None
        self.notes_builder = None
        try:
            self.notes_manager = NotesManager()
            self.notes_builder = NotesTreeBuilder(self.model, self.notes_manager)
            self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._on_notes_context_menu)
            self.tree.doubleClicked.connect(self._on_notes_double_clicked)
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

    def _selected_note_item(self):
        """Возвращает (item, Note) для выбранного элемента заметок или (None, None)."""
        index = self.tree.currentIndex()
        if not index.isValid():
            return None, None
        item = self.model.itemFromIndex(index)
        while item is not None:
            data = item.data(Qt.UserRole)
            if data == NOTES_ROOT_DATA:
                return item, None
            if isinstance(data, Note):
                return item, data
            item = item.parent()
        return None, None

    def _is_notes_selected(self) -> bool:
        return self._selected_note_item()[0] is not None

    # ── действия (возвращают True, если обработали) ──────────────────
    def handle_enter(self) -> bool:
        """Enter: заметка — открыть, папка/корень — раскрыть/свернуть."""
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
        self.ensure_notes_node()
        self.statusBar.showMessage(f"🗑 «{note.name}» — в корзину", 3000)
        return True

    # ── операции с заметками ─────────────────────────────────────────
    def open_note(self, note_id: int):
        if self.notes_manager is None:
            return
        note = self.notes_manager.get(note_id)
        if note is None:
            return
        dlg = NotesDialog(self, title=note.name, text=note.note, name=note.name)
        if dlg.exec() == NotesDialog.Accepted:
            title, text = dlg.get_data()
            self.notes_manager.update(note.id, name=title or note.name, note=text)
            self.ensure_notes_node()
            self.statusBar.showMessage(f"✅ Заметка «{title or note.name}» сохранена", 3000)

    def _current_notes_parent_id(self) -> int:
        """Родитель для новой заметки: выбранная папка или родитель выбранной заметки."""
        item, note = self._selected_note_item()
        if item is None or note is None:
            return 0
        return note.id if note.is_folder else note.pid

    def new_note(self):
        if self.notes_manager is None:
            return
        parent_id = self._current_notes_parent_id()
        note_id = self.notes_manager.create("Новая заметка", pid=parent_id, type_=0)
        self.ensure_notes_node()
        self.open_note(note_id)

    def new_folder(self):
        if self.notes_manager is None:
            return
        parent_id = self._current_notes_parent_id()
        self.notes_manager.create("Новая папка", pid=parent_id, type_=1)
        self.ensure_notes_node()
        self.statusBar.showMessage("📁 Папка создана", 2000)

    def rename_selected(self):
        item, note = self._selected_note_item()
        if item is None or note is None:
            return
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Название:", text=note.name)
        if ok and new_name.strip():
            self.notes_manager.update(note.id, name=new_name.strip())
            self.ensure_notes_node()

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
        item = self.model.itemFromIndex(index)
        if item is None:
            return
        data = item.data(Qt.UserRole)
        if isinstance(data, Note) and not data.is_folder:
            self.open_note(data.id)
