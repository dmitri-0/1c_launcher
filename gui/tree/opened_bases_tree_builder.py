"""
Модуль для построения модели "Открытые базы" (запущенные процессы 1C) для дерева
"""
from PySide6.QtGui import QStandardItem, QColor
from PySide6.QtCore import Qt
from services.process_manager import ProcessManager, Process1C

class OpenedBasesTreeBuilder:
    NODE_NAME = "Открытые базы"

    def __init__(self, model):
        self.model = model
        self.folder_item = None

    def build_tree(self):
        """
        Создает/обновляет ветку "Открытые базы" со всеми процессами 1cv8.exe
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

        # Вставляем процессы (только имя, без hwnd и pid)
        processes = ProcessManager.get_running_processes()
        process_count = 0
        for proc in processes:
            row = [QStandardItem(proc.name)]

            # Устанавливаем цвет текста для всей строки или только для первой колонки
            # color = QColor("#00FF00") if "тест" in proc.name.lower() else QColor("#FF0000")
            # row[0].setForeground(color)
                
            # Записываем объект в data, чтобы потом работать
            for item in row:
                item.setEditable(False)
            row[0].setData(proc, Qt.UserRole)
            self.folder_item.appendRow(row)
            process_count += 1

        # Вставляем её первой!
        root.insertRow(0, [self.folder_item])
        
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
