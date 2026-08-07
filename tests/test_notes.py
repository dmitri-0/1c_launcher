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


def test_update_caret_roundtrip(tmp_path):
    """Позиция курсора хранится в БД и восстанавливается."""
    mgr = NotesManager(tmp_path / "notes.db")
    try:
        note_id = mgr.create("Заметка", "текст")
        assert mgr.get(note_id).caret == 0
        mgr.update(note_id, caret=7)
        assert mgr.get(note_id).caret == 7
        mgr.update(note_id, note="новый текст", caret=3)
        note = mgr.get(note_id)
        assert note.note == "новый текст"
        assert note.caret == 3
    finally:
        mgr.close()


def test_migration_adds_caret_column(tmp_path):
    """Старая БД (без колонки caret) при открытии мигрируется."""
    import sqlite3

    path = tmp_path / "notes.db"
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE notes(id INTEGER PRIMARY KEY AUTOINCREMENT, pid INTEGER NOT NULL DEFAULT 0,"
        " name TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', pos INTEGER NOT NULL DEFAULT 0,"
        " created TEXT NOT NULL DEFAULT '', modified TEXT NOT NULL DEFAULT '',"
        " trash INTEGER NOT NULL DEFAULT 0, type INTEGER NOT NULL DEFAULT 0)"
    )
    con.commit()
    con.close()

    mgr = NotesManager(path)
    try:
        cols = [row[1] for row in mgr._conn.execute("PRAGMA table_info(notes)").fetchall()]
        assert "caret" in cols
        note_id = mgr.create("После миграции")
        assert mgr.get(note_id).caret == 0
    finally:
        mgr.close()


# ── панель preview/редактирования ───────────────────────────────────
def test_notes_panel_preview_default_and_edit(qt_app):
    from notes.notes_panel import NotesPanel

    raw = "# Заголовок\nтекст"
    panel = NotesPanel()
    note = Note(id=1, pid=0, name="Заметка.md", note=raw, pos=0,
                created="", modified="", trash=0, type=0, caret=5)
    panel.show_note(note)
    assert panel.is_edit_mode() is False          # по умолчанию — preview
    assert panel.body.isReadOnly() is True
    assert panel.get_text() == raw                # сырой текст не теряется

    panel.enter_edit(caret=5)
    assert panel.is_edit_mode() is True
    assert panel.body.isReadOnly() is False
    assert panel.body.textCursor().position() == 5  # позиция курсора восстановлена

    panel.body.insertPlainText("X")               # вставка в позицию курсора (5)
    expected = raw[:5] + "X" + raw[5:]
    assert panel.get_text() == expected
    assert panel.current_caret() == 6

    panel.enter_preview()
    assert panel.get_text() == expected           # текст сохранился после выхода из режима
    assert panel.body.isReadOnly() is True


def test_notes_panel_switch_note_while_editing(qt_app):
    """Регрессия: переключение заметки во время редактирования не должно
    заносить текст старой заметки в новую (show_note выходит из режима правки)."""
    from notes.notes_panel import NotesPanel

    panel = NotesPanel()
    note_a = Note(id=1, pid=0, name="A", note="текст A", pos=0,
                  created="", modified="", trash=0, type=0, caret=0)
    note_b = Note(id=2, pid=0, name="B", note="текст B", pos=1,
                  created="", modified="", trash=0, type=0, caret=0)

    panel.show_note(note_a)
    panel.enter_edit(caret=0)
    panel.body.setPlainText("отредактировано A")   # правим A

    panel.show_note(note_b)                        # переключаемся на B
    assert panel.is_edit_mode() is False           # вышли из режима правки
    assert panel.get_text() == "текст B"           # НЕ текст A
    assert panel.title_label.text() == "B"


def test_notes_panel_plain_format_fallback(qt_app):
    from notes.notes_panel import NotesPanel

    panel = NotesPanel()
    note = Note(id=2, pid=0, name="Просто заметка", note="без разметки", pos=0,
                created="", modified="", trash=0, type=0, caret=0)
    panel.show_note(note)
    assert panel.get_text() == "без разметки"
    assert panel.is_edit_mode() is False


