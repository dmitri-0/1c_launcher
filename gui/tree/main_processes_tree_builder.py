"""
Модуль для построения модели "Основное" (запущенные процессы Code.exe, TOTALCMD.EXE, WindowsTerminal.exe) для дерева
"""
from PySide6.QtGui import QStandardItem
from PySide6.QtCore import Qt
from services.process_manager import ProcessManager

class MainProcessesTreeBuilder:
    NODE_NAME = "Основное"

    def __init__(self, model):
        self.model = model
        self.folder_item = None

    def build_tree(self):
        """
        Создает/обновляет ветку "Основное" со всеми процессами Code.exe, TOTALCMD.EXE, WindowsTerminal.exe
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

        # Вставляем процессы
        processes = ProcessManager.get_running_main_processes()
        process_count = 0
        for proc in processes:
            row = [QStandardItem(proc.name)]

            # Записываем объект в data, чтобы потом работать
            for item in row:
                item.setEditable(False)
            row[0].setData(proc, Qt.UserRole)
            self.folder_item.appendRow(row)
            process_count += 1

        # Вставляем её второй строкой (после "Открытые базы")
        # Если "Открытые базы" есть на позиции 0, вставляем на позицию 1
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
