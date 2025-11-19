from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Signal, Qt
from typing import List, Optional
from models.database import Database1C


class DatabaseListWidget(QWidget):
    """Виджет для отображения списка баз данных"""
    
    database_selected = Signal(object)
    database_double_clicked = Signal()
    
    def __init__(self):
        super().__init__()
        self.databases = []
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Таблица с базами
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Название", "Тип", "ID", "Версия"])
        
        # Настройка таблицы
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Автоматическое изменение размера колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # Подключение сигналов
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_double_click)
        
        layout.addWidget(self.table)
    
    def set_databases(self, databases: List[Database1C]):
        """Установка списка баз данных"""
        self.databases = databases
        self.update_table()
    
    def update_table(self):
        """Обновление таблицы"""
        self.table.setRowCount(len(self.databases))
        
        for row, db in enumerate(self.databases):
            # Название
            name_item = QTableWidgetItem(db.name)
            self.table.setItem(row, 0, name_item)
            
            # Тип подключения
            type_item = QTableWidgetItem(db.get_connection_type())
            self.table.setItem(row, 1, type_item)
            
            # ID
            id_item = QTableWidgetItem(db.id)
            self.table.setItem(row, 2, id_item)
            
            # Версия
            version_item = QTableWidgetItem(db.version or "-")
            self.table.setItem(row, 3, version_item)
    
    def on_selection_changed(self):
        """Обработка изменения выбора"""
        selected_db = self.get_selected_database()
        self.database_selected.emit(selected_db)
    
    def on_double_click(self):
        """Обработка двойного клика"""
        self.database_double_clicked.emit()
    
    def get_selected_database(self) -> Optional[Database1C]:
        """Получение выбранной базы данных"""
        selected_rows = self.table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.databases):
                return self.databases[row]
        return None
