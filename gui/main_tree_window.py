# gui/main_tree_window.py

from PySide6.QtWidgets import (QMainWindow, QTreeView, QVBoxLayout, QWidget, 
                               QStatusBar, QDialog, QVBoxLayout as QVBoxLayoutDialog,
                               QCheckBox, QDialogButtonBox, QLabel, QLineEdit,
                               QFormLayout, QHBoxLayout, QTextEdit, QPushButton)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut
from PySide6.QtCore import Qt
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING
import subprocess
import os
from pathlib import Path
import platform
import re
import uuid
from datetime import datetime


class HelpDialog(QDialog):
    """Диалог помощи по горячим клавишам"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка по горячим клавишам")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("<h2>Горячие клавиши</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Текстовое поле с подсказками
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <style>
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; font-weight: bold; }
            tr:hover { background-color: #f5f5f5; }
            .key { font-weight: bold; color: #0066cc; }
        </style>
        <table>
            <tr>
                <th>Клавиша</th>
                <th>Действие</th>
            </tr>
            <tr>
                <td><span class="key">F1</span></td>
                <td>Показать это окно справки</td>
            </tr>
            <tr>
                <td><span class="key">F3</span></td>
                <td>Открыть выбранную базу данных (режим предприятия)</td>
            </tr>
            <tr>
                <td><span class="key">F4</span></td>
                <td>Открыть конфигуратор для выбранной базы</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+C</span></td>
                <td>Скопировать строку подключения в буфер обмена</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+D</span></td>
                <td>Копировать выбранную базу (создать дубликат)</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+E</span></td>
                <td>Редактировать настройки выбранной базы</td>
            </tr>
            <tr>
                <td><span class="key">Esc</span></td>
                <td>Выход из программы</td>
            </tr>
        </table>
        <br>
        <p><b>Примечание:</b> Для работы горячих клавиш (кроме Esc) необходимо выбрать базу данных в дереве, а не папку.</p>
        <p><b>Копирование базы (Ctrl+D):</b> Создаёт копию выбранной базы с новым ID. К имени исходной базы добавляется текущая дата.</p>
        """)
        layout.addWidget(help_text)
        
        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)


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
        
        # Папка
        self.folder_edit = QLineEdit()
        self.folder_edit.setText(database.folder if database else "")
        self.folder_edit.setPlaceholderText("Например: /Тестовые")
        form_layout.addRow("Папка:", self.folder_edit)
        
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
            'folder': self.folder_edit.text(),
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
        self.resize(1100, 600)  # Увеличена ширина с 900 до 1100
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        self.bases_dict = {}  # Словарь для быстрого поиска баз по индексу
        self.all_bases = []   # Список всех баз в памяти
        self.last_launched_db = None  # Последняя запущенная база

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            "Имя базы", "Connect", "Версия"
        ])
        
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        
        # Устанавливаем ширину колонок
        self.tree.setColumnWidth(0, 350)  # Имя базы - увеличенная ширина
        self.tree.setColumnWidth(1, 450)  # Connect - увеличенная ширина
        self.tree.setColumnWidth(2, 100)  # Версия
        
        layout = QVBoxLayout()
        layout.addWidget(self.tree)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        # Настройка горячих клавиш
        self.setup_shortcuts()
        
        self.load_bases()
        
        # Раскрываем папку "Недавние" и устанавливаем курсор на последнюю запущенную базу
        self.expand_recent_and_select_last()

    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # F1 - помощь по горячим клавишам
        self.shortcut_f1 = QShortcut(QKeySequence("F1"), self)
        self.shortcut_f1.activated.connect(self.show_help)
        
        # F3 - открытие базы
        self.shortcut_f3 = QShortcut(QKeySequence("F3"), self)
        self.shortcut_f3.activated.connect(self.open_database)
        
        # F4 - запуск конфигуратора
        self.shortcut_f4 = QShortcut(QKeySequence("F4"), self)
        self.shortcut_f4.activated.connect(self.open_configurator)
        
        # Ctrl+C - копирование строки подключения
        self.shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        self.shortcut_copy.activated.connect(self.copy_connection_string)
        
        # Ctrl+D - копирование базы
        self.shortcut_duplicate = QShortcut(QKeySequence("Ctrl+D"), self)
        self.shortcut_duplicate.activated.connect(self.duplicate_database)
        
        # Ctrl+E - настройки базы
        self.shortcut_settings = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_settings.activated.connect(self.edit_database_settings)
        
        # Esc - выход из программы
        self.shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        self.shortcut_esc.activated.connect(self.close)

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

    def _build_launch_command(self, executable, mode, database):
        """
        Формирует командную строку для запуска 1С
        mode: 'ENTERPRISE' или 'DESIGNER'
        Возвращает строку команды
        """
        try:
            # Формируем параметры командной строки
            params = [mode]
            
            if database.connect:
                # Парсим строку подключения для серверных баз
                parsed_connect = self._parse_server_connect_string(database.connect)
                params.append(f'/S"{parsed_connect}"')
            
            # Добавляем пользователя, если задан
            if database.usr:
                params.append(f'/N"{database.usr}"')
            if database.pwd:
                params.append(f'/P"{database.pwd}"')
            
            # Собираем полную команду
            cmd_line = f'"{executable}" ' + ' '.join(f'"{p}"' if ' ' in p and not p.startswith('/') else p for p in params)
            
            return cmd_line
            
        except Exception as e:
            print(f"Ошибка формирования командной строки: {e}")
            return None

    def _launch_1c_process(self, executable, mode, database):
        """
        Запуск 1С через BAT-файл
        mode: 'ENTERPRISE' или 'DESIGNER'
        """
        try:
            cmd_line = self._build_launch_command(executable, mode, database)
            
            if not cmd_line:
                return False
            
            # Выводим строку запуска в статус бар
            self.statusBar.showMessage(f"Запуск: {cmd_line}")
            
            # Создаем временный BAT-файл и запускаем через него
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False, encoding='cp866') as bat_file:
                bat_file.write('@echo off\n')
                bat_file.write(f'start "" {cmd_line}\n')
                bat_file.write('exit\n')
                bat_path = bat_file.name
            
            os.startfile(bat_path)
            
            # Удаляем временный файл через 3 секунды
            from PySide6.QtCore import QTimer
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
        # Сохраняем оригинальную папку, если еще не сохранена
        if not database.is_recent and not database.original_folder:
            database.original_folder = database.folder
        
        # Помечаем базу как недавнюю
        database.is_recent = True
        
        # Устанавливаем время последнего запуска
        database.last_run_time = datetime.now()
        
        # Удаляем базу из текущей позиции в списке
        if database in self.all_bases:
            self.all_bases.remove(database)
        
        # Вставляем базу в начало списка
        self.all_bases.insert(0, database)
        
        # Сохраняем изменения в файл
        self.save_bases()
        
        # Запоминаем последнюю запущенную базу
        self.last_launched_db = database

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
            # Помечаем базу как недавнюю
            self._move_to_recent(database)
            # Перезагружаем дерево
            self.load_bases()
            # Раскрываем "Недавние" и выделяем базу
            self.expand_recent_and_select_last()
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
            # Помечаем базу как недавнюю
            self._move_to_recent(database)
            # Перезагружаем дерево
            self.load_bases()
            # Раскрываем "Недавние" и выделяем базу
            self.expand_recent_and_select_last()
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
            # Создаем копию базы с новым ID
            from models.database import Database1C
            
            new_database = Database1C(
                id=str(uuid.uuid4()),  # Новый UUID
                name=database.name,  # Сохраняем имя
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
                last_run_time=None  # Сбрасываем время запуска для копии
            )
            
            # Добавляем текущую дату к имени исходной базы
            current_date = datetime.now().strftime("%Y-%m-%d")
            database.name = f"{database.name} {current_date}"
            
            # Добавляем новую базу в список после исходной
            index = self.all_bases.index(database)
            self.all_bases.insert(index + 1, new_database)
            
            # Сохраняем изменения
            self.save_bases()
            
            # Перезагружаем дерево
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
        
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            
            # Обновляем настройки базы
            database.folder = settings['folder']
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
            # Записываем базы из памяти
            with open(IBASES_PATH, 'w', encoding=ENCODING) as f:
                for base in self.all_bases:
                    f.write(f"[{base.name}]\n")
                    f.write(f"ID={base.id}\n")
                    f.write(f"Connect={base.connect}\n")
                    f.write(f"Folder={base.folder}\n")
                    
                    # Добавляем тег IsRecent (OriginalFolder НЕ сохраняем в файл)
                    if base.is_recent:
                        f.write(f"IsRecent=1\n")
                    
                    # Сохраняем LastRunTime в формате ISO 8601
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
            # Используем get_display_folder() для отображения в дереве
            folder = base.get_display_folder()
            folders[folder].append(base)
        
        for folder_idx, (folder, dbases) in enumerate(folders.items()):
            folder_item = QStandardItem(folder)
            folder_item.setEditable(False)
            row = [folder_item] + [QStandardItem("") for _ in range(2)]
            self.model.appendRow(row)
            
            for db_idx, base in enumerate(dbases):
                # Сохраняем ссылку на базу
                self.bases_dict[(folder_idx, db_idx)] = base
                
                vers = base.get_full_version()
                row = [
                    QStandardItem(base.name),
                    QStandardItem(base.connect),
                    QStandardItem(vers)
                ]
                for item in row:
                    item.setEditable(False)
                folder_item.appendRow(row)

        self.statusBar.showMessage(f"Найдено баз: {sum(len(v) for v in folders.values())}")

    def expand_recent_and_select_last(self):
        """Раскрывает папку 'Недавние' и устанавливает курсор на последнюю запущенную базу"""
        # Ищем папку "Недавние"
        for folder_idx in range(self.model.rowCount()):
            folder_item = self.model.item(folder_idx, 0)
            if folder_item and "Недавние" in folder_item.text():
                # Раскрываем папку
                folder_index = self.model.index(folder_idx, 0)
                self.tree.expand(folder_index)
                
                # Если есть последняя запущенная база, выделяем её
                if self.last_launched_db:
                    # Ищем базу в папке "Недавние"
                    for db_idx in range(folder_item.rowCount()):
                        db_item = folder_item.child(db_idx, 0)
                        if db_item and db_item.text() == self.last_launched_db.name:
                            # Выделяем базу
                            db_index = self.model.index(db_idx, 0, folder_index)
                            self.tree.setCurrentIndex(db_index)
                            self.tree.scrollTo(db_index)
                            break
                else:
                    # Если нет последней запущенной базы, выделяем первую в "Недавние"
                    if folder_item.rowCount() > 0:
                        first_db_index = self.model.index(0, 0, folder_index)
                        self.tree.setCurrentIndex(first_db_index)
                        self.tree.scrollTo(first_db_index)
                break