def test_notes_handlers_delegate_outside_notes_node():
    """Регрессия: NotesMixin (первый в MRO TreeWindow) не должен съедать
    Enter/F4/Del для баз — вне узла заметок делегирует super() (ShortcutsMixin)."""
    from gui.mixins.notes_mixin import NotesMixin

    calls = []

    class _Base:
        def handle_enter(self):
            calls.append("enter")

        def handle_delete(self):
            calls.append("delete")

        def handle_f4(self):
            calls.append("f4")

    class _FakeTree:
        def currentIndex(self):
            return object()

        def isExpanded(self, index):
            return False

        def setExpanded(self, index, expand):
            calls.append("expand")

    class _Stub(NotesMixin, _Base):
        def __init__(self):
            self._sel = (None, None)
            self._tree = _FakeTree()

        def _selected_note_item(self):
            return self._sel

        @property
        def tree(self):
            return self._tree

    s = _Stub()

    # вне узла заметок (база/процесс) → делегирование ShortcutsMixin-логике
    s.handle_enter()
    s.handle_delete()
    s.handle_f4()
    assert calls == ["enter", "delete", "f4"]

    # в узле заметок: папка — раскрытие, делегирования нет
    s._sel = (object(), Note(id=1, pid=0, name="Папка", note="", pos=0,
                             created="", modified="", trash=0, type=1))
    calls.clear()
    s.handle_enter()
    assert calls == ["expand"]
    calls.clear()
    s.handle_f4()          # папка — съедаем F4, но не редактируем
    assert calls == []


def test_note_under_note_builds_tree(tmp_path):
    """Заметки можно вкладывать в заметки — дерево строится по pid независимо от type."""
    from PySide6.QtGui import QStandardItemModel
    from notes.notes_tree_builder import NotesTreeBuilder

    mgr = NotesManager(tmp_path / "notes.db")
    try:
        parent_id = mgr.create("Родитель", "текст родителя", type_=0)   # заметка
        mgr.create("Ребёнок", pid=parent_id, type_=0)                   # вложенная заметка
        node = NotesTreeBuilder(QStandardItemModel(), mgr).build_node()
        assert node.rowCount() == 1
        parent_item = node.child(0, 0)
        assert parent_item.text() == "Родитель"
        assert parent_item.child(0, 0).text() == "Ребёнок"
    finally:
        mgr.close()


def test_config_notes_panel_width():
    import config

    settings = config.load_settings(config.find_config_file())
    percent = config.NOTES_PANEL_WIDTH_PERCENT
    assert percent == settings["notes"].get("panel_width_percent", 80)


# ── движки рендеринга ───────────────────────────────────────────────
def test_engines_detect_and_fallback():
    from notes.engines import detect_engine, get_engine
    from notes.engines.plain_engine import PlainTextEngine
    from notes.engines.md_engine import MarkdownEngine

    assert detect_engine("todo.md", "текст") == MarkdownEngine.name
    assert detect_engine("Заметка", "# Заголовок") == MarkdownEngine.name
    assert detect_engine("Заметка", "просто текст") == PlainTextEngine.name
    assert isinstance(get_engine("md"), MarkdownEngine)
    assert isinstance(get_engine("неизвестный"), PlainTextEngine)   # fallback
    assert isinstance(get_engine(""), PlainTextEngine)
    assert get_engine("md").supports_editing() is True


def test_engines_render(qt_app):
    from notes.engines import get_engine
    from PySide6.QtWidgets import QTextEdit

    widget = QTextEdit()
    get_engine("plain").render(widget, "просто текст", "x")
    assert widget.toPlainText() == "просто текст"
    get_engine("md").render(widget, "# Заголовок", "x.md")
    assert "Заголовок" in widget.toPlainText()


def test_engines_json_bsl_image_detection():
    from notes.engines import detect_engine, get_engine
    from notes.engines.bsl_engine import BslEngine
    from notes.engines.json_engine import JsonEngine
    from notes.engines.image_engine import ImageEngine

    assert detect_engine("config.json", "") == JsonEngine.name
    assert detect_engine("module.bsl", "") == BslEngine.name
    assert detect_engine("photo.png", "") == ImageEngine.name
    assert detect_engine("photo.JPG", "") == ImageEngine.name
    assert detect_engine("data.os", "") == BslEngine.name
    assert detect_engine("readme.md", "") == "md"
    assert isinstance(get_engine("json"), JsonEngine)
    assert isinstance(get_engine("bsl"), BslEngine)
    assert isinstance(get_engine("image"), ImageEngine)
    assert get_engine("image").supports_editing() is False


