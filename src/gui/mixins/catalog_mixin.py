"""Миксин «Каталог»: узел «📂 Каталог», preview/редактирование файлов как заметок.

CatalogMixin стоит ПЕРВЫМ в MRO TreeWindow: его handle_enter/handle_f4/handle_delete
перехватывают выборку по узлу каталога и делегируют super() (→ NotesMixin →
ShortcutsMixin) вне каталога.

Панель заметок общая: файлы каталога показываются в ней через те же движки.
Текстовые файлы редактируются в панели (сохранение в файл), бинарные —
открываются внешним приложением (os.startfile).
"""

import os

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt, QModelIndex

from config import CATALOG_PATH, CATALOG_MASK
from catalog.catalog_manager import CatalogManager, CatalogFile
from catalog.catalog_tree_builder import CatalogTreeBuilder, CATALOG_ROOT_DATA
from notes.engines import detect_engine


class CatalogMixin:
    """Интеграция каталога файлов в главное окно."""

    def init_catalog(self):
        self.catalog_mixin = self
        self.catalog_manager = CatalogManager(CATALOG_PATH, CATALOG_MASK)
        self.catalog_builder = CatalogTreeBuilder(self.model, self.catalog_manager)
        self._active_catalog_path = None
        self._active_catalog_encoding = "utf-8"
        if self.catalog_manager.is_configured():
            self.tree.selectionModel().currentChanged.connect(self._on_catalog_selection_changed)
            self.tree.customContextMenuRequested.connect(self._on_catalog_context_menu)

    def load_bases(self):
        # Кооперативный override: BasesDataMixin перечитывает базы (модель очищается),
        # NotesMixin пересобирает «📝 Заметки», мы — «📂 Каталог».
        super().load_bases()
        self.ensure_catalog_node()

    # ── дерево ───────────────────────────────────────────────────────
    def ensure_catalog_node(self):
        """Пересобрать корневой узел «📂 Каталог» (если каталог настроен)."""
        if self.catalog_manager is None or not self.catalog_manager.is_configured():
            return
        root = self.model
        for i in range(root.rowCount()):
            item = root.item(i, 0)
            if item and item.data(Qt.UserRole) == CATALOG_ROOT_DATA:
                root.removeRow(i)
                break
        root.appendRow([self.catalog_builder.build_node()])

    def _catalog_file_from_index(self, index: QModelIndex):
        """CatalogFile из индекса (поднимаясь к корню) или None."""
        if not index.isValid():
            return None
        item = self.model.itemFromIndex(index.siblingAtColumn(0) if index.column() != 0 else index)
        while item is not None:
            data = item.data(Qt.UserRole)
            if data == CATALOG_ROOT_DATA:
                return None
            if isinstance(data, CatalogFile):
                return data
            item = item.parent()
        return None

    def _catalog_take_panel(self) -> bool:
        """True, если текущая выборка — файл каталога (панель покажем сами)."""
        f = self._catalog_file_from_index(self.tree.currentIndex())
        return f is not None and not f.is_dir

    # ── выбор файла → preview в панели ───────────────────────────────
    def _on_catalog_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        self._save_active_file()
        f = self._catalog_file_from_index(current)
        if f is not None and not f.is_dir:
            self._active_catalog_path = f.path
            engine_name = detect_engine(f.name, "")
            if engine_name == "image":
                # картинка: preview движком image (text = путь к файлу)
                self.notes_panel.show_content(f.name, str(f.path), engine_name="image")
            else:
                result = self.catalog_manager.read_text_with_encoding(f.path)
                if result is not None:
                    text, encoding = result
                    self._active_catalog_encoding = encoding
                    self.notes_panel.show_content(f.name, text)
                else:
                    text, encoding = "", "utf-8"
                    self._active_catalog_encoding = "utf-8"
                    self.notes_panel.show_content(f.name, text, binary=True)
            self._show_notes_panel()  # общий метод из NotesMixin
        else:
            self._active_catalog_path = None
            # папка/не-каталог: панель скрывает NotesMixin, если не активна заметка
            if not self._notes_wants_panel():
                self.notes_panel.hide()

    def _save_active_file(self):
        """Сохранить редактируемый файл каталога в ЕГО кодировке (best-effort)."""
        if self.catalog_manager is None or self._active_catalog_path is None:
            return
        try:
            if self.notes_panel.is_edit_mode():
                self.catalog_manager.write_text(
                    self._active_catalog_path,
                    self.notes_panel.get_text(),
                    encoding=self._active_catalog_encoding,
                )
        except Exception as e:
            print(f"Не удалось сохранить файл: {e}")

    def _open_external(self, path) -> None:
        """Открыть файл системным приложением (по умолчанию)."""
        try:
            os.startfile(str(path))  # noqa: S606 — намеренное открытие внешним приложением
        except Exception as e:
            print(f"Не удалось открыть {path}: {e}")

    # ── действия (кооперативные: вне каталога делегируем super()) ───
    def handle_enter(self) -> bool:
        f = self._catalog_file_from_index(self.tree.currentIndex())
        if f is None:
            return super().handle_enter()
        if f.is_dir:
            index = self.tree.currentIndex()
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
        return True  # файл: preview уже показан при выборе

    def handle_f4(self) -> bool:
        f = self._catalog_file_from_index(self.tree.currentIndex())
        if f is None:
            return super().handle_f4()
        if f.is_dir:
            return True
        if self.notes_panel.is_edit_mode():
            self._save_active_file()
            self.notes_panel.enter_preview()
        else:
            if detect_engine(f.name, "") == "image":
                self._open_external(f.path)  # картинка → внешнее приложение
                return True
            text = self.catalog_manager.read_text(f.path)
            if text is not None:
                self.notes_panel.enter_edit(caret=0)
                self.notes_panel.focus_editor()
            else:
                self._open_external(f.path)  # бинарный → внешнее приложение
        return True

    def handle_delete(self) -> bool:
        f = self._catalog_file_from_index(self.tree.currentIndex())
        if f is not None:
            return True  # в v1 файлы каталога из дерева не удаляем
        return super().handle_delete()

    # ── контекстное меню ─────────────────────────────────────────────
    def _on_catalog_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        self.tree.setCurrentIndex(index)
        f = self._catalog_file_from_index(index)
        if f is None:
            return

        menu = QMenu(self)
        if f.is_dir:
            menu.addAction("🔄 Обновить", self.ensure_catalog_node)
        else:
            menu.addAction("🖥️ Открыть внешним приложением", lambda: self._open_external(f.path))
            menu.addAction("🔄 Обновить", self.ensure_catalog_node)
        menu.exec(self.tree.viewport().mapToGlobal(pos))
