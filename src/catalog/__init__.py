"""Пакет «Каталог» — просмотр/редактирование содержимого папки как заметок.

Файлы каталога (root-узел «📂 Каталог») показываются в той же панели, что и
заметки, через общие движки рендеринга: md/текст — preview и редактирование
в панели (сохранение в файл), бинарные (картинки/pdf) — внешним приложением (F4).
"""

from .catalog_manager import CatalogManager, CatalogFile
from .catalog_tree_builder import CatalogTreeBuilder, CATALOG_ROOT_DATA

__all__ = [
    "CatalogManager",
    "CatalogFile",
    "CatalogTreeBuilder",
    "CATALOG_ROOT_DATA",
]
