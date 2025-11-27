from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QStatusBar, QMessageBox, QSystemTrayIcon, QMenu, QStyle, QApplication
)
from PySide6.QtGui import QStandardItemModel, QKeySequence, QShortcut, QIcon, QAction
from PySide6.QtCore import Qt
from services.base_reader import BaseReader
from services.process_manager import ProcessManager, Process1C
from config import IBASES_PATH, ENCODING
from dialogs import HelpDialog, DatabaseSettingsDialog
from models.database import Database1C

from gui.hotkeys import GlobalHotkeyManager
from gui.actions import DatabaseActions, DatabaseOperations, ProcessActions
from gui.tree import TreeBuilder, OpenedBasesTreeBuilder

class TreeWindow(QMainWindow):
    ...

    def refresh_opened_bases_and_restore(self):
        """
        Обновить "Открытые базы", развернуть папку и установить курсор на первый дочерний элемент
        """
        result = self.opened_bases_builder.build_tree()
        if result:
            folder_item, process_count = result
            folder_index = self.tree.model().indexFromItem(folder_item)
            self.tree.setFirstColumnSpanned(folder_index.row(), folder_index.parent(), True)
            for proc_row in range(process_count):
                self.tree.setFirstColumnSpanned(proc_row, folder_index, True)
            # Разворачиваем папку
            self.tree.expand(folder_index)
            # На первый дочерний элемент, если есть
            if folder_item.rowCount() > 1:
                first_proc_index = self.model.index(1, 0, folder_index)
                self.tree.setCurrentIndex(first_proc_index)
                self.tree.scrollTo(first_proc_index)

    ... # Остальной неизменный код класса
