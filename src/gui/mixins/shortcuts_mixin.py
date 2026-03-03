from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QKeySequence, QShortcut
from ..dialogs import DatabaseSettingsDialog
from models.database import Database1C
from gui.theme import ThemeManager


class ShortcutsMixin:
    """Миксин для настройки горячих клавиш и их обработчиков."""

    def toggle_theme(self):
        """Переключение темы приложения (светлая/темная)."""
        ThemeManager.toggle_theme(QApplication.instance())
        status = "Темная" if ThemeManager.is_dark() else "Светлая"
        self.statusBar.showMessage(f"\\U0001f3a8 Тема переключена: {status}", 2000)

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
        """Обработка F8: выгрузка CF (/DumpCfg) для выбранной базы, с вопросом об обновлении из хранилища."""
        db = self.operations.get_selected_database(self.model, self.tree)
        if db:
            reply = QMessageBox.question(
                self,
                "Выгрузка CF",
                "Обновить конфигурацию из хранилища перед выгрузкой?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.actions.update_cfg_from_repository_and_dump_cf(db)
            else:
                self.actions.save_and_dump_cf(db)

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
