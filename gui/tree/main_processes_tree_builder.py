"""
Модуль для построения модели "Основное" (отслеживаемые приложения) для дерева
Приложения всегда отображаются: либо как запущенные процессы, либо как варианты для запуска
"""
from dataclasses import dataclass
from typing import Optional
from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt
from services.process_manager import ProcessManager
from config import TRACKED_APPLICATIONS, get_launch_path


@dataclass
class TrackedApp:
    """
    Представление отслеживаемого приложения
    Может быть либо запущенным процессом, либо опцией для запуска
    """
    process_name: str
    display_name: str
    icon: str
    launch_path: str
    process: Optional[object] = None  # Process1C объект, если процесс запущен
    is_running: bool = False


class MainProcessesTreeBuilder:
    NODE_NAME = "Основное"

    def __init__(self, model):
        self.model = model
        self.folder_item = None

    def build_tree(self):
        """
        Создает/обновляет ветку "Основное" со всеми отслеживаемыми приложениями
        Приложения всегда показываются: либо как запущенные процессы, либо как варианты для запуска
        Возвращает кортеж (folder_item, process_count) для последующего объединения ячеек
        """
        # Ищем, удаляем старую папку если уже есть
        root = self.model
        for i in range(root.rowCount()):
            item = root.item(i, 0)
            if item and item.text() == self.NODE_NAME:
                root.removeRow(i)
                break
        
        # Создаем папку
        self.folder_item = QStandardItem(self.NODE_NAME)
        self.folder_item.setEditable(False)
        self.folder_item.setData(None, Qt.UserRole)  # Отметка, что это не база ibases

        # Получаем список запущенных процессов
        running_processes = ProcessManager.get_running_main_processes()
        
        # Создаем словарь для быстрого поиска запущенных процессов
        process_map = {}
        for proc in running_processes:
            # Получаем имя процесса из psutil
            try:
                import psutil
                ps_proc = psutil.Process(proc.pid)
                proc_name = ps_proc.name()
                if proc_name not in process_map:
                    process_map[proc_name] = []
                process_map[proc_name].append(proc)
            except:
                continue

        # Проходим по всем отслеживаемым приложениям
        process_count = 0
        for app_config in TRACKED_APPLICATIONS:
            process_name = app_config["process_name"]
            display_name = app_config["display_name"]
            icon = app_config["icon"]
            launch_path = get_launch_path(app_config)
            
            # Проверяем, запущено ли приложение
            if process_name in process_map and len(process_map[process_name]) > 0:
                # Приложение запущено - показываем все экземпляры
                for proc in process_map[process_name]:
                    tracked_app = TrackedApp(
                        process_name=process_name,
                        display_name=display_name,
                        icon=icon,
                        launch_path=launch_path,
                        process=proc,
                        is_running=True
                    )
                    row = [QStandardItem(proc.name)]
                    for item in row:
                        item.setEditable(False)
                    # Сохраняем как процесс (Process1C объект) для совместимости
                    row[0].setData(proc, Qt.UserRole)
                    self.folder_item.appendRow(row)
                    process_count += 1
            else:
                # Приложение не запущено - показываем вариант для запуска
                tracked_app = TrackedApp(
                    process_name=process_name,
                    display_name=display_name,
                    icon=icon,
                    launch_path=launch_path,
                    process=None,
                    is_running=False
                )
                display_text = f"{icon} {display_name} [Запустить]"
                row = [QStandardItem(display_text)]
                for item in row:
                    item.setEditable(False)
                # Сохраняем TrackedApp для последующей обработки
                row[0].setData(tracked_app, Qt.UserRole)
                self.folder_item.appendRow(row)
                process_count += 1

        # Вставляем её второй строкой (после "Открытые базы")
        insert_position = 1
        if root.rowCount() > 0 and root.item(0, 0) and "Открытые базы" in root.item(0, 0).text():
            insert_position = 1
        else:
            insert_position = 0
        
        root.insertRow(insert_position, [self.folder_item])
        
        return self.folder_item, process_count

    def get_process_items(self):
        """
        Возвращает список QStandardItem (0-й колонки) для процессов
        """
        result = []
        if not self.folder_item:
            return result
        for i in range(0, self.folder_item.rowCount()):
            item = self.folder_item.child(i, 0)
            if item and item.data(Qt.UserRole):
                result.append(item)
        return result