def test_bsl_highlighter_dark_theme(qt_app):
    """BslHighlighter не падает на типичном модуле 1С (тёмная палитра)."""
    from PySide6.QtGui import QTextDocument
    from notes.engines.highlighters import BslHighlighter

    doc = QTextDocument()
    hl = BslHighlighter(doc)
    doc.setPlainText(
        "&НаКлиенте\n"
        "Процедура Тест()\n"
        "    // комментарий\n"
        "    Стр = \"привет\";\n"
        "    Если Истина Тогда Возврат; КонецЕсли;\n"
        "КонецПроцедуры\n"
    )
    hl.rehighlight()
    assert doc.characterCount() > 0  # подсветка отработала без ошибок


def test_notes_panel_json_bsl_highlighting(qt_app):
    """Панель включает подсветку для bsl/json и отключает для прочих движков."""
    from notes.notes_panel import NotesPanel

    panel = NotesPanel()
    bsl = Note(id=1, pid=0, name="module.bsl", note="Процедура Тест()\nКонецПроцедуры", pos=0,
               created="", modified="", trash=0, type=0, caret=0)
    panel.show_note(bsl)
    assert panel._highlighter is not None          # bsl → подсветка включена
    md = Note(id=2, pid=0, name="x.md", note="# Заголовок", pos=1,
              created="", modified="", trash=0, type=0, caret=0)
    panel.show_note(md)
    assert panel._highlighter is None              # md → подсветка отключена


def test_config_notes_zoom_default():
    import config

    settings = config.load_settings(config.find_config_file())
    assert config.NOTES_ZOOM_DEFAULT == settings["notes"].get("zoom_default", 0)


def test_notes_panel_zoom_buttons(qt_app):
    from notes.notes_panel import NotesPanel

    panel = NotesPanel()
    note = Note(id=1, pid=0, name="Z", note="текст", pos=0,
                created="", modified="", trash=0, type=0, caret=0)
    panel.show_note(note)
    base = panel._base_pt
    assert panel._zoom == 0

    panel.change_zoom(1)
    assert panel._zoom == 1
    assert panel.body.font().pointSizeF() > base          # шрифт вырос

    panel.change_zoom(-2)
    assert panel._zoom == -1                               # 1 - 2 = -1 (ступени непрерывны)
    panel.change_zoom(0, reset=True)
    assert panel._zoom == 0
    assert panel.body.font().pointSizeF() == base          # сброс вернул базовый размер

    # в редактировании zoom тоже меняет шрифт, текст не теряется
    panel.enter_edit(caret=0)
    panel.change_zoom(2)
    assert panel.is_edit_mode()
    assert panel.get_text() == "текст"


def test_notes_panel_image_paste_placeholder(qt_app):
    from notes.notes_panel import NotesPanel
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QMimeData

    saved = []
    panel = NotesPanel()
    panel.image_handler = lambda img: saved.append(img) or "[IMG]"
    panel.enter_edit(caret=0)
    mime = QMimeData()
    mime.setImageData(QImage(8, 8, QImage.Format.Format_ARGB32))
    panel.body.insertFromMimeData(mime)
    assert saved, "image_handler должен был вызваться"
    assert panel.body.toPlainText() == "[IMG]"             # placeholder вместо картинки


def test_mixin_image_handler_wired():
    from gui.mixins.notes_mixin import NotesMixin

    assert hasattr(NotesMixin, "_save_note_image")
    assert hasattr(NotesMixin, "_switch_focus")


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
    assert hasattr(TreeWindow, "_toggle_notes_edit")
    assert hasattr(TreeWindow, "_save_current_note")
    assert hasattr(TreeWindow, "handle_f4")


def test_config_notes_path_default():
    import config

    # Самосогласованность: константа == значению из найденного launcher.toml
    # (устойчиво к тому, что оператор пропишет свой путь в [notes] path)
    settings = config.load_settings(config.find_config_file())
    assert config.NOTES_PATH == settings["notes"].get("path", "")
