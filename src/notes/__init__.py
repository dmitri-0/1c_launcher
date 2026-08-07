"""Пакет «Заметки» лаунчера 1С.

Модель — как у FlashNote: дерево смежным списком (pid), папка = узел с детьми.
Тело заметки — plain text; Markdown-разметка рендерится в preview (F4).
"""

from .notes_manager import NotesManager, Note, guess_note_format
from .notes_dialog import NotesDialog
from .notes_tree_builder import NotesTreeBuilder, NOTES_ROOT_DATA

__all__ = [
    "NotesManager",
    "Note",
    "guess_note_format",
    "NotesDialog",
    "NotesTreeBuilder",
    "NOTES_ROOT_DATA",
]
