from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QStatusBar, QPushButton, QHBoxLayout,
)
from PySide6.QtGui import QStandardItemModel

from gui.hotkeys import GlobalHotkeyManager
from gui.actions import DatabaseActions, DatabaseOperations, ProcessActions
from gui.tree import TreeBuilder, OpenedBasesTreeBuilder, MainProcessesTreeBuilder
from gui.mixins import (
    TrayMixin,
    ShortcutsMixin,
    IbasesEditorMixin,
    BasesDataMixin,
    TreeNavigationMixin,
    DbmMixin,
)


class TreeWindow(
    TrayMixin,
    ShortcutsMixin,
    IbasesEditorMixin,
    BasesDataMixin,
    TreeNavigationMixin,
    DbmMixin,
    QMainWindow,
):
    """Основное окно с деревом баз 1С и управлением процессами."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Базы 1С")
        self.resize(1100, 600)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # --- Кнопка DBM ---
        self.btn_dbm = QPushButton("DBM")
        self.btn_dbm.setToolTip("Запустить DBM API")
        self.btn_dbm.setFixedSize(60, 25)
        self.btn_dbm.setStyleSheet("""
            QPushButton {
                background-color: #5c5c5c;
                color: white;
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #6d6d6d; }
            QPushButton:pressed { background-color: #4a4a4a; }
        """)
        self.btn_dbm.clicked.connect(self.run_dbm_app)

        # Верхняя панель (кнопка прижата вправо)
        top_layout = QHBoxLayout()
        top_layout.addStretch()
        top_layout.addWidget(self.btn_dbm)
        top_layout.setContentsMargins(0, 5, 10, 0)

        # Модель и дерево
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Имя базы", "Connect", "Версия"])
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 450)
        self.tree.setColumnWidth(2, 60)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(self.tree)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Данные
        self.all_bases = []
        self.last_launched_db = None
        self.last_activated_process = None
        self.last_activated_main_process = None
        self._ibases_editor_process = None

        # Инициализация
        self.setup_tray_icon()
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.actions = DatabaseActions(self, self.all_bases, self.save_bases, self.reload_and_navigate)
        self.operations = DatabaseOperations(self, self.all_bases, self.save_bases, self.reload_and_navigate)
        self.process_actions = ProcessActions(self)
        self.tree_builder = TreeBuilder(self.model)
        self.opened_bases_builder = OpenedBasesTreeBuilder(self.model)
        self.main_processes_builder = MainProcessesTreeBuilder(self.model)

        self.setup_shortcuts()
        self.hotkey_manager.register()
        self.load_bases()
        self.refresh_opened_bases()
        self.refresh_main_processes()
        self.expand_and_select_initial()

    def nativeEvent(self, eventType, message):
        """Обработка нативных событий Windows (глобальные хоткеи)."""
        handled, result = self.hotkey_manager.handle_native_event(eventType, message)
        if handled:
            return True, 0
        return super().nativeEvent(eventType, message)
