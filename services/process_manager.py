"""
Модуль для управления процессами 1cv8.exe и 1cv8c.exe
Позволяет:
- Получать список запущенных процессов 1C
- Активировать окно процесса
- Закрывать процесс корректно или принудительно
"""

import psutil
import win32gui
import win32con
import win32process
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Process1C:
    """
    Представление процесса 1C
    """
    pid: int
    name: str  # Имя окна (как в диспетчере задач)
    hwnd: int  # Handle окна
    
    def __eq__(self, other):
        if not isinstance(other, Process1C):
            return False
        return self.pid == other.pid
    
    def __hash__(self):
        return hash(self.pid)


class ProcessManager:
    """
    Менеджер для работы с процессами 1cv8.exe и 1cv8c.exe
    """
    
    PROCESS_NAMES = ["1cv8.exe", "1cv8c.exe"]
    
    @staticmethod
    def get_running_processes() -> List[Process1C]:
        """
        Получить список всех запущенных процессов 1cv8.exe и 1cv8c.exe
        
        Returns:
            Список Process1C объектов
        """
        processes = []
        
        # Собираем PID всех процессов 1cv8.exe и 1cv8c.exe
        process_pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'].lower() in [name.lower() for name in ProcessManager.PROCESS_NAMES]:
                    process_pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Для каждого PID находим главное окно
        for pid in process_pids:
            window_info = ProcessManager._find_main_window(pid)
            if window_info:
                hwnd, title = window_info
                # Если заголовка нет - отображаем "Без имени"
                base_name = title if title else "Без имени"
                
                # Добавляем префикс: К для Конфигуратора, П для остальных
                if title and "Конфигуратор" in title:
                    display_name = f"К: {base_name}"
                else:
                    display_name = f"П: {base_name}"
                
                processes.append(Process1C(pid=pid, name=display_name, hwnd=hwnd))
        
        return processes
    
    @staticmethod
    def _find_main_window(pid: int) -> Optional[Tuple[int, str]]:
        """
        Найти главное окно процесса
        
        Args:
            pid: ID процесса
            
        Returns:
            (hwnd, title) или None, где title может быть пустой строкой
        """
        result = []
        
        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            if window_pid == pid:
                title = win32gui.GetWindowText(hwnd)
                # Проверяем, что это главное окно (не дочернее)
                # Теперь принимаем окна даже без заголовка
                if win32gui.GetParent(hwnd) == 0:
                    result.append((hwnd, title))
            return True
        
        try:
            win32gui.EnumWindows(callback, None)
            # Возвращаем первое найденное окно
            return result[0] if result else None
        except Exception:
            return None
    
    @staticmethod
    def activate_window(process: Process1C) -> bool:
        """
        Активировать окно процесса (развернуть, если свёрнуто, и переключить фокус)
        
        Args:
            process: Процесс для активации
            
        Returns:
            True если успешно, False в противном случае
        """
        try:
            hwnd = process.hwnd
            
            # Если окно свёрнуто, разворачиваем
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # Переключаем фокус на окно
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            print(f"Ошибка активации окна: {e}")
            return False
    
    @staticmethod
    def close_process(process: Process1C, force: bool = False) -> bool:
        """
        Закрыть процесс
        
        Args:
            process: Процесс для закрытия
            force: Если True - принудительное завершение, иначе - корректное закрытие
            
        Returns:
            True если успешно, False в противном случае
        """
        try:
            proc = psutil.Process(process.pid)
            
            if force:
                # Принудительное завершение
                proc.kill()
            else:
                # Корректное закрытие через окно (WM_CLOSE)
                try:
                    win32gui.PostMessage(process.hwnd, win32con.WM_CLOSE, 0, 0)
                except Exception:
                    # Если не удалось закрыть через окно, пробуем terminate
                    proc.terminate()
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Ошибка закрытия процесса: {e}")
            return False
    
    @staticmethod
    def get_foreground_process() -> Optional[Process1C]:
        """
        Получить текущий активный процесс 1C (если он активен)
        
        Returns:
            Process1C или None
        """
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # Проверяем, является ли этот процесс одним из отслеживаемых
            proc = psutil.Process(pid)
            if proc.name().lower() in [name.lower() for name in ProcessManager.PROCESS_NAMES]:
                title = win32gui.GetWindowText(hwnd)
                # Если заголовка нет - отображаем "Без имени"
                display_name = title if title else "Без имени"
                return Process1C(pid=pid, name=display_name, hwnd=hwnd)
        except Exception:
            pass
        
        return None
