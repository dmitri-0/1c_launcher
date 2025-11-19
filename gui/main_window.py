from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QStatusBar
from PySide6.QtCore import Qt
from gui.database_list_widget import DatabaseListWidget
from services.base_reader import BaseReader
from services.base_launcher import BaseLauncher
from config import IBASES_PATH, ENCODING


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.reader = BaseReader(IBASES_PATH, ENCODING)
        self.launcher = BaseLauncher()
        self.databases = []
        
        self.init_ui()
        self.load_databases()
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("Лончер баз 1С")
        self.setMinimumSize(800, 600)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        layout = QVBoxLayout(central_widget)
        
        # Заголовок
        header = QLabel("🚀 Лончер баз данных 1С")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Виджет со списком баз
        self.database_list = DatabaseListWidget()
        self.database_list.database_selected.connect(self.on_database_selected)
        self.database_list.database_double_clicked.connect(self.launch_database)
        layout.addWidget(self.database_list)
        
        # Кнопки управления
        button_layout = QVBoxLayout()
        
        self.launch_btn = QPushButton("Запустить базу")
        self.launch_btn.setEnabled(False)
        self.launch_btn.clicked.connect(self.launch_database)
        self.launch_btn.setStyleSheet("padding: 10px; font-size: 14px;")
        button_layout.addWidget(self.launch_btn)
        
        self.refresh_btn = QPushButton("Обновить список")
        self.refresh_btn.clicked.connect(self.load_databases)
        self.refresh_btn.setStyleSheet("padding: 10px; font-size: 14px;")
        button_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(button_layout)
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
    
    def load_databases(self):
        """Загрузка списка баз данных"""
        self.databases = self.reader.read_bases()
        self.database_list.set_databases(self.databases)
        self.status_bar.showMessage(f"Загружено баз: {len(self.databases)}")
    
    def on_database_selected(self, database):
        """Обработка выбора базы данных"""
        self.launch_btn.setEnabled(database is not None)
        if database:
            self.status_bar.showMessage(f"Выбрана база: {database.name}")
    
    def launch_database(self):
        """Запуск выбранной базы данных"""
        selected_db = self.database_list.get_selected_database()
        if selected_db:
            success = self.launcher.launch_database(selected_db)
            if success:
                self.status_bar.showMessage(f"База '{selected_db.name}' запущена", 3000)
            else:
                self.status_bar.showMessage(f"Ошибка запуска базы '{selected_db.name}'", 3000)
