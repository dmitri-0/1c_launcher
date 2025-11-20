"""Диалог настроек базы данных"""

import re
import platform
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QComboBox
)


class DatabaseSettingsDialog(QDialog):
    """Диалог настроек базы данных"""
    def __init__(self, parent=None, database=None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle(f"Настройки базы: {database.name if database else 'Новая база'}")
        self.setMinimumWidth(600)
        
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
        
        # Пользователь
        self.user_edit = QLineEdit()
        self.user_edit.setText(database.usr if database and database.usr else "")
        form_layout.addRow("Пользователь:", self.user_edit)
        
        # Пароль
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setText(database.pwd if database and database.pwd else "")
        form_layout.addRow("Пароль:", self.password_edit)
        
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
            'usr': self.user_edit.text() if self.user_edit.text() else None,
            'pwd': self.password_edit.text() if self.password_edit.text() else None,
            'version': version if version else None,
            'app_arch': app_arch,
            'app': self.app_edit.text() if self.app_edit.text() else None
        }
