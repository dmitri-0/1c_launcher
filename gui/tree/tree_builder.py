"""Построение модели дерева и логика отображения иерархии баз 1С.
"""

from collections import defaultdict
from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt

class TreeBuilder:
    def __init__(self, model):
        self.model = model

    def add_bases_to_folder(self, folder_item, folder_path, bases):
        subfolders = defaultdict(list)
        direct_bases = []
        for base in bases:
            if base.folder == "/" + folder_path:
                direct_bases.append(base)
            elif base.folder.startswith("/" + folder_path + "/"):
                rel_path = base.folder[len(folder_path)+2:]
                if "/" in rel_path:
                    subfolder_name = rel_path.split("/", 1)[0]
                    subfolders[subfolder_name].append(base)
                else:
                    subfolders[rel_path].append(base)
        for subfolder_name in sorted(subfolders.keys()):
            subfolder_item = QStandardItem(subfolder_name)
            subfolder_item.setEditable(False)
            subfolder_path = folder_path + "/" + subfolder_name
            self.add_bases_to_folder(subfolder_item, subfolder_path, subfolders[subfolder_name])
            row = [subfolder_item] + [QStandardItem("") for _ in range(2)]
            folder_item.appendRow(row)
        for base in direct_bases:
            vers = base.get_full_version()
            row = [
                QStandardItem(base.name),
                QStandardItem(base.connect),
                QStandardItem(vers)
            ]
            for item in row:
                item.setEditable(False)
            row[0].setData(base, Qt.UserRole)
            folder_item.appendRow(row)

    def build_tree(self, bases):
        self.model.removeRows(0, self.model.rowCount())
        recent_bases = [base for base in bases if base.is_recent]
        regular_bases = [base for base in bases if not base.is_recent]
        if recent_bases:
            folder_item = QStandardItem("Недавние")
            folder_item.setEditable(False)
            row = [folder_item] + [QStandardItem("") for _ in range(2)]
            self.model.appendRow(row)
            for base in recent_bases:
                vers = base.get_full_version()
                base_row = [
                    QStandardItem(base.name),
                    QStandardItem(base.connect),
                    QStandardItem(vers)
                ]
                for item in base_row:
                    item.setEditable(False)
                base_row[0].setData(base, Qt.UserRole)
                folder_item.appendRow(base_row)
        root_folders = defaultdict(list)
        for base in regular_bases:
            folder = base.folder.lstrip("/")
            if folder:
                root_folder = folder.split("/")[0]
                root_folders[root_folder].append(base)
            else:
                root_folders[""] .append(base)
        for root_folder_name in sorted(root_folders.keys()):
            if not root_folder_name:
                continue
            folder_bases = root_folders[root_folder_name]
            folder_item = QStandardItem(root_folder_name)
            folder_item.setEditable(False)
            row = [folder_item] + [QStandardItem("") for _ in range(2)]
            self.model.appendRow(row)
            self.add_bases_to_folder(folder_item, root_folder_name, folder_bases)
