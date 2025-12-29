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
    """Основное окно с деревом баз 1С и управлением процессами."""
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
        self.tree.setColumnWidth(2, 60)
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Данные
        self.all_bases = []
        self.last_launched_db = None
        self.last_activated_process = None  # Последний активированный процесс 1C

        # Настройка трея
        self.setup_tray_icon()

        # Вспомогательные менеджеры и логика
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.actions = DatabaseActions(self, self.all_bases, self.save_bases, self.reload_and_navigate)
        self.operations = DatabaseOperations(self, self.all_bases, self.save_bases, self.reload_and_navigate)
        self.process_actions = ProcessActions(self)
        self.tree_builder = TreeBuilder(self.model)
        self.opened_bases_builder = OpenedBasesTreeBuilder(self.model)

        self.setup_shortcuts()
        self.hotkey_manager.register()
        self.load_bases()
        self.refresh_opened_bases()
        self.expand_and_select_initial()

    def setup_tray_icon(self):
        """Настройка иконки в системном трее."""
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        """Обработка активации иконки в трее."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        """Показать окно из трея."""
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.refresh_opened_bases()
        self.expand_and_select_initial()

    def minimize_to_tray(self):
        """Свернуть окно в трей."""
        self.hide()

    def quit_application(self):
        """Полный выход из приложения."""
        self.hotkey_manager.unregister()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """При закрытии окна сворачиваем в трей вместо выхода."""
        event.ignore()
        self.minimize_to_tray()

    def nativeEvent(self, eventType, message):
        handled, result = self.hotkey_manager.handle_native_event(eventType, message)
        if handled:
            return True, 0
        return super().nativeEvent(eventType, message)

    def setup_shortcuts(self):
        """Настройка горячих клавиш."""
        shortcuts = {
            "F1": self.show_help,
            "F3": self.handle_f3_open,
            "F4": self.handle_f4_open,
            "F5": self.handle_f5_ir_tools,
            "F6": self.handle_f6_server_console,
            "F7": self.handle_f7_save_cfg,
            "Ctrl+F7": self.handle_ctrl_f7_update_cfg_from_repository,
            "F8": self.handle_f8_dump_cf,
            "Return": self.handle_enter,
            "Ctrl+C": lambda: self.operations.copy_connection_string(self.operations.get_selected_database(self.model, self.tree)),
            "Ctrl+D": lambda: self.operations.duplicate_database(self.operations.get_selected_database(self.model, self.tree), Database1C),
            "Ctrl+E": lambda: self.operations.edit_database_settings(self.operations.get_selected_database(self.model, self.tree), DatabaseSettingsDialog),
            "Del": self.handle_delete,
            "Shift+Del": self.handle_shift_delete,
            "Shift+F10": lambda: self.operations.add_database(Database1C, DatabaseSettingsDialog, lambda: self.operations.get_current_folder(self.model, self.tree)),
            "Esc": self.minimize_to_tray,
            "Shift+Esc": self.quit_application
        }
        for key, handler in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)

    def handle_enter(self):
        """Обработка Enter: активация процесса или открытие базы."""
        process = self.process_actions.get_selected_process()
        if process:
            self.process_actions.activate_process(process)
        else:
            db = self.operations.get_selected_database(self.model, self.tree)
            if db:
                self.actions.open_database(db)

    def handle_f3_open(self):
        """Обработка F3: открытие только базы (не процесса)."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            open_success = self.actions.open_database(db)
            if open_success:
                self.minimize_to_tray()

    def handle_f4_open(self):
        """Обработка F4: открытие конфигуратора."""
        open_success = self.actions.open_configurator(self.operations.get_selected_database(self.model, self.tree))
        if open_success:
            self.minimize_to_tray()

    def handle_f5_ir_tools(self):
        """Обработка F5: запуск инструментов ИР для выбранной базы."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            open_success = self.actions.open_ir_tools(db)
            if open_success:
                self.minimize_to_tray()

    def handle_f6_server_console(self):
        """Обработка F6: запуск консоли сервера 1С для выбранной базы."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            open_success = self.actions.open_server_console(db)
            if open_success:
                self.minimize_to_tray()

    def handle_f7_save_cfg(self):
        """Обработка F7: обновление конфигурации БД (/UpdateDBCfg) для выбранной базы."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            self.actions.save_cfg(db)

    def handle_ctrl_f7_update_cfg_from_repository(self):
        """Обработка Ctrl+F7: обновление конфигурации из хранилища и сохранение (/UpdateDBCfg)."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            self.actions.update_cfg_from_repository(db)

    def handle_f8_dump_cf(self):
        """Обработка F8: выгрузка CF (/DumpCfg) для выбранной базы."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            self.actions.dump_cf(db)

    def handle_delete(self):
        """Обработка Del: закрытие процесса или удаление базы."""
        process = self.process_actions.get_selected_process()
        if process:
            self.process_actions.close_process(process, force=False)
        else:
            db = self.operations.get_selected_database(self.model, self.tree)
            if db:
                self.operations.delete_database(db)

    def handle_shift_delete(self):
        """Обработка Shift+Del: принудительное завершение процесса или очистка кеша."""
        process = self.process_actions.get_selected_process()
        if process:
            self.process_actions.close_process(process, force=True)
        else:
            db = self.operations.get_selected_database(self.model, self.tree)
            if db:
                self.operations.clear_cache(db)

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def load_bases(self):
        """Загрузка баз из ibases.v8i."""
        reader = BaseReader(IBASES_PATH, ENCODING)
        self.all_bases.clear()
        self.all_bases.extend(reader.read_bases())
        self.tree_builder.build_tree(self.all_bases)

    def refresh_opened_bases(self):
        result = self.opened_bases_builder.build_tree()
        if result:
            folder_item, process_count = result
            folder_index = self.tree.model().indexFromItem(folder_item)
            self.tree.setFirstColumnSpanned(folder_index.row(), folder_index.parent(), True)
            for proc_row in range(process_count):
                self.tree.setFirstColumnSpanned(proc_row, folder_index, True)
            self.expand_and_select_initial()

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
                    if base.client_type:
                        f.write(f"ClientType={base.client_type}\n")
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
        self.refresh_opened_bases()
        self.expand_and_select_initial()

    def expand_and_select_initial(self):
        """Разворачивает нужные папки и устанавливает курсор."""
        opened_folder_idx = None
        recent_folder_idx = None

        for folder_idx in range(self.model.rowCount()):
            folder_item = self.model.item(folder_idx, 0)
            if not folder_item:
                continue
            if "Открытые базы" in folder_item.text():
                opened_folder_idx = folder_idx
            elif "Недавние" in folder_item.text():
                recent_folder_idx = folder_idx

        if opened_folder_idx is not None:
            folder_item = self.model.item(opened_folder_idx, 0)
            folder_index = self.model.index(opened_folder_idx, 0)
            self.tree.expand(folder_index)
            if folder_item.rowCount() > 0:
                if self.last_activated_process:
                    for proc_idx in range(0, folder_item.rowCount()):
                        proc_item = folder_item.child(proc_idx, 0)
                        if proc_item:
                            proc = proc_item.data(Qt.UserRole)
                            if proc and proc.pid == self.last_activated_process.pid:
                                proc_index = self.model.index(proc_idx, 0, folder_index)
                                self.tree.setCurrentIndex(proc_index)
                                self.tree.scrollTo(proc_index)
                                return
                first_proc_index = self.model.index(0, 0, folder_index)
                self.tree.setCurrentIndex(first_proc_index)
                self.tree.scrollTo(first_proc_index)
                return

        if recent_folder_idx is not None:
            folder_item = self.model.item(recent_folder_idx, 0)
            folder_index = self.model.index(recent_folder_idx, 0)
            self.tree.expand(folder_index)
            if self.last_launched_db:
                for db_idx in range(folder_item.rowCount()):
                    db_item = folder_item.child(db_idx, 0)
                    if db_item:
                        db = db_item.data(Qt.UserRole)
                        if db and db.id == self.last_launched_db.id:
                            db_index = self.model.index(db_idx, 0, folder_index)
                            self.tree.setCurrentIndex(db_index)
                            self.tree.scrollTo(db_index)
                            return
            if folder_item.rowCount() > 0:
                first_db_index = self.model.index(0, 0, folder_index)
                self.tree.setCurrentIndex(first_db_index)
                self.tree.scrollTo(first_db_index)
