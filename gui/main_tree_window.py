# gui/main_tree_window.py

from PySide6.QtWidgets import QMainWindow, QTreeView, QVBoxLayout, QWidget, QStatusBar
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING

class TreeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Дерево баз 1С")
        self.resize(900, 600)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            "Имя базы", "Папка", "Тип подключения", "Connect", "Версия"
        ])
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        # выход/вход в папки по стрелкам работает из коробки
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.load_bases()

    def load_bases(self):
        from collections import defaultdict
        reader = BaseReader(IBASES_PATH, ENCODING)
        bases = reader.read_bases()
        self.model.removeRows(0, self.model.rowCount())
        folders = defaultdict(list)
        for base in bases:
            folder = base.get_folder_path()
            folders[folder].append(base)
        for folder, dbases in folders.items():
            folder_item = QStandardItem(folder)
            folder_item.setEditable(False)
            row = [folder_item] + [QStandardItem("") for _ in range(4)]
            self.model.appendRow(row)
            for base in dbases:
                vers = base.get_full_version()
                row = [
                    QStandardItem(base.name),
                    QStandardItem(folder),
                    QStandardItem(base.get_connection_type()),
                    QStandardItem(base.connect),
                    QStandardItem(vers)
                ]
                for item in row:
                    item.setEditable(False)
                folder_item.appendRow(row)

        self.statusBar.showMessage(f"Найдено баз: {sum(len(v) for v in folders.values())}")

