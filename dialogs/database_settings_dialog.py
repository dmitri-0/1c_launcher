"""Диалог настроек базы данных"""

import re
import platform
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel
)


class DatabaseSettingsDialog(QDialog):
    """Диалог настроек базы данных"""
    def __init__(self, parent=None, database=None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle(f"Настройки базы: {database.name if database else 'Новая база'}")
        self.setMinimumWidth(700)
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Название базы (теперь можно редактировать)
        self.name_edit = QLineEdit()
        self.name_edit.setText(database.name if database else "")
        self.name_edit.setPlaceholderText("Введите название базы")
        form_layout.addRow("Название:", self.name_edit)
        
        # Папка
        self.folder_edit = QLineEdit()
        self.folder_edit.setText(database.folder if database else "")
        self.folder_edit.setPlaceholderText("Например: /Тестовые или /Рабочие/Магазины")
        form_layout.addRow("Папка:", self.folder_edit)
        
        # Строка подключения
        self.connect_edit = QLineEdit()
        self.connect_edit.setText(database.connect if database else "")
        form_layout.addRow("Строка подключения:", self.connect_edit)
        
        # Путь к хранилищу
        self.storage_path_edit = QLineEdit()
        self.storage_path_edit.setText(
            database.storage_path if database and database.storage_path else ""
        )
        self.storage_path_edit.setPlaceholderText("tcp://server/repo")
        form_layout.addRow("Путь к хранилищу:", self.storage_path_edit)
        
        # Версия - выпадающий список с разрядностью
        self.version_combo = QComboBox()
        self.version_combo.setEditable(True)  # Позволяет вводить свою версию
        
        # Получаем список установленных версий
        installed_versions = self._get_installed_versions()
        if installed_versions:
            self.version_combo.addItems(installed_versions)
        
        # Устанавливаем текущее значение
        if database and database.version:
            # Формируем строку версии с разрядностью
            arch_display = 'x64' if database.app_arch == 'x86_64' else 'x86'
            version_with_arch = f"{database.version} ({arch_display})"
            
            # Проверяем, есть ли такая версия в списке
            index = self.version_combo.findText(version_with_arch)
            if index >= 0:
                self.version_combo.setCurrentIndex(index)
            else:
                # Если версии нет в списке, добавляем её
                self.version_combo.addItem(version_with_arch)
                self.version_combo.setCurrentText(version_with_arch)
        
        form_layout.addRow("Версия:", self.version_combo)
        
        # Путь к 1cv8.exe (опционально)
        self.app_edit = QLineEdit()
        self.app_edit.setText(database.app if database and database.app else "")
        self.app_edit.setPlaceholderText("Оставьте пустым для автоопределения")
        form_layout.addRow("Путь к 1cv8.exe:", self.app_edit)
        
        layout.addLayout(form_layout)
        
        # Таблица учетных данных
        credentials_label = QLabel("Учетные данные:")
        layout.addWidget(credentials_label)
        
        self.credentials_table = QTableWidget(2, 3)  # 2 строки, 3 колонки
        self.credentials_table.setHorizontalHeaderLabels([
            "Предприятие", "Конфигуратор", "Хранилище"
        ])
        self.credentials_table.setVerticalHeaderLabels([
            "Пользователь", "Пароль"
        ])
        
        # Настраиваем растягивание колонок
        header = self.credentials_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        # Устанавливаем высоту таблицы
        self.credentials_table.setMaximumHeight(120)
        
        # Заполняем таблицу существующими данными
        if database:
            # Предприятие
            self.credentials_table.setItem(0, 0, QTableWidgetItem(
                database.usr_enterprise or ""
            ))
            self.credentials_table.setItem(1, 0, QTableWidgetItem(
                database.pwd_enterprise or ""
            ))
            
            # Конфигуратор
            self.credentials_table.setItem(0, 1, QTableWidgetItem(
                database.usr_configurator or ""
            ))
            self.credentials_table.setItem(1, 1, QTableWidgetItem(
                database.pwd_configurator or ""
            ))
            
            # Хранилище
            self.credentials_table.setItem(0, 2, QTableWidgetItem(
                database.usr_storage or ""
            ))
            self.credentials_table.setItem(1, 2, QTableWidgetItem(
                database.pwd_storage or ""
            ))
        else:
            # Инициализируем пустые ячейки для новой базы
            for row in range(2):
                for col in range(3):
                    self.credentials_table.setItem(row, col, QTableWidgetItem(""))
        
        layout.addWidget(self.credentials_table)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def _get_installed_versions(self):
        """Получает список установленных версий 1С из системы"""
        versions = []
        
        if platform.system() == 'Windows':
            # Проверяем оба пути - Program Files и Program Files (x86)
            base_paths = [
                (Path(r"C:\Program Files\1cv8"), "x64"),
                (Path(r"C:\Program Files (x86)\1cv8"), "x86")
            ]
            
            for base_path, bitness in base_paths:
                if base_path.exists():
                    # Ищем все подпапки с версиями
                    for item in base_path.iterdir():
                        if item.is_dir() and item.name != 'common':
                            # Проверяем наличие bin/1cv8.exe
                            exe_path = item / 'bin' / '1cv8.exe'
                            if exe_path.exists():
                                # Добавляем версию с пометкой разрядности
                                version_str = f"{item.name} ({bitness})"
                                if version_str not in versions:
                                    versions.append(version_str)
        
        # Сортируем версии в обратном порядке (новые первыми)
        versions.sort(reverse=True)
        
        return versions
    
    def get_settings(self):
        """Возвращает настройки в виде словаря"""
        # Извлекаем версию и разрядность из комбобокса
        version_text = self.version_combo.currentText()
        
        # Парсим версию и разрядность
        # Формат: "8.3.23.2040 (x86)" или "8.3.23.2040 (x64)"
        version = version_text
        app_arch = 'x86'  # по умолчанию
        
        # Ищем разрядность в скобках
        match = re.search(r'\(\s*(x86|x64)\s*\)\s*$', version_text)
        if match:
            arch_str = match.group(1)
            app_arch = 'x86_64' if arch_str == 'x64' else 'x86'
            # Убираем разрядность из версии
            version = version_text[:match.start()].strip()
        
        return {
            'name': self.name_edit.text(),
            'folder': self.folder_edit.text(),
            'connect': self.connect_edit.text(),
            'version': version if version else None,
            'app_arch': app_arch,
            'app': self.app_edit.text() if self.app_edit.text() else None,
            'storage_path': self.storage_path_edit.text() if self.storage_path_edit.text() else None,
            # Данные из таблицы
            'usr_enterprise': self.credentials_table.item(0, 0).text() or None,
            'pwd_enterprise': self.credentials_table.item(1, 0).text() or None,
            'usr_configurator': self.credentials_table.item(0, 1).text() or None,
            'pwd_configurator': self.credentials_table.item(1, 1).text() or None,
            'usr_storage': self.credentials_table.item(0, 2).text() or None,
            'pwd_storage': self.credentials_table.item(1, 2).text() or None,
        }
