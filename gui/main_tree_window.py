# gui/main_tree_window.py

from PySide6.QtWidgets import (QMainWindow, QTreeView, QVBoxLayout, QWidget, 
                               QStatusBar, QDialog, QVBoxLayout as QVBoxLayoutDialog,
                               QCheckBox, QDialogButtonBox, QLabel, QLineEdit,
                               QFormLayout, QHBoxLayout)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut
from PySide6.QtCore import Qt
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING
import subprocess
import os
from pathlib import Path
import platform
import re


class DatabaseSettingsDialog(QDialog):
    """Диалог настроек базы данных"""
    def __init__(self, parent=None, database=None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle(f"Настройки базы: {database.name if database else ''}")
        self.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Название базы (только для отображения)
        self.name_label = QLabel(database.name if database else "")
        form_layout.addRow("Название:", self.name_label)
        
        # Строка подключения
        self.connect_edit = QLineEdit()
        self.connect_edit.setText(database.connect if database else "")
        form_layout.addRow("Строка подключения:", self.connect_edit)
        
        # Пользователь
        self.user_edit = QLineEdit()
        self.user_edit.setText(database.usr if database and database.usr else "")
        form_layout.addRow("Пользователь:", self.user_edit)
        
        # Пароль
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setText(database.pwd if database and database.pwd else "")
        form_layout.addRow("Пароль:", self.password_edit)
        
        # Версия
        self.version_edit = QLineEdit()
        self.version_edit.setText(database.version if database and database.version else "")
        form_layout.addRow("Версия:", self.version_edit)
        
        # Разрядность
        bitness_layout = QHBoxLayout()
        self.bitness_32 = QCheckBox("32-бит (x86)")
        self.bitness_64 = QCheckBox("64-бит (x64)")
        
        # Устанавливаем текущее значение
        if database:
            if database.app_arch == 'x86_64':
                self.bitness_64.setChecked(True)
            else:
                self.bitness_32.setChecked(True)
        else:
            self.bitness_32.setChecked(True)
        
        # Взаимоисключающие чекбоксы
        self.bitness_32.toggled.connect(lambda checked: self.bitness_64.setChecked(not checked) if checked else None)
        self.bitness_64.toggled.connect(lambda checked: self.bitness_32.setChecked(not checked) if checked else None)
        
        bitness_layout.addWidget(self.bitness_32)
        bitness_layout.addWidget(self.bitness_64)
        bitness_layout.addStretch()
        
        form_layout.addRow("Разрядность:", bitness_layout)
        
        # Путь к 1cv8.exe (опционально)
        self.app_edit = QLineEdit()
        self.app_edit.setText(database.app if database and database.app else "")
        self.app_edit.setPlaceholderText("Оставьте пустым для автоопределения")
        form_layout.addRow("Путь к 1cv8.exe:", self.app_edit)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_settings(self):
        """Возвращает настройки в виде словаря"""
        return {
            'connect': self.connect_edit.text(),
            'usr': self.user_edit.text() if self.user_edit.text() else None,
            'pwd': self.password_edit.text() if self.password_edit.text() else None,
            'version': self.version_edit.text() if self.version_edit.text() else None,
            'app_arch': 'x86_64' if self.bitness_64.isChecked() else 'x86',
            'app': self.app_edit.text() if self.app_edit.text() else None
        }


class TreeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Дерево баз 1С")
        self.resize(900, 600)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        self.bases_dict = {}  # Словарь для быстрого поиска баз по индексу
        self.all_bases = []   # Список всех баз в памяти

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            "Имя базы", "Папка", "Тип подключения", "Connect", "Версия"
        ])
        
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        # Настройка горячих клавиш
        self.setup_shortcuts()
        
        self.load_bases()

    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # F3 - открытие базы
        self.shortcut_f3 = QShortcut(QKeySequence("F3"), self)
        self.shortcut_f3.activated.connect(self.open_database)
        
        # F4 - запуск конфигуратора
        self.shortcut_f4 = QShortcut(QKeySequence("F4"), self)
        self.shortcut_f4.activated.connect(self.open_configurator)
        
        # Ctrl+C - копирование строки подключения
        self.shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        self.shortcut_copy.activated.connect(self.copy_connection_string)
        
        # Ctrl+E - настройки базы
        self.shortcut_settings = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_settings.activated.connect(self.edit_database_settings)

    def get_selected_database(self):
        """Получить выбранную базу данных"""
        indexes = self.tree.selectedIndexes()
        if not indexes:
            self.statusBar.showMessage("⚠️ Выберите базу данных")
            return None
        
        # Берем первую ячейку выбранной строки
        index = indexes[0]
        
        # Если это папка (родительский элемент), игнорируем
        if not index.parent().isValid() and index.row() in [i for i in range(self.model.rowCount())]:
            self.statusBar.showMessage("⚠️ Выберите базу, а не папку")
            return None
        
        # Получаем индекс базы из словаря
        row = index.row()
        parent_row = index.parent().row() if index.parent().isValid() else -1
        
        key = (parent_row, row)
        return self.bases_dict.get(key)

    def _parse_server_connect_string(self, connect_string):
        """
        Парсит строку подключения серверной базы и преобразует её в формат для /S параметра.
        
        Пример:
        Вход: Srvr="srv-1c-8323:1541";Ref="AstorCO_1017_Pechericadv_2";
        Выход: srv-1c-8323:1541\AstorCO_1017_Pechericadv_2
        """
        try:
            # Ищем Srvr="..." и Ref="..."
            srvr_match = re.search(r'Srvr="([^"]+)"', connect_string, re.IGNORECASE)
            ref_match = re.search(r'Ref="([^"]+)"', connect_string, re.IGNORECASE)
            
            if srvr_match and ref_match:
                server = srvr_match.group(1)
                ref = ref_match.group(1)
                return f"{server}\\{ref}"
            
            # Если не нашли оба параметра, возвращаем исходную строку
            return connect_string
            
        except Exception as e:
            print(f"Ошибка парсинга строки подключения: {e}")
            return connect_string

    def _launch_1c_process(self, executable, mode, database):
        """
        Универсальный метод запуска 1С
        mode: 'ENTERPRISE' или 'DESIGNER'
        """
        try:
            # Формируем параметры командной строки
            params = [mode]
            
            # Добавляем строку подключения
            if database.connect:
                # Парсим строку подключения для серверных баз
                parsed_connect = self._parse_server_connect_string(database.connect)
                params.append(f'/S"{parsed_connect}"')
            
            # Добавляем пользователя, если задан
            if database.usr:
                params.append(f"/N{database.usr}")
            
            # Добавляем пароль, если задан
            if database.pwd:
                params.append(f"/P{database.pwd}")
            
            # Собираем полную команду
            cmd_line = f'"{executable}" ' + ' '.join(f'"{p}"' if ' ' in p and not p.startswith('/') else p for p in params)
            
            # Выводим команду в консоль для отладки
            print("\n" + "="*80)
            print(f"КОМАНДА ЗАПУСКА 1С ({mode}):")
            print(cmd_line)
            print("="*80 + "\n")
            
            if platform.system() == 'Windows':
                # МЕТОД 1: Используем os.startfile (работает как двойной клик в проводнике)
                try:
                    # Создаем временный .bat файл для запуска
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False, encoding='cp866') as bat_file:
                        bat_file.write('@echo off\n')
                        bat_file.write(f'start "" {cmd_line}\n')
                        bat_file.write('exit\n')
                        bat_path = bat_file.name
                    
                    # Запускаем bat-файл через os.startfile
                    os.startfile(bat_path)
                    
                    # Удаляем временный файл через несколько секунд
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(3000, lambda: self._cleanup_temp_file(bat_path))
                    
                    return True
                    
                except Exception as e:
                    print(f"МЕТОД 1 (os.startfile) не сработал: {e}")
                    
                    # МЕТОД 2: Используем subprocess с правильными флагами
                    try:
                        # Используем shell=True для правильной обработки параметров
                        subprocess.Popen(
                            cmd_line,
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB
                        )
                        return True
                    except Exception as e2:
                        print(f"МЕТОД 2 (subprocess с shell) не сработал: {e2}")
                        
                        # МЕТОД 3: Прямой запуск через subprocess без DETACHED_PROCESS
                        try:
                            command = [str(executable)] + params
                            subprocess.Popen(
                                command,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NEW_CONSOLE
                            )
                            return True
                        except Exception as e3:
                            print(f"МЕТОД 3 (subprocess без detached) не сработал: {e3}")
                            raise e3
            else:
                # Для Linux/Mac
                command = [str(executable)] + params
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                return True
                
        except Exception as e:
            print(f"ВСЕ МЕТОДЫ ЗАПУСКА НЕ СРАБОТАЛИ: {e}")
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
            self.statusBar.showMessage(f"✅ База {database.name} запущена")
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
            self.statusBar.showMessage(f"✅ Конфигуратор для {database.name} запущен")
        else:
            self.statusBar.showMessage(f"❌ Ошибка при запуске конфигуратора для {database.name}")

    def copy_connection_string(self):
        """Копировать строку подключения (Ctrl+C)"""
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

    def edit_database_settings(self):
        """Редактировать настройки базы (Ctrl+E)"""
        database = self.get_selected_database()
        if not database:
            return
        
        dialog = DatabaseSettingsDialog(self, database)
        
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            
            # Обновляем настройки базы
            database.connect = settings['connect']
            database.usr = settings['usr']
            database.pwd = settings['pwd']
            database.version = settings['version']
            database.app_arch = settings['app_arch']
            database.app = settings['app']
            
            # Сохраняем изменения
            self.save_bases()
            
            # Перезагружаем дерево
            self.load_bases()
            
            self.statusBar.showMessage(f"✅ Настройки базы {database.name} сохранены")

    def _get_1c_executable(self, database):
        """Определяет путь к исполняемому файлу 1C с учетом разрядности"""
        # Определяем разрядность (по умолчанию 32-бит)
        bitness = database.app_arch or 'x86'
        
        # Если указан пользовательский путь
        if database.app:
            path = Path(database.app)
            if path.exists():
                return path
        
        # Стандартные пути для Windows
        if platform.system() == 'Windows':
            # Для версий ищем в Program Files
            if database.version:
                version = database.version
                if bitness == 'x86_64':
                    # 64-битная версия
                    path = Path(rf"C:\Program Files\1cv8\{version}\bin\1cv8.exe")
                else:
                    # 32-битная версия
                    path = Path(rf"C:\Program Files (x86)\1cv8\{version}\bin\1cv8.exe")
                
                if path.exists():
                    return path
            
            # Общие пути
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
            # Записываем базы из памяти, а не перечитываем из файла
            with open(IBASES_PATH, 'w', encoding=ENCODING) as f:
                for base in self.all_bases:
                    f.write(f"[{base.name}]\n")
                    f.write(f"ID={base.id}\n")
                    f.write(f"Connect={base.connect}\n")
                    f.write(f"Folder={base.folder}\n")
                    
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
                    
                    f.write("\n")
            
        except Exception as e:
            self.statusBar.showMessage(f"❌ Ошибка сохранения: {e}")

    def load_bases(self):
        """Загружает базы из файла"""
        from collections import defaultdict
        reader = BaseReader(IBASES_PATH, ENCODING)
        bases = reader.read_bases()
        
        # Сохраняем список баз в памяти
        self.all_bases = bases
        
        self.model.removeRows(0, self.model.rowCount())
        self.bases_dict.clear()
        
        folders = defaultdict(list)
        for base in bases:
            folder = base.get_folder_path()
            folders[folder].append(base)
        
        for folder_idx, (folder, dbases) in enumerate(folders.items()):
            folder_item = QStandardItem(folder)
            folder_item.setEditable(False)
            row = [folder_item] + [QStandardItem("") for _ in range(4)]
            self.model.appendRow(row)
            
            for db_idx, base in enumerate(dbases):
                # Сохраняем ссылку на базу
                self.bases_dict[(folder_idx, db_idx)] = base
                
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