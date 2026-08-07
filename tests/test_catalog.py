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


def test_notes_db_default_next_to_exe_frozen(monkeypatch):
    """В сборке notes.db создаётся РЯДОМ С exe (динамические файлы — у бинарника)."""
    import sys
    from notes import notes_manager

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\dist\app\app.exe")
    assert notes_manager._default_db_path() == Path("C:/dist/app/notes.db")
