"""Тесты менеджера заметок (SQLite) и интеграции «📝 Заметки» в лаунчер."""

from pathlib import Path

from notes.notes_manager import NotesManager, Note, guess_note_format


# ── формат (preview) ──────────────────────────────────────────────────
def test_guess_format_md_by_extension():
    assert guess_note_format("todo.md", "some text") == "md"
    assert guess_note_format("README.markdown", "text") == "md"


def test_guess_format_md_by_markers():
    assert guess_note_format("Заметка", "# Заголовок\nтекст") == "md"
    assert guess_note_format("Заметка", "- пункт списка") == "md"
    assert guess_note_format("Заметка", "**жирный** текст") == "md"
    assert guess_note_format("Заметка", "> цитата") == "md"


def test_guess_format_plain_fallback():
    # не распознан формат → plain text (пока движок понимает только md)
    assert guess_note_format("Заметка", "просто текст без разметки") == "plain"
    assert guess_note_format("Заметка", "") == "plain"


# ── SQLite-хранилище ─────────────────────────────────────────────────
def test_create_and_load(tmp_path):
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        note_id = mgr.create("Первая", "текст заметки")
        assert note_id > 0
        note = mgr.get(note_id)
        assert note.name == "Первая"
        assert note.note == "текст заметки"
        assert note.type == 0
        assert note.trash == 0
        assert mgr.load_all() == [note]
    finally:
        mgr.close()


def test_tree_and_folders(tmp_path):
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        folder_id = mgr.create("Папка", type_=1)
        child_id = mgr.create("Внутри", pid=folder_id)
        root_note_id = mgr.create("Отдельная")
        assert mgr.get(folder_id).is_folder
        assert mgr.get(child_id).pid == folder_id
        assert {n.id for n in mgr.load_all()} == {folder_id, child_id, root_note_id}
    finally:
        mgr.close()


def test_update_rename_and_text(tmp_path):
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        note_id = mgr.create("Имя")
        mgr.update(note_id, name="Новое имя")
        mgr.update(note_id, note="новый текст")
        note = mgr.get(note_id)
        assert note.name == "Новое имя"
        assert note.note == "новый текст"
        assert note.modified >= note.created
    finally:
        mgr.close()


def test_trash_hides_note(tmp_path):
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        note_id = mgr.create("Скрыть")
        assert mgr.load_all()
        mgr.delete_to_trash(note_id)
        assert mgr.load_all() == []            # из дерева скрыта
        assert mgr.get(note_id).trash == 1     # но не удалена
        mgr.restore(note_id)
        assert len(mgr.load_all()) == 1
    finally:
        mgr.close()


def test_trash_folder_cascades_to_children(tmp_path):
    """Удаление папки в корзину не осиротляет детей: они тоже получают trash=1."""
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        folder_id = mgr.create("Папка", type_=1)
        child_id = mgr.create("Дочка", pid=folder_id)
        mgr.delete_to_trash(folder_id)
        assert mgr.get(folder_id).trash == 1
        assert mgr.get(child_id).trash == 1
    finally:
        mgr.close()


def test_purge_subtree(tmp_path):
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        folder_id = mgr.create("Папка", type_=1)
        child_id = mgr.create("Дочка", pid=folder_id)
        other_id = mgr.create("Другая")
        mgr.purge(folder_id)
        remaining = {n.id for n in mgr.load_all(include_trash=True)}
        assert remaining == {other_id}
        assert mgr.get(child_id) is None
    finally:
        mgr.close()


def test_schema_recreated(tmp_path):
    """Повторное открытие той же БД не ломает схему."""
    path = tmp_path / "notes.db"
    NotesManager(path).close()
    mgr = NotesManager(path)
    try:
        note_id = mgr.create("После переоткрытия")
        assert mgr.get(note_id).name == "После переоткрытия"
    finally:
        mgr.close()


# ── интеграция в GUI ─────────────────────────────────────────────────
def test_builder_builds_tree_from_db(tmp_path):
    from PySide6.QtGui import QStandardItemModel
    from notes.notes_tree_builder import NotesTreeBuilder

    mgr = NotesManager(tmp_path / "notes.db")
    try:
        folder_id = mgr.create("Папка", type_=1)
        mgr.create("Внутри", pid=folder_id)
        mgr.create("Отдельная")
        node = NotesTreeBuilder(QStandardItemModel(), mgr).build_node()
        assert node.rowCount() == 2                       # папка выше заметки
        assert node.child(0, 0).text() == "Папка"
        assert node.child(0, 0).child(0, 0).text() == "Внутри"
        assert node.child(1, 0).text() == "Отдельная"
    finally:
        mgr.close()


def test_ensure_notes_node_idempotent(tmp_path):
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtCore import Qt
    from notes.notes_tree_builder import NotesTreeBuilder, NOTES_ROOT_DATA
    from gui.mixins.notes_mixin import NotesMixin

    class Stub(NotesMixin):
        def __init__(self, model, mgr):
            self.model = model
            self.notes_manager = mgr
            self.notes_builder = NotesTreeBuilder(model, mgr)

    model = QStandardItemModel()
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        mgr.create("Заметка")
        stub = Stub(model, mgr)
        stub.ensure_notes_node()
        rows_first = model.rowCount()
        assert rows_first == 1
        stub.ensure_notes_node()
        assert model.rowCount() == rows_first            # повторный вызов не плодит узлы
        assert model.item(0, 0).data(Qt.UserRole) == NOTES_ROOT_DATA
    finally:
        mgr.close()


def test_dialog_preview_roundtrip(qt_app):
    """F4-preview не теряет сырой текст: get_data всегда возвращает plain."""
    from notes.notes_dialog import NotesDialog

    raw = "# Заголовок\n**жирный** текст"
    dlg = NotesDialog(title="Заметка.md", text=raw)
    dlg.toggle_preview()                                  # → preview (markdown)
    assert dlg.get_data() == ("Заметка.md", raw)
    dlg.toggle_preview()                                  # → редактирование
    assert dlg.get_data() == ("Заметка.md", raw)


def test_notes_mixin_registered_in_tree_window():
    from gui.tree_window import TreeWindow
    from gui.mixins import NotesMixin

    assert NotesMixin in TreeWindow.__mro__
    assert hasattr(TreeWindow, "ensure_notes_node")
    assert hasattr(TreeWindow, "handle_enter")
    assert hasattr(TreeWindow, "init_notes")


def test_config_notes_path_default():
    import config

    # Самосогласованность: константа == значению из найденного launcher.toml
    # (устойчиво к тому, что оператор пропишет свой путь в [notes] path)
    settings = config.load_settings(config.find_config_file())
    assert config.NOTES_PATH == settings["notes"].get("path", "")
