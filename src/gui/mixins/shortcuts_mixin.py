from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeySequence, QShortcut
from ..dialogs import DatabaseSettingsDialog
from models.database import Database1C
from gui.theme import ThemeManager


class ShortcutsMixin:
    """Миксин для настройки горячих клавиш и их обработчиков."""

    def setup_shortcuts(self):
        """Настройка горячих клавиш."""
        shortcuts = {
            "F1": self.show_help,
            "F3": self.handle_f3_open,
            "F4": self.handle_f4_open,
            "Shift+Return": self.handle_f4_open,
            "F5": self.handle_f5_ir_tools,
            "F6": self.handle_f6_server_console,
            "F7": self.handle_f7_save_cfg,
            "Ctrl+F7": self.handle_ctrl_f7_update_cfg_from_repository,
            "F8": self.handle_f8_dump_cf,
            "Return": self.handle_enter,
            "Ctrl+C": lambda: self.operations.copy_connection_string(
                self.operations.get_selected_database(self.model, self.tree)
            ),
            "Ctrl+D": lambda: self.operations.duplicate_database(
                self.operations.get_selected_database(self.model, self.tree), Database1C
            ),
            "Ctrl+E": lambda: self.operations.edit_database_settings(
                self.operations.get_selected_database(self.model, self.tree), DatabaseSettingsDialog
            ),
            "Ctrl+I": self.edit_ibases_in_notepad,
            "Del": self.handle_delete,
            "Backspace": self.handle_delete,
            "Shift+Del": self.handle_shift_delete,
            "Shift+F10": lambda: self.operations.add_database(
                Database1C, DatabaseSettingsDialog,
                lambda: self.operations.get_current_folder(self.model, self.tree)
            ),
            "Esc": self.minimize_to_tray,
            "Shift+Esc": self.quit_application,
            "F10": self.toggle_theme,
        }
        for key, handler in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)

    def toggle_theme(self):
        """Переключение темы приложения (светлая/темная)."""
        ThemeManager.toggle_theme(QApplication.instance())
        status = "Темная" if ThemeManager.is_dark() else "Светлая"
        self.statusBar.showMessage(f"\U0001f3a8 Тема переключена: {status}", 2000)

    def handle_enter(self):
        """Обработка Enter: активация процесса или открытие базы."""
        process = self.process_actions.get_selected_process()
        if process:
            selected_index = self.tree.currentIndex()
            if selected_index.isValid():
                parent_item = self.model.itemFromIndex(selected_index.parent())
                if parent_item and "Основное" in parent_item.text():
                    self.process_actions.activate_process(process)
                    self.last_activated_main_process = process
                else:
                    self.process_actions.activate_process(process)
                    self.last_activated_process = process
        else:
            db = self.operations.get_selected_database(self.model, self.tree)
            if db:
                open_success = self.actions.open_database(db)
                if open_success:
                    self.minimize_to_tray()

    def handle_f3_open(self):
        """Обработка F3: открытие только базы (не процесса)."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            open_success = self.actions.open_database(db)
            if open_success:
                self.minimize_to_tray()

    def handle_f4_open(self):
        """Обработка F4: открытие конфигуратора."""
        open_success = self.actions.open_configurator(
            self.operations.get_selected_database(self.model, self.tree)
        )
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
        """Открыть диалог справки."""
        from ..dialogs import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec()
