import subprocess
import platform
from pathlib import Path
from typing import Optional
from models.database import Database1C


class BaseLauncher:
    """Сервис для запуска баз 1С"""
    
    def __init__(self):
        self.platform = platform.system()
    
    def launch_database(self, database: Database1C, debug_mode: bool = False) -> bool:
        """
        Запускает базу данных 1С
        
        Args:
            database: Объект базы данных
            debug_mode: Режим отладки (отключение защиты от опасных действий + привилегированный режим)
            
        Returns:
            True если запуск прошел успешно, False в противном случае
        """
        try:
            # Получаем путь к 1cv8.exe или используем заданный в конфиге
            executable = self._get_1c_executable(database.app)
            
            if not executable:
                print("❌ Не удалось найти исполняемый файл 1C")
                return False
            
            # Формируем команду запуска
            command = [str(executable), "ENTERPRISE", f"/IBConnectionString{database.connect}"]
            
            # В режиме отладки добавляем параметры для отключения защиты и привилегированного режима
            if debug_mode:
                command.append("/DisableUnsafeActionProtection")
                command.append("/AllowExecuteScheduledJobs")
            
            # Запускаем процесс
            subprocess.Popen(command, 
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=subprocess.DETACHED_PROCESS if self.platform == 'Windows' else 0)
            
            mode_info = " (режим отладки)" if debug_mode else ""
            print(f"✅ База {database.name} запущена{mode_info}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при запуске базы: {e}")
            return False
    
    def _get_1c_executable(self, custom_path: Optional[str] = None) -> Optional[Path]:
        """
        Определяет путь к исполняемому файлу 1C
        
        Args:
            custom_path: Пользовательский путь к 1cv8.exe
            
        Returns:
            Path к 1cv8.exe или None
        """
        # Если указан пользовательский путь
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                return path
        
        # Стандартные пути для Windows
        if self.platform == 'Windows':
            common_paths = [
                Path(r"C:\Program Files\1cv8\common\1cestart.exe"),
                Path(r"C:\Program Files (x86)\1cv8\common\1cestart.exe"),
            ]
            
            for path in common_paths:
                if path.exists():
                    return path
        
        return None
    
    def get_connection_string(self, database: Database1C) -> str:
        """
        Возвращает строку подключения базы
        
        Args:
            database: Объект базы данных
            
        Returns:
            Строка подключения
        """
        return database.connect
