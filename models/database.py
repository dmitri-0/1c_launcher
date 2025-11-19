from dataclasses import dataclass
from typing import Optional

@dataclass
class Database1C:
    """Модель базы данных 1С"""
    id: str
    name: str
    folder: str
    connect: str
    app: Optional[str] = None
    version: Optional[str] = None
    
    def __str__(self):
        return f"{self.name} ({self.folder})"
    
    def get_connection_type(self):
        """Определяет тип подключения: File или Srvr"""
        if 'File=' in self.connect:
            return 'Файловая'
        elif 'Srvr=' in self.connect:
            return 'Клиент-серверная'
        return 'Неизвестно'
