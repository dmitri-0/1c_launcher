"""Операции CRUD и вспомогательные операции над базами 1С.

Отвечает за:
- Добавление, редактирование, копирование, удаление баз
- Операции с кэшем
- Копирование строк подключения
- Вспомогательные методы выбора
"""

import uuid
from datetime import datetime
from pathlib import Path
import shutil
import os
from PySide6.QtWidgets import QMessageBox, QApplication

class DatabaseOperations:
    def __init__(self, window, all_bases, save_callback, reload_callback):
        self.window = window
        self.all_bases = all_bases
        self.save_callback = save_callback
        self.reload_callback = reload_callback

    def get_selected_database(self, model, tree):
        indexes = tree.selectedIndexes()
        if not indexes:
            self.window.statusBar.showMessage("⚠️ Выберите базу данных")
            return None
        index = indexes[0]
        item = model.itemFromIndex(index)
        if item and item.data(256): # Qt.UserRole == 256
            return item.data(256)
        self.window.statusBar.showMessage("⚠️ Выберите базу, а не папку")
        return None

    def get_current_folder(self, model, tree):
        indexes = tree.selectedIndexes()
        if not indexes:
            return "/"
        index = indexes[0]
        item = model.itemFromIndex(index)
        folder_parts = []
        current_item = item
        while current_item:
            if current_item.data(256):
                database = current_item.data(256)
                if not database.is_recent:
                    return database.folder
            else:
                folder_name = current_item.text()
                if "Недавние" not in folder_name:
                    folder_parts.insert(0, folder_name)
            current_item = current_item.parent()
        if folder_parts:
            return "/" + "/".join(folder_parts)
        return "/"

    def copy_connection_string(self, database):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(database.connect)
            self.window.statusBar.showMessage(f"✅ Строка подключения скопирована в буфер обмена")
        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка копирования: {e}")

    def duplicate_database(self, database, Database1C):
        try:
            new_database = Database1C(
                id=str(uuid.uuid4()),
                name=database.name,
                folder=database.folder,
                connect=database.connect,
                app=database.app,
                version=database.version,
                app_arch=database.app_arch,
                order_in_tree=database.order_in_tree,
                usr=database.usr,
                pwd=database.pwd,
                original_folder=database.original_folder,
                is_recent=database.is_recent,
                last_run_time=None,
                usr_enterprise=database.usr_enterprise,
                pwd_enterprise=database.pwd_enterprise,
                usr_configurator=database.usr_configurator,
                pwd_configurator=database.pwd_configurator,
                usr_storage=database.usr_storage,
                pwd_storage=database.pwd_storage,
                storage_path=database.storage_path,
                client_type=database.client_type,
            )
            current_date = datetime.now().strftime("%Y-%m-%d")
            database.name = f"{database.name} {current_date}"
            index = self.all_bases.index(database)
            self.all_bases.insert(index + 1, new_database)
            self.save_callback()
            self.reload_callback()
            self.window.statusBar.showMessage(f"✅ База скопирована. Исходная база переименована в '{database.name}'")
        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка копирования базы: {e}")

    def edit_database_settings(self, database, DatabaseSettingsDialog):
        dialog = DatabaseSettingsDialog(self.window, database)
        if dialog.exec():
            settings = dialog.get_settings()
            database.name = settings['name']
            database.folder = settings['folder']
            database.connect = settings['connect']
            database.usr = settings.get('usr')
            database.pwd = settings.get('pwd')
            database.version = settings['version']
            database.app_arch = settings['app_arch']
            database.app = settings['app']
            database.storage_path = settings['storage_path']
            database.usr_enterprise = settings['usr_enterprise']
            database.pwd_enterprise = settings['pwd_enterprise']
            database.usr_configurator = settings['usr_configurator']
            database.pwd_configurator = settings['pwd_configurator']
            database.usr_storage = settings['usr_storage']
            database.pwd_storage = settings['pwd_storage']
            database.client_type = settings['client_type']
            self.save_callback()
            self.reload_callback()
            self.window.statusBar.showMessage(f"✅ Настройки базы {database.name} сохранены")

    def delete_database(self, database):
        if database.is_recent:
            reply = QMessageBox.question(
                self.window,
                "Удаление из недавних",
                f"Убрать базу '{database.name}' из недавних?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                database.is_recent = False
                if database.original_folder:
                    database.folder = database.original_folder
                    database.original_folder = None
                database.last_run_time = None
                self.save_callback()
                self.reload_callback()
                self.window.statusBar.showMessage(f"✅ База '{database.name}' убрана из недавних")
        else:
            reply = QMessageBox.question(
                self.window,
                "Удаление базы",
                f"Удалить базу '{database.name}' из списка?\n\nКэш базы также будет очищен.\n\nВнимание: это не удалит файлы базы данных!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                cache_result = self._clear_database_cache(database)
                self.all_bases.remove(database)
                self.save_callback()
                self.reload_callback()
                result_message = f"✅ База '{database.name}' удалена из списка\n\nРезультат очистки кэша:\n" + "\n".join(cache_result)
                QMessageBox.information(
                    self.window,
                    "База удалена",
                    result_message
                )
                self.window.statusBar.showMessage(f"✅ База '{database.name}' удалена")

    def clear_cache(self, database):
        reply = QMessageBox.question(
            self.window,
            "Очистка кэша",
            f"Очистить кэш базы '{database.name}'?\n\nБудет удален:\n- Программный кэш ...{database.id})\n- Пользовательский кэш ...{database.id})\n- Кэш ИР Портативный (по строке подключения)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        deleted_items = self._clear_database_cache(database)
        result_message = "\n".join(deleted_items)
        QMessageBox.information(
            self.window,
            "Результат очистки кэша",
            result_message
        )
        self.window.statusBar.showMessage(f"✅ Кэш базы '{database.name}' очищен")

    def add_database(self, Database1C, DatabaseSettingsDialog, get_current_folder):
        current_folder = get_current_folder()
        new_database = Database1C(
            id=str(uuid.uuid4()),
            name="Новая база",
            folder=current_folder,
            connect="",
            app=None,
            version=None,
            app_arch='x86',
            order_in_tree=None,
            usr=None,
            pwd=None,
            original_folder=None,
            is_recent=False,
            last_run_time=None,
            usr_enterprise=None,
            pwd_enterprise=None,
            usr_configurator=None,
            pwd_configurator=None,
            usr_storage=None,
            pwd_storage=None,
            storage_path=None,
            client_type='thick',
        )
        dialog = DatabaseSettingsDialog(self.window, new_database)
        if dialog.exec():
            settings = dialog.get_settings()
            new_database.name = settings['name']
            new_database.folder = settings['folder']
            new_database.connect = settings['connect']
            new_database.usr = settings.get('usr')
            new_database.pwd = settings.get('pwd')
            new_database.version = settings['version']
            new_database.app_arch = settings['app_arch']
            new_database.app = settings['app']
            new_database.storage_path = settings['storage_path']
            new_database.usr_enterprise = settings['usr_enterprise']
            new_database.pwd_enterprise = settings['pwd_enterprise']
            new_database.usr_configurator = settings['usr_configurator']
            new_database.pwd_configurator = settings['pwd_configurator']
            new_database.usr_storage = settings['usr_storage']
            new_database.pwd_storage = settings['pwd_storage']
            new_database.client_type = settings['client_type']
            self.all_bases.append(new_database)
            self.save_callback()
            self.reload_callback()
            self.window.statusBar.showMessage(f"✅ База '{new_database.name}' добавлена")

    def _clear_database_cache(self, database):
        try:
            appdata_local = Path(os.environ.get('LOCALAPPDATA', ''))
            appdata_roaming = Path(os.environ.get('APPDATA', ''))
            deleted_items = []
            program_cache_path = appdata_local / '1C' / '1cv8' / database.id
            if program_cache_path.exists():
                try:
                    shutil.rmtree(program_cache_path)
                    deleted_items.append(f"✅ Программный кэш: {program_cache_path}")
                except Exception as e:
                    deleted_items.append(f"⚠️ Ошибка удаления программного кэша: {e}")
            else:
                deleted_items.append("ℹ️ Программный кэш не найден")
            
            user_cache_path = appdata_roaming / '1C' / '1Cv82' / database.id
            if user_cache_path.exists():
                try:
                    shutil.rmtree(user_cache_path)
                    deleted_items.append(f"✅ Пользовательский кэш: {user_cache_path}")
                except Exception as e:
                    deleted_items.append(f"⚠️ Ошибка удаления пользовательского кэша: {e}")
            else:
                deleted_items.append("ℹ️ Пользовательский кэш не найден")

            # Очистка кэша ИР Портативный
            ir_folder_name = self._generate_ir_folder_name(database.connect)
            if ir_folder_name:
                ir_cache_path = appdata_local / '1C' / '1cv8' / ir_folder_name
                if ir_cache_path.exists():
                    try:
                        shutil.rmtree(ir_cache_path)
                        deleted_items.append(f"✅ Кэш ИР: {ir_cache_path}")
                    except Exception as e:
                        deleted_items.append(f"⚠️ Ошибка удаления кэша ИР: {e}")
                else:
                    deleted_items.append(f"ℹ️ Кэш ИР не найден ({ir_folder_name})")

            return deleted_items
        except Exception as e:
            return [f"❌ Ошибка очистки кэша: {e}"]

    def _generate_ir_folder_name(self, connection_string):
        """
        Генерирует имя папки кэша для ИР Портативный на основе строки подключения.
        Пример: Srvr="srv-1c-8325:1541";Ref="ZUP_0202_Pechericadv_1";
        Результат: Srvr__srv_1c_8325_1541__Ref__ZUP_0202_Pechericadv_1__
        """
        if not connection_string:
            return ""
        
        name = connection_string
        # Replace parameter separators and quotes
        name = name.replace('="', '__')
        name = name.replace('";', '__')
        
        # Replace unsafe characters in filenames
        name = name.replace(':', '_')
        name = name.replace('-', '_')
        name = name.replace('.', '_')
        name = name.replace(',', '_')
        name = name.replace('\\', '_')
        name = name.replace('/', '_')
        name = name.replace(' ', '_')
        
        return name
