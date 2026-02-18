"""
Модуль для действий с процессами 1C (активация, закрытие, снятие задачи) и запуск отслеживаемых приложений
"""
import os
import subprocess
from PySide6.QtCore import Qt, QTimer
from services.process_manager import ProcessManager, Process1C
from typing import Optional, Union


class ProcessActions:
    """
    Класс для выполнения действий с процессами 1C и отслеживаемыми приложениями
    """
    
    def __init__(self, window):
        """
        Args:
            window: Главное окно приложения
        """
        self.window = window
    
    def get_selected_process(self) -> Optional[Union[Process1C, object]]:
        """
        Получить выбранный процесс или TrackedApp в дереве
        
        Returns:
            Process1C, TrackedApp или None (возвращает None если выбрана база данных)
        """
        index = self.window.tree.currentIndex()
        if not index.isValid():
            return None
        
        item = self.window.model.itemFromIndex(index)
        if not item:
            return None
        
        data = item.data(Qt.UserRole)
        if not data:
            return None
        
        # Проверяем, что это действительно процесс, а не база данных
        # Process1C - это процесс 1C
        if isinstance(data, Process1C):
            return data
        
        # TrackedApp имеет атрибут is_running
        if hasattr(data, 'is_running'):
            return data
        
        # Если это база данных (Database1C) или что-то другое - возвращаем None
        return None
    
    def activate_process(self, process: Optional[Union[Process1C, object]] = None):
        """
        Активировать окно процесса или запустить приложение (по нажатию Enter)
        
        Args:
            process: Процесс для активации или TrackedApp для запуска, если None - берётся выбранный
        """
        if process is None:
            process = self.get_selected_process()
        
        if not process:
            return
        
        # Проверяем, является ли это TrackedApp
        if hasattr(process, 'is_running'):
            # Это TrackedApp
            tracked_app = process
            if tracked_app.is_running and tracked_app.process:
                # Процесс запущен - активируем
                success = ProcessManager.activate_window(tracked_app.process)
                if success:
                    self.window.statusBar.showMessage(f"✅ Активирован: {tracked_app.process.name}", 3000)
                    # Сохраняем историю
                    if hasattr(self.window, 'last_activated_main_process'):
                        self.window.last_activated_main_process = tracked_app.process
                    # Сворачиваем лончер в трей
                    self.window.minimize_to_tray()
                else:
                    self.window.statusBar.showMessage(f"❌ Не удалось активировать: {tracked_app.process.name}", 3000)
            else:
                # Процесс не запущен - запускаем
                self.launch_application(tracked_app)
        elif isinstance(process, Process1C):
            # Это обычный процесс 1C
            success = ProcessManager.activate_window(process)
            if success:
                self.window.statusBar.showMessage(f"✅ Активирован: {process.name}", 3000)
                # Сохраняем историю: предыдущий становится текущим, а новый - последним
                if hasattr(self.window, 'last_activated_process') and self.window.last_activated_process and self.window.last_activated_process.pid != process.pid:
                    if hasattr(self.window, 'previous_activated_process'):
                        self.window.previous_activated_process = self.window.last_activated_process
                self.window.last_activated_process = process
                # Сворачиваем лончер в трей
                self.window.minimize_to_tray()
            else:
                self.window.statusBar.showMessage(f"❌ Не удалось активировать: {process.name}", 3000)
    
    def launch_application(self, tracked_app):
        """
        Запустить приложение
        
        Args:
            tracked_app: TrackedApp объект с информацией о приложении
        """
        if not tracked_app.launch_path:
            self.window.statusBar.showMessage("❌ Путь запуска не настроен", 3000)
            return
        
        try:
            # Проверяем, существует ли файл (только для полных путей, не для wt.exe)
            if os.path.isabs(tracked_app.launch_path) and not os.path.exists(tracked_app.launch_path):
                self.window.statusBar.showMessage(f"❌ Не найден файл: {tracked_app.launch_path}", 4000)
                return
            
            # Запускаем приложение в отдельном процессе
            if os.name == 'nt':  # Windows
                # Используем subprocess с DETACHED_PROCESS для полной отвязки
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    tracked_app.launch_path,
                    creationflags=DETACHED_PROCESS,
                    shell=True
                )
            else:
                # Для других ОС
                subprocess.Popen([tracked_app.launch_path])
            
            self.window.statusBar.showMessage(f"🚀 Запущено: {tracked_app.display_name}", 3000)
            
            # Обновляем список процессов с задержкой
            QTimer.singleShot(1000, self.window.refresh_main_processes)
            
            # Сворачиваем в трей
            self.window.minimize_to_tray()
            
        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка запуска: {str(e)}", 4000)
    
    def close_process(self, process: Optional[Union[Process1C, object]] = None, force: bool = False):
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
        
        # Если это TrackedApp, получаем его процесс
        if hasattr(process, 'is_running'):
            tracked_app = process
            if not tracked_app.is_running or not tracked_app.process:
                return
            process = tracked_app.process
        
        if not isinstance(process, Process1C):
            return
        
        action_name = "Снята задача" if force else "Закрыто"
        activate_success = ProcessManager.activate_window(process)
        success = ProcessManager.close_process(process, force=force)
        
        if success:
            self.window.statusBar.showMessage(f"✅ {action_name}: {process.name}", 3000)
            
            # Обновляем список процессов с задержкой и восстанавливаем позицию
            # Для force=True - 100мс, для корректного закрытия - 500мс (даём время на завершение)
            delay = 10 if force else 10
            # Проверяем, какой тип процесса
            selected_index = self.window.tree.currentIndex()
            if selected_index.isValid():
                parent_item = self.window.model.itemFromIndex(selected_index.parent())
                if parent_item and "Основное" in parent_item.text():
                    # Основной процесс
                    QTimer.singleShot(delay, self.window.refresh_main_processes)
                else:
                    # Процесс 1С
                    QTimer.singleShot(delay, self.window.refresh_opened_bases)
        else:
            self.window.statusBar.showMessage(f"❌ Не удалось закрыть: {process.name}", 3000)
