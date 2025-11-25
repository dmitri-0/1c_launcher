from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QStatusBar, QMessageBox, QSystemTrayIcon, QMenu, QStyle
)
from PySide6.QtGui import QStandardItemModel, QKeySequence, QShortcut, QIcon, QAction
from PySide6.QtCore import Qt
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING
from dialogs import HelpDialog, DatabaseSettingsDialog
from models.database import Database1C

from gui.hotkeys import GlobalHotkeyManager
from gui.actions import DatabaseActions, DatabaseOperations
from gui.tree import TreeBuilder

class TreeWindow(QMainWindow):
    """
    Главное окно приложения с деревом баз данных 1С. Отвечает только за UI,
    координацию действий и подключение вспомогательных менеджеров.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Базы 1С")
        self.resize(1100, 600)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Модель и дерево
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            "Имя базы", "Connect", "Версия"
        ])
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 450)
        self.tree.setColumnWidth(2, 100)
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Данные
        self.all_bases = []
        self.last_launched_db = None

        # Настройка трея
        self.setup_tray_icon()

        # Вспомогательные менеджеры и логика
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.actions = DatabaseActions(self, self.all_bases, self.save_bases, self.reload_and_navigate)
        self.operations = DatabaseOperations(self, self.all_bases, self.save_bases, self.reload_and_navigate)
        self.tree_builder = TreeBuilder(self.model)

        self.setup_shortcuts()
        self.hotkey_manager.register()
        self.load_bases()
        self.expand_recent_and_select_last()

    def setup_tray_icon(self):
        """Настройка иконки в системном трее"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Используем стандартную иконку приложения
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        self.tray_icon.setIcon(icon)
        
        # Создаем контекстное меню для трея
        tray_menu = QMenu()
        
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # Двойной клик по иконке трея показывает окно
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        """Обработка активации иконки в трее"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        """Показать окно из трея"""
        self.showNormal()
        self.activateWindow()

    def minimize_to_tray(self):
        """Свернуть окно в трей"""
        self.hide()
        self.tray_icon.showMessage(
            "Базы 1С",
            "Приложение свернуто в трей",
            QSystemTrayIcon.Information,
            2000
        )

    def quit_application(self):
        """Полный выход из приложения"""
        self.hotkey_manager.unregister()
        self.tray_icon.hide()
        self.close()

    def closeEvent(self, event):
        """При закрытии окна сворачиваем в трей вместо выхода"""
        event.ignore()
        self.minimize_to_tray()

    def nativeEvent(self, eventType, message):
        handled, result = self.hotkey_manager.handle_native_event(eventType, message)
        if handled:
            return True, 0
        return super().nativeEvent(eventType, message)

    def setup_shortcuts(self):
        shortcuts = {
            "F1": self.show_help,
            "F3": lambda: self.actions.open_database(self.operations.get_selected_database(self.model, self.tree)),
            "F4": lambda: self.actions.open_configurator(self.operations.get_selected_database(self.model, self.tree)),
            "Ctrl+C": lambda: self.operations.copy_connection_string(self.operations.get_selected_database(self.model, self.tree)),
            "Ctrl+D": lambda: self.operations.duplicate_database(self.operations.get_selected_database(self.model, self.tree), Database1C),
            "Ctrl+E": lambda: self.operations.edit_database_settings(self.operations.get_selected_database(self.model, self.tree), DatabaseSettingsDialog),
            "Del": lambda: self.operations.delete_database(self.operations.get_selected_database(self.model, self.tree)),
            "Shift+Del": lambda: self.operations.clear_cache(self.operations.get_selected_database(self.model, self.tree)),
            "Shift+F10": lambda: self.operations.add_database(Database1C, DatabaseSettingsDialog, lambda: self.operations.get_current_folder(self.model, self.tree)),
            "Esc": self.minimize_to_tray
        }
        for key, handler in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def load_bases(self):
        reader = BaseReader(IBASES_PATH, ENCODING)
        self.all_bases.clear()
        self.all_bases.extend(reader.read_bases())
        self.tree_builder.build_tree(self.all_bases)

    def save_bases(self):
        try:
            with open(IBASES_PATH, 'w', encoding=ENCODING) as f:
                for base in self.all_bases:
                    f.write(f"[{base.name}]\n")
                    f.write(f"ID={base.id}\n")
                    f.write(f"Connect={base.connect}\n")
                    f.write(f"Folder={base.folder}\n")
                    if base.is_recent:
                        f.write(f"IsRecent=1\n")
                    if base.last_run_time:
                        f.write(f"LastRunTime={base.last_run_time.isoformat()}\n")
                    if base.app:
                        f.write(f"App={base.app}\n")
                    if base.version:
                        f.write(f"Version={base.version}\n")
                    if base.app_arch:
                        f.write(f"AppArch={base.app_arch}\n")
                    if base.order_in_tree is not None:
                        f.write(f"OrderInTree={base.order_in_tree}\n")
                    if base.usr:
                        f.write(f"Usr={base.usr}\n")
                    if base.pwd:
                        f.write(f"Pwd={base.pwd}\n")
                    if base.storage_path:
                        f.write(f"StoragePath={base.storage_path}\n")
                    if base.usr_enterprise:
                        f.write(f"UsrEnterprise={base.usr_enterprise}\n")
                    if base.pwd_enterprise:
                        f.write(f"PwdEnterprise={base.pwd_enterprise}\n")
                    if base.usr_configurator:
                        f.write(f"UsrConfigurator={base.usr_configurator}\n")
                    if base.pwd_configurator:
                        f.write(f"PwdConfigurator={base.pwd_configurator}\n")
                    if base.usr_storage:
                        f.write(f"UsrStorage={base.usr_storage}\n")
                    if base.pwd_storage:
                        f.write(f"PwdStorage={base.pwd_storage}\n")
                    f.write("\n")
        except Exception as e:
            self.statusBar.showMessage(f"❌ Ошибка сохранения: {e}")

    def reload_and_navigate(self):
        self.load_bases()
        self.expand_recent_and_select_last()

    def expand_recent_and_select_last(self):
        for folder_idx in range(self.model.rowCount()):
            folder_item = self.model.item(folder_idx, 0)
            if folder_item and "Недавние" in folder_item.text():
                folder_index = self.model.index(folder_idx, 0)
                self.tree.expand(folder_index)
                # Поиск последней запущенной базы
                if self.last_launched_db:
                    for db_idx in range(folder_item.rowCount()):
                        db_item = folder_item.child(db_idx, 0)
                        if db_item:
                            db = db_item.data(Qt.UserRole)
                            if db and db.id == self.last_launched_db.id:
                                db_index = self.model.index(db_idx, 0, folder_index)
                                self.tree.setCurrentIndex(db_index)
                                self.tree.scrollTo(db_index)
                                break
                else:
                    if folder_item.rowCount() > 0:
                        first_db_index = self.model.index(0, 0, folder_index)
                        self.tree.setCurrentIndex(first_db_index)
                        self.tree.scrollTo(first_db_index)
                break