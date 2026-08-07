"""Построение узла «📂 Каталог» в дереве лаунчера.

Корень помечается CATALOG_ROOT_DATA (Qt.UserRole), элементы — CatalogFile.
Папки строятся рекурсивно, файлы — с учётом маски менеджера.
"""

from collections import defaultdict
from pathlib import Path

from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt

from catalog.catalog_manager import CatalogManager, CatalogFile

CATALOG_ROOT_DATA = "catalog:root"  # маркер корневого узла каталога


class CatalogTreeBuilder:
    NODE_NAME = "📂 Каталог"

    def __init__(self, model, manager: CatalogManager):
        self.model = model
        self.manager = manager

    def build_node(self) -> QStandardItem:
        root = QStandardItem(self.NODE_NAME)
        root.setEditable(False)
        root.setData(CATALOG_ROOT_DATA, Qt.UserRole)

        children_of = defaultdict(list)
        for f in self.manager.scan():
            rel = f.path.relative_to(self.manager.root)
            children_of[rel.parent].append(f)

        for item in self._build_level(children_of, Path(".")):
            root.appendRow(item)
        return root

    def _build_level(self, children_of, parent_rel: Path):
        items = children_of.get(parent_rel, [])
        items.sort(key=lambda f: (0 if f.is_dir else 1, f.name.lower()))
        for f in items:
            item = QStandardItem(f.name)
            item.setEditable(False)
            item.setData(f, Qt.UserRole)
            if f.is_dir:
                for child in self._build_level(children_of, f.path.relative_to(self.manager.root)):
                    item.appendRow(child)
            yield item
