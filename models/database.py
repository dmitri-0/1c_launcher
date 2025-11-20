from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Database1C:
    """Модель базы данных 1С"""
    id: str
    name: str  # Название из секции [Название]
    folder: str  # Папка из поля Folder
    connect: str  # Строка подключения
    app: Optional[str] = None
    version: Optional[str] = None
    app_arch: Optional[str] = None  # Разрядность: x86 или x86_64
    order_in_tree: Optional[float] = None  # Порядок в дереве
    usr: Optional[str] = None  # Имя пользователя
    pwd: Optional[str] = None  # Пароль
    original_folder: Optional[str] = None  # Оригинальная папка (только в памяти, не сохраняется)
    is_recent: bool = False  # Флаг принадлежности к "Недавним"
    last_run_time: Optional[datetime] = None  # Время последнего запуска для сортировки недавних
    
    def __str__(self):
        return self.name
    
    def is_database(self) -> bool:
        """
        Проверяет, является ли запись базой данных.
        База данных должна иметь непустую строку подключения (Connect).
        Если Connect пустой или отсутствует - это структурная папка.
        """
        return bool(self.connect and self.connect.strip())
    
    def get_connection_type(self):
        """Определяет тип подключения: File или Srvr"""
        if 'File=' in self.connect:
            return 'Файловая'
        elif 'Srvr=' in self.connect:
            return 'Клиент-серверная'
        return 'Неизвестно'
    
    def get_full_version(self) -> str:
        """Возвращает версию с разрядностью"""
        if not self.version:
            return '-'
        
        version_str = self.version
        if self.app_arch:
            arch_display = 'x64' if self.app_arch == 'x86_64' else 'x86'
            version_str += f" ({arch_display})"
        
        return version_str
    
    def get_folder_path(self) -> str:
        """Возвращает путь к папке (без начального слэша)"""
        folder = self.folder.strip()
        if folder.startswith('/'):
            folder = folder[1:]
        return folder if folder else 'Без папки'
    
    def get_display_folder(self) -> str:
        """Возвращает папку для отображения в дереве"""
        # Если база помечена как недавняя, показываем "Недавние"
        if self.is_recent:
            return "Недавние"
        return self.get_folder_path()
