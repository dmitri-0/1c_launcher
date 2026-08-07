"""Тесты каталога файлов (узел «📂 Каталог») и размещения данных рядом с exe."""

from pathlib import Path

from catalog.catalog_manager import CatalogManager, parse_mask


def _make_tree(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.md").write_bytes("# Заголовок\nтекст".encode("utf-8"))
    (tmp_path / "b.json").write_bytes('{"x": 1}'.encode("utf-8"))
    (tmp_path / "sub" / "c.bsl").write_bytes("Процедура Тест()\nКонецПроцедуры".encode("cp1251"))
    (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)  # бинарный
    return tmp_path


def test_parse_mask():
    assert parse_mask(".md, .json") == {".md", ".json"}
    assert parse_mask("") == set()


def test_scan_with_mask(tmp_path):
    root = _make_tree(tmp_path)
    mgr = CatalogManager(str(root), mask=".md,.json")
    files = mgr.scan()
    names = {f.name for f in files if not f.is_dir}
    assert names == {"a.md", "b.json"}          # c.bsl и img.png отфильтрованы
    assert {f.name for f in files if f.is_dir} == {"sub"}


def test_scan_all_files(tmp_path):
    root = _make_tree(tmp_path)
    mgr = CatalogManager(str(root))
    names = {f.name for f in mgr.scan() if not f.is_dir}
    assert names == {"a.md", "b.json", "c.bsl", "img.png"}


def test_read_text_and_binary(tmp_path):
    root = _make_tree(tmp_path)
    mgr = CatalogManager(str(root))
    assert mgr.read_text(root / "a.md") == "# Заголовок\nтекст"
    assert "КонецПроцедуры" in mgr.read_text(root / "sub" / "c.bsl")  # cp1251
    assert mgr.read_text(root / "img.png") is None                    # бинарный


def test_write_text_preserves_encoding(tmp_path):
    """Сохранение cp1251-файла не перекодирует его в utf-8."""
    root = _make_tree(tmp_path)
    mgr = CatalogManager(str(root))
    bsl = root / "sub" / "c.bsl"

    result = mgr.read_text_with_encoding(bsl)
    assert result is not None
    text, enc = result
    assert enc == "cp1251"

    mgr.write_text(bsl, text + "\nДобавлено", encoding=enc)
    reread = mgr.read_text_with_encoding(bsl)
    assert reread is not None
    assert reread[0].endswith("Добавлено")
    assert reread[1] == "cp1251"
    # байты файла остались невалидным utf-8 → кодировка не изменилась
    try:
        bsl.read_bytes().decode("utf-8")
        utf8_ok = True
    except UnicodeDecodeError:
        utf8_ok = False
    assert utf8_ok is False


def test_write_text_roundtrip(tmp_path):
    root = _make_tree(tmp_path)
    mgr = CatalogManager(str(root))
    target = root / "b.json"
    mgr.write_text(target, '{"y": 2}')
    assert mgr.read_text(target) == '{"y": 2}'


def test_unconfigured_manager():
    mgr = CatalogManager("")
    assert mgr.is_configured() is False
    assert mgr.scan() == []


def test_catalog_builder_builds_node(tmp_path):
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtCore import Qt
    from catalog.catalog_manager import CatalogManager
    from catalog.catalog_tree_builder import CatalogTreeBuilder, CATALOG_ROOT_DATA
    from catalog.catalog_manager import CatalogFile

    root = _make_tree(tmp_path)
    builder = CatalogTreeBuilder(QStandardItemModel(), CatalogManager(str(root)))
    node = builder.build_node()
    assert node.data(Qt.UserRole) == CATALOG_ROOT_DATA
    names = [node.child(i, 0).text() for i in range(node.rowCount())]
    # папка «sub» выше файлов, внутри — файлы по алфавиту
    assert names[0] == "sub"
    assert set(names[1:]) == {"a.md", "b.json", "img.png"}
    sub = node.child(0, 0)
    assert sub.child(0, 0).text() == "c.bsl"
    assert isinstance(sub.data(Qt.UserRole), CatalogFile)


def test_catalog_mixin_registered_in_tree_window():
    from gui.tree_window import TreeWindow
    from gui.mixins import CatalogMixin

    assert CatalogMixin in TreeWindow.__mro__
    assert CatalogMixin.__mro__.index(CatalogMixin) < TreeWindow.__mro__.index(
        __import__("gui.mixins", fromlist=["NotesMixin"]).NotesMixin
    )  # CatalogMixin стоит ПЕРВЫМ — перехватывает Enter/F4/Del раньше заметок
    assert hasattr(TreeWindow, "ensure_catalog_node")
    assert hasattr(TreeWindow, "_save_active_file")


def test_catalog_handlers_delegate_outside_catalog():
    """Вне узла каталога CatalogMixin делегирует super() (заметки/базы)."""
    from gui.mixins.catalog_mixin import CatalogMixin

    calls = []

    class _Base:
        def handle_enter(self):
            calls.append("enter")

        def handle_f4(self):
            calls.append("f4")

        def handle_delete(self):
            calls.append("delete")

    class _Stub(CatalogMixin, _Base):
        def __init__(self):
            self._catalog_file = None
            self._tree = _FakeTree()

        def _catalog_file_from_index(self, index):
            return self._catalog_file

        @property
        def tree(self):
            return self._tree

        @property
        def notes_panel(self):
            return _FakePanel()

    class _FakeTree:
        def currentIndex(self):
            return object()

        def isExpanded(self, index):
            return False

        def setExpanded(self, index, expand):
            calls.append("expand")

    class _FakePanel:
        def is_edit_mode(self):
            return False

        def enter_edit(self, caret=0):
            pass

    s = _Stub()
    s.handle_enter()
    s.handle_f4()
    s.handle_delete()
    assert calls == ["enter", "f4", "delete"]   # вне каталога — делегирование


def test_notes_db_default_in_appdata(monkeypatch):
    """notes.db по умолчанию лежит в %APPDATA%\\1c_launcher — вне каталога исходников
    (одинаково для скриптовой и exe-версии, переопределяется в launcher.toml)."""
    import os
    from notes import notes_manager

    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    assert notes_manager._default_db_path() == Path("C:/Users/test/AppData/Roaming/1c_launcher/notes.db")


def test_notes_images_in_db(tmp_path):
    """Вставленные картинки хранятся в БД (blob) — портативно, без файлов на диске."""
    from notes.notes_manager import NotesManager

    mgr = NotesManager(tmp_path / "notes.db")
    try:
        note_id = mgr.create("Заметка")
        image_id = mgr.add_image(note_id, "img.png", b"\x89PNG-fake-bytes")
        assert image_id > 0
        assert mgr.get_image(image_id) == b"\x89PNG-fake-bytes"
        assert mgr.get_image(99999) is None
    finally:
        mgr.close()


def test_purge_removes_images(tmp_path):
    """purge удаляет и blob-картинки удалённых заметок (нет сирот в images)."""
    from notes.notes_manager import NotesManager

    mgr = NotesManager(tmp_path / "notes.db")
    try:
        nid = mgr.create("Заметка")
        img = mgr.add_image(nid, "i.png", b"\x89PNG-fake")
        assert mgr.get_image(img) is not None
        mgr.purge(nid)
        assert mgr.get_image(img) is None
    finally:
        mgr.close()


def test_migrate_legacy_db_to_appdata(monkeypatch, tmp_path):
    """Старая notes.db (с заметками) переносится в %APPDATA% один раз."""
    from notes import notes_manager
    from notes.notes_manager import NotesManager

    legacy = tmp_path / "legacy_notes.db"
    mgr = NotesManager(legacy)
    mgr.create("Старая заметка")
    mgr.close()
    target = tmp_path / "appdata" / "1c_launcher" / "notes.db"
    monkeypatch.setattr(notes_manager, "_legacy_db_candidates", lambda: [legacy])

    # target отсутствует → миграция
    assert notes_manager.migrate_legacy_db(target) is True
    assert target.exists()
    assert NotesManager(target).load_all()[0].name == "Старая заметка"
    NotesManager(target).close()

    # target уже есть и содержит заметки → повторно не трогаем
    assert notes_manager.migrate_legacy_db(target) is False

    # пустая legacy (0 заметок) — миграции нет
    empty = tmp_path / "empty.db"
    NotesManager(empty).close()
    target2 = tmp_path / "appdata" / "1c_launcher" / "notes2.db"
    monkeypatch.setattr(notes_manager, "_legacy_db_candidates", lambda: [empty])
    assert notes_manager.migrate_legacy_db(target2) is False
    assert not target2.exists()

    # источник не удаляется (копия-бэкап)
    assert legacy.exists()


def test_note_document_loads_image_from_db(qt_app):
    """NoteTextDocument достаёт blob из БД по URL noteimg:<id> (md-preview)."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument, QImage
    from notes.notes_document import NoteTextDocument
    from notes.notes_manager import NotesManager

    mgr = NotesManager(Path(__import__("tempfile").gettempdir()) / "notes_test_tmp.db")
    try:
        # реальный png: рисуем и сохраняем в QBuffer
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        QImage(4, 4, QImage.Format.Format_ARGB32).save(buf, "PNG")
        buf.close()
        image_id = mgr.add_image(1, "img.png", bytes(buf.data()))

        doc = NoteTextDocument()
        doc.loader = mgr.get_image
        result = doc.loadResource(QTextDocument.ImageResource, QUrl(f"noteimg:{image_id}"))
        assert result is not None
        assert isinstance(result, QImage)
        assert result.isNull() is False
        # неизвестный id → None (fallback)
        assert doc.loadResource(QTextDocument.ImageResource, QUrl("noteimg:99999")) is None
    finally:
        mgr.close()
        (Path(__import__("tempfile").gettempdir()) / "notes_test_tmp.db").unlink(missing_ok=True)

def test_path_caret_persistence(tmp_path):
    """Позиция курсора файла каталога сохраняется в meta БД заметок."""
    from notes.notes_manager import NotesManager

    mgr = NotesManager(tmp_path / "notes.db")
    try:
        assert mgr.get_path_caret(r"C:\work\module.bsl") == 0
        mgr.set_path_caret(r"C:\work\module.bsl", 123)
        assert mgr.get_path_caret(r"C:\work\module.bsl") == 123
        mgr.set_path_caret(r"C:\work\module.bsl", 0)  # 0 не сохраняется
        assert mgr.get_path_caret(r"C:\work\module.bsl") == 123
    finally:
        mgr.close()
