"""
Модуль для действий с процессами 1C (активация, закрытие, снятие задачи)
"""
from PySide6.QtCore import Qt
from services.process_manager import ProcessManager, Process1C
from typing import Optional


class ProcessActions:
    """
    Класс для выполнения действий с процессами 1C
    """
    
    def __init__(self, window):
        """
        Args:
            window: Главное окно приложения
        """
        self.window = window
    
    def get_selected_process(self) -> Optional[Process1C]:
        """
        Получить выбранный процесс в дереве
        
        Returns:
            Process1C или None
        """
        index = self.window.tree.currentIndex()
        if not index.isValid():
            return None
        
        item = self.window.model.itemFromIndex(index)
        if not item:
            return None
        
        data = item.data(Qt.UserRole)
        if isinstance(data, Process1C):
            return data
        
        return None
    
    def activate_process(self, process: Optional[Process1C] = None):
        """
        Активировать окно процесса (по нажатию Enter)
        
        Args:
            process: Процесс для активации, если None - берётся выбранный
        """
        if process is None:
            process = self.get_selected_process()
        
        if not process:
            return
        
        success = ProcessManager.activate_window(process)
        if success:
            self.window.statusBar.showMessage(f"✅ Активирован: {process.name}", 3000)
            # Сохраняем последний активированный процесс
            self.window.last_activated_process = process
            # Сворачиваем лончер в трей
            self.window.minimize_to_tray()
        else:
            self.window.statusBar.showMessage(f"❌ Не удалось активировать: {process.name}", 3000)
    
    def close_process(self, process: Optional[Process1C] = None, force: bool = False):
        """
        Закрыть процесс
        
        Args:
            process: Процесс для закрытия
            force: True - принудительное завершение (Shift+Del), False - корректное (Del)
        """
        if process is None:
            process = self.get_selected_process()
        
        if not process:
            return
        
        action_name = "Снята задача" if force else "Закрыто"
        success = ProcessManager.close_process(process, force=force)
        
        if success:
            self.window.statusBar.showMessage(f"✅ {action_name}: {process.name}", 3000)
            # Обновляем список процессов
            self.window.refresh_opened_bases()
        else:
            self.window.statusBar.showMessage(f"❌ Не удалось закрыть: {process.name}", 3000)
