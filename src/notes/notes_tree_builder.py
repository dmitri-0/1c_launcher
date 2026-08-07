"""Построение узла «📝 Заметки» в дереве лаунчера.

Корневой узел помечается константой NOTES_ROOT_DATA (Qt.UserRole), элементы —
объектами Note — так миксин отличает заметки от баз/процессов.
"""

from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt

from notes.notes_manager import NotesManager, Note

NOTES_ROOT_DATA = "notes:root"  # маркер корневого узла заметок


class NotesTreeBuilder:
    NODE_NAME = "📝 Заметки"

    def __init__(self, model, manager: NotesManager):
        self.model = model
        self.manager = manager

    def build_node(self) -> QStandardItem:
        """Собирает корневой узел «📝 Заметки» со всем деревом из БД."""
        root = QStandardItem(self.NODE_NAME)
        root.setEditable(False)
        root.setData(NOTES_ROOT_DATA, Qt.UserRole)

        notes = self.manager.load_all()
        by_pid: dict = {}
        for note in notes:
            by_pid.setdefault(note.pid, []).append(note)

        for note in self._sorted(by_pid.get(0, [])):
            root.appendRow(self._build_row(note, by_pid))
        return root

    def _build_row(self, note: Note, by_pid: dict) -> QStandardItem:
        item = QStandardItem(note.name)
        item.setEditable(False)
        item.setData(note, Qt.UserRole)
        for child in self._sorted(by_pid.get(note.id, [])):
            item.appendRow(self._build_row(child, by_pid))
        return item

    @staticmethod
    def _sorted(notes) -> list:
        # Папки выше заметок, внутри — по (pos, name)
        return sorted(notes, key=lambda n: (0 if n.is_folder else 1, n.pos, n.name))
