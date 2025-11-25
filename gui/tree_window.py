# gui/tree_window.py

from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QStatusBar, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING
from dialogs import HelpDialog, DatabaseSettingsDialog
from collections import defaultdict
import os
from pathlib import Path
import platform
import re
import uuid
from datetime import datetime
import shutil
import tempfile
import sys

# Импорт для глобальных горячих клавиш (только для Windows)
if platform.system() == 'Windows':
    try:
        import win32con
        import win32gui
        WINDOWS_HOTKEY_AVAILABLE = True
    except ImportError:
        WINDOWS_HOTKEY_AVAILABLE = False
        print("Предупреждение: pywin32 не установлен. Глобальные горячие клавиши недоступны.")
else:
    WINDOWS_HOTKEY_AVAILABLE = False


class TreeWindow(QMainWindow):
    # ID для горячей клавиши
    HOTKEY_ID = 1
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Базы 1С")
        self.resize(1100, 600)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        self.bases_dict = {}
        self.all_bases = []
        self.last_launched_db = None
        self.hotkey_registered = False

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
        
        self.setup_shortcuts()
        self.register_global_hotkey()
        self.load_bases()
        self.expand_recent_and_select_last()

    def register_global_hotkey(self):
        """Регистрирует глобальную горячую клавишу Win+1"""
        if not WINDOWS_HOTKEY_AVAILABLE:
            return
        
        try:
            # Получаем ID окна
            hwnd = int(self.winId())
            
            # Регистрируем Win+1 (MOD_WIN = 0x0008, VK_1 = 0x31)
            # MOD_WIN = 0x0008, MOD_ALT = 0x0001, MOD_CONTROL = 0x0002, MOD_SHIFT = 0x0004
            import ctypes
            user32 = ctypes.windll.user32
            
            MOD_WIN = 0x0008
            VK_1 = 0x31  # Клавиша '1'
            
            result = user32.RegisterHotKey(hwnd, self.HOTKEY_ID, MOD_WIN, VK_1)
            
            if result:
                self.hotkey_registered = True
                print("✅ Глобальная горячая клавиша Win+1 зарегистрирована")
            else:
                print("⚠️ Не удалось зарегистрировать глобальную горячую клавишу Win+1")
                
        except Exception as e:
            print(f"❌ Ошибка регистрации глобальной горячей клавиши: {e}")

    def unregister_global_hotkey(self):
        """Отменяет регистрацию глобальной горячей клавиши"""
        if not WINDOWS_HOTKEY_AVAILABLE or not self.hotkey_registered:
            return
        
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            
            user32.UnregisterHotKey(hwnd, self.HOTKEY_ID)
            self.hotkey_registered = False
            print("✅ Глобальная горячая клавиша отменена")
            
        except Exception as e:
            print(f"❌ Ошибка отмены регистрации глобальной горячей клавиши: {e}")

    def nativeEvent(self, eventType, message):
        """Перехватывает нативные события Windows для обработки глобальных горячих клавиш"""
        if WINDOWS_HOTKEY_AVAILABLE and eventType == "windows_generic_MSG":
            try:
                import ctypes
                
                # Структура MSG в Windows
                msg = ctypes.wintypes.MSG.from_address(int(message))
                
                # WM_HOTKEY = 0x0312
                if msg.message == 0x0312:
                    if msg.wParam == self.HOTKEY_ID:
                        # Активируем окно
                        self.activate_window()
                        return True, 0
                        
            except Exception as e:
                print(f"Ошибка обработки nativeEvent: {e}")
        
        return super().nativeEvent(eventType, message)

    def activate_window(self):
        """Активирует и выводит окно на передний план"""
        try:
            # Показываем окно, если оно было свернуто
            if self.isMinimized():
                self.showNormal()
            
            # Активируем окно через Qt
            self.activateWindow()
            self.raise_()
            
            # Дополнительно используем Windows API для гарантированной активации
            if WINDOWS_HOTKEY_AVAILABLE:
                import ctypes
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                
                # SetForegroundWindow требует, чтобы окно было видимо
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
                user32.SetForegroundWindow(hwnd)
                
            print("✅ Окно активировано")
            
        except Exception as e:
            print(f"❌ Ошибка активации окна: {e}")

    def closeEvent(self, event):
        """Обработчик закрытия окна - отменяем регистрацию горячей клавиши"""
        self.unregister_global_hotkey()
        super().closeEvent(event)

    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        shortcuts = {
            "F1": self.show_help,
            "F3": self.open_database,
            "F4": self.open_configurator,
            "Ctrl+C": self.copy_connection_string,
            "Ctrl+D": self.duplicate_database,
            "Ctrl+E": self.edit_database_settings,
            "Del": self.delete_database,
            "Shift+Del": self.clear_cache,
            "Shift+F10": self.add_database,
            "Esc": self.close
        }
        
        for key, handler in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)

    def show_help(self):
        """Показать окно помощи (F1)"""
        dialog = HelpDialog(self)
        dialog.exec()

    def get_selected_database(self):
        """Получить выбранную базу данных"""
        indexes = self.tree.selectedIndexes()
        if not indexes:
            self.statusBar.showMessage("⚠️ Выберите базу данных")
            return None
        
        index = indexes[0]
        item = self.model.itemFromIndex(index)
        
        if item and item.data(Qt.UserRole):
            return item.data(Qt.UserRole)
        
        self.statusBar.showMessage("⚠️ Выберите базу, а не папку")
        return None

    def get_current_folder(self):
        """Получить полный путь папки, на которой стоит курсор (для новой базы)"""
        indexes = self.tree.selectedIndexes()
        if not indexes:
            return "/"
        
        index = indexes[0]
        item = self.model.itemFromIndex(index)
        
        folder_parts = []
        current_item = item
        
        while current_item:
            if current_item.data(Qt.UserRole):
                database = current_item.data(Qt.UserRole)
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

    def _parse_server_connect_string(self, connect_string):
        """
        Парсит строку подключения серверной базы и преобразует её в формат для /S параметра.
        """
        try:
            srvr_match = re.search(r'Srvr="([^"]+)"', connect_string, re.IGNORECASE)
            ref_match = re.search(r'Ref="([^"]+)"', connect_string, re.IGNORECASE)
            
            if srvr_match and ref_match:
                server = srvr_match.group(1)
                ref = ref_match.group(1)
                return f"{server}\\{ref}"
            
            return connect_string
            
        except Exception as e:
            print(f"Ошибка парсинга строки подключения: {e}")
            return connect_string

    def _build_launch_command(self, executable, mode, database):
        """
        Формирует командную строку для запуска 1С
        mode: 'ENTERPRISE' или 'DESIGNER'
        """
        try:
            params = [mode]
            
            if database.connect:
                parsed_connect = self._parse_server_connect_string(database.connect)
                params.append(f'/S"{parsed_connect}"')
            
            # Используем учетные данные в зависимости от режима
            usr = None
            pwd = None
            
            if mode == 'ENTERPRISE':
                usr = database.usr_enterprise or database.usr  # Фолбэк на старое поле
                pwd = database.pwd_enterprise or database.pwd
            elif mode == 'DESIGNER':
                usr = database.usr_configurator or database.usr  # Фолбэк на старое поле
                pwd = database.pwd_configurator or database.pwd
            
            if usr:
                params.append(f'/N"{usr}"')
            if pwd:
                params.append(f'/P"{pwd}"')
            
            cmd_line = f'"{executable}" ' + ' '.join(f'"{p}"' if ' ' in p and not p.startswith('/') else p for p in params)
            
            return cmd_line
            
        except Exception as e:
            print(f"Ошибка формирования командной строки: {e}")
            return None

    def _launch_1c_process(self, executable, mode, database):
        """Запуск 1С через BAT-файл"""
        try:
            cmd_line = self._build_launch_command(executable, mode, database)
            
            if not cmd_line:
                return False
            
            self.statusBar.showMessage(f"🚀 Запуск: {cmd_line}")
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False, encoding='cp866') as bat_file:
                bat_file.write('@echo off\n')
                bat_file.write(f'start "" {cmd_line}\n')
                bat_file.write('exit\n')
                bat_path = bat_file.name
            
            os.startfile(bat_path)
            QTimer.singleShot(3000, lambda: self._cleanup_temp_file(bat_path))
            
            return True
            
        except Exception as e:
            print(f"Ошибка запуска через BAT: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _cleanup_temp_file(self, filepath):
        """Удаляет временный файл"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass

    def _move_to_recent(self, database):
        """Помечает базу как недавнюю и перемещает в начало списка"""
        if not database.is_recent and not database.original_folder:
            database.original_folder = database.folder
        
        database.is_recent = True
        database.last_run_time = datetime.now()
        
        if database in self.all_bases:
            self.all_bases.remove(database)
        
        self.all_bases.insert(0, database)
        self.save_bases()
        self.last_launched_db = database

    def _clear_database_cache(self, database):
        """Очищает кэш базы данных"""
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
            
            return deleted_items
            
        except Exception as e:
            return [f"❌ Ошибка очистки кэша: {e}"]

    def _delayed_reload_after_launch(self):
        """Перезагружает базы сразу после запуска"""
        self.load_bases()
        self.expand_recent_and_select_last()

    def open_database(self):
        """Открыть базу (F3)"""
        database = self.get_selected_database()
        if not database:
            return
        
        executable = self._get_1c_executable(database)
        if not executable:
            self.statusBar.showMessage("❌ Не удалось найти исполняемый файл 1C")
            return
        
        if self._launch_1c_process(executable, "ENTERPRISE", database):
            self._move_to_recent(database)
            self._delayed_reload_after_launch()
        else:
            self.statusBar.showMessage(f"❌ Ошибка при запуске базы {database.name}")

    def open_configurator(self):
        """Открыть конфигуратор (F4)"""
        database = self.get_selected_database()
        if not database:
            return
        
        executable = self._get_1c_executable(database)
        if not executable:
            self.statusBar.showMessage("❌ Не удалось найти исполняемый файл 1C")
            return
        
        if self._launch_1c_process(executable, "DESIGNER", database):
            self._move_to_recent(database)
            self._delayed_reload_after_launch()
        else:
            self.statusBar.showMessage(f"❌ Ошибка при запуске конфигуратора для {database.name}")

    def copy_connection_string(self):
        """Скопировать строку подключения (Ctrl+C)"""
        database = self.get_selected_database()
        if not database:
            return
        
        try:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(database.connect)
            self.statusBar.showMessage(f"✅ Строка подключения скопирована в буфер обмена")
        except Exception as e:
            self.statusBar.showMessage(f"❌ Ошибка копирования: {e}")

    def duplicate_database(self):
        """Копировать базу (Ctrl+D)"""
        database = self.get_selected_database()
        if not database:
            return
        
        try:
            from models.database import Database1C
            
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
                # Копируем новые поля
                usr_enterprise=database.usr_enterprise,
                pwd_enterprise=database.pwd_enterprise,
                usr_configurator=database.usr_configurator,
                pwd_configurator=database.pwd_configurator,
                usr_storage=database.usr_storage,
                pwd_storage=database.pwd_storage,
                storage_path=database.storage_path,
            )
            
            current_date = datetime.now().strftime("%Y-%m-%d")
            database.name = f"{database.name} {current_date}"
            
            index = self.all_bases.index(database)
            self.all_bases.insert(index + 1, new_database)
            
            self.save_bases()
            self.load_bases()
            
            self.statusBar.showMessage(f"✅ База скопирована. Исходная база переименована в '{database.name}'")
            
        except Exception as e:
            self.statusBar.showMessage(f"❌ Ошибка копирования базы: {e}")
            import traceback
            traceback.print_exc()

    def edit_database_settings(self):
        """Редактировать настройки базы (Ctrl+E)"""
        database = self.get_selected_database()
        if not database:
            return
        
        dialog = DatabaseSettingsDialog(self, database)
        
        if dialog.exec():
            settings = dialog.get_settings()
            
            database.name = settings['name']
            database.folder = settings['folder']
            database.connect = settings['connect']
            database.usr = settings.get('usr')  # Старое поле (для обратной совместимости)
            database.pwd = settings.get('pwd')
            database.version = settings['version']
            database.app_arch = settings['app_arch']
            database.app = settings['app']
            database.storage_path = settings['storage_path']
            # Новые поля
            database.usr_enterprise = settings['usr_enterprise']
            database.pwd_enterprise = settings['pwd_enterprise']
            database.usr_configurator = settings['usr_configurator']
            database.pwd_configurator = settings['pwd_configurator']
            database.usr_storage = settings['usr_storage']
            database.pwd_storage = settings['pwd_storage']
            
            self.save_bases()
            self.load_bases()
            
            self.statusBar.showMessage(f"✅ Настройки базы {database.name} сохранены")

    def delete_database(self):
        """Удалить базу (Del)"""
        database = self.get_selected_database()
        if not database:
            return
        
        if database.is_recent:
            reply = QMessageBox.question(
                self,
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
                
                self.save_bases()
                self.load_bases()
                
                self.statusBar.showMessage(f"✅ База '{database.name}' убрана из недавних")
        else:
            reply = QMessageBox.question(
                self,
                "Удаление базы",
                f"Удалить базу '{database.name}' из списка?\n\nКэш базы также будет очищен.\n\nВнимание: это не удалит файлы базы данных!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                cache_result = self._clear_database_cache(database)
                self.all_bases.remove(database)
                self.save_bases()
                self.load_bases()
                
                result_message = f"✅ База '{database.name}' удалена из списка\n\nРезультат очистки кэша:\n" + "\n".join(cache_result)
                QMessageBox.information(
                    self,
                    "База удалена",
                    result_message
                )
                
                self.statusBar.showMessage(f"✅ База '{database.name}' удалена")

    def clear_cache(self):
        """Очистить кэш базы (Shift+Del)"""
        database = self.get_selected_database()
        if not database:
            return
        
        reply = QMessageBox.question(
            self,
            "Очистка кэша",
            f"Очистить кэш базы '{database.name}'?\n\nБудет удален:\n- Программный кэш (AppData\\Local\\1C\\1cv8\\{database.id})\n- Пользовательский кэш (AppData\\Roaming\\1C\\1Cv82\\{database.id})",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        deleted_items = self._clear_database_cache(database)
        
        result_message = "\n".join(deleted_items)
        QMessageBox.information(
            self,
            "Результат очистки кэша",
            result_message
        )
        
        self.statusBar.showMessage(f"✅ Кэш базы '{database.name}' очищен")

    def add_database(self):
        """Добавить новую базу (Shift+F10)"""
        from models.database import Database1C
        
        current_folder = self.get_current_folder()
        
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
            # Новые поля
            usr_enterprise=None,
            pwd_enterprise=None,
            usr_configurator=None,
            pwd_configurator=None,
            usr_storage=None,
            pwd_storage=None,
            storage_path=None,
        )
        
        dialog = DatabaseSettingsDialog(self, new_database)
        
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
            # Новые поля
            new_database.usr_enterprise = settings['usr_enterprise']
            new_database.pwd_enterprise = settings['pwd_enterprise']
            new_database.usr_configurator = settings['usr_configurator']
            new_database.pwd_configurator = settings['pwd_configurator']
            new_database.usr_storage = settings['usr_storage']
            new_database.pwd_storage = settings['pwd_storage']
            
            self.all_bases.append(new_database)
            
            self.save_bases()
            self.load_bases()
            
            self.statusBar.showMessage(f"✅ База '{new_database.name}' добавлена")

    def _get_1c_executable(self, database):
        """Определяет путь к исполняемому файлу 1C с учетом разрядности"""
        bitness = database.app_arch or 'x86'
        
        if database.app:
            path = Path(database.app)
            if path.exists():
                return path
        
        if platform.system() == 'Windows':
            if database.version:
                version = database.version
                if bitness == 'x86_64':
                    path = Path(rf"C:\Program Files\1cv8\{version}\bin\1cv8.exe")
                else:
                    path = Path(rf"C:\Program Files (x86)\1cv8\{version}\bin\1cv8.exe")
                
                if path.exists():
                    return path
            
            common_paths = [
                Path(r"C:\Program Files\1cv8\common\1cestart.exe"),
                Path(r"C:\Program Files (x86)\1cv8\common\1cestart.exe"),
            ]
            
            for path in common_paths:
                if path.exists():
                    return path
        
        return None

    def save_bases(self):
        """Сохраняет базы в файл ibases.v8i"""
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
                    
                    # Старые поля (для обратной совместимости)
                    if base.usr:
                        f.write(f"Usr={base.usr}\n")
                    if base.pwd:
                        f.write(f"Pwd={base.pwd}\n")
                    
                    # Новые поля для таблицы учетных данных
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

    def _add_bases_to_folder(self, folder_item, folder_path, bases):
        """Добавляет базы в папку, создавая подпапки при необходимости."""
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
            self._add_bases_to_folder(subfolder_item, subfolder_path, subfolders[subfolder_name])
            
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

    def load_bases(self):
        """Загружает базы из файла"""
        reader = BaseReader(IBASES_PATH, ENCODING)
        bases = reader.read_bases()
        
        self.all_bases = bases
        
        self.model.removeRows(0, self.model.rowCount())
        self.bases_dict.clear()
        
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
                root_folders[""].append(base)
        
        for root_folder_name in sorted(root_folders.keys()):
            if not root_folder_name:
                continue
            
            folder_bases = root_folders[root_folder_name]
            
            folder_item = QStandardItem(root_folder_name)
            folder_item.setEditable(False)
            row = [folder_item] + [QStandardItem("") for _ in range(2)]
            self.model.appendRow(row)
            
            self._add_bases_to_folder(folder_item, root_folder_name, folder_bases)

    def expand_recent_and_select_last(self):
        """Раскрывает папку 'Недавние' и устанавливает курсор на последнюю запущенную базу"""
        for folder_idx in range(self.model.rowCount()):
            folder_item = self.model.item(folder_idx, 0)
            if folder_item and "Недавние" in folder_item.text():
                folder_index = self.model.index(folder_idx, 0)
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
                                break
                else:
                    if folder_item.rowCount() > 0:
                        first_db_index = self.model.index(0, 0, folder_index)
                        self.tree.setCurrentIndex(first_db_index)
                        self.tree.scrollTo(first_db_index)
                break
