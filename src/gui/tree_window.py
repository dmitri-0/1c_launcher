from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QStatusBar,
)
from PySide6.QtGui import QStandardItemModel, QAction

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
    DigitNavigationMixin,
)
from models.database import Database1C
from gui.dialogs import DatabaseSettingsDialog


class TreeWindow(
    TrayMixin,
    ShortcutsMixin,
    IbasesEditorMixin,
    BasesDataMixin,
    TreeNavigationMixin,
    DbmMixin,
    DigitNavigationMixin,
    QMainWindow,
):
    """Основное окно с деревом баз 1С и управлением процессами."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Базы 1С")
        self.resize(1100, 600)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Модель и дерево
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Имя базы", "Connect", "Версия"])
        self.tree = QTreeView()
        self.tree.setModel(self.model)

        # Делегат для отображения номеров слева
        from gui.tree.number_prefix_delegate import NumberPrefixDelegate
        self.tree.setItemDelegateForColumn(0, NumberPrefixDelegate(self.tree))

        self.tree.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 450)
        self.tree.setColumnWidth(2, 60)

        layout = QVBoxLayout()
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

        self.setup_menu()
        self.setup_digit_navigation()
        self.hotkey_manager.register()
        self.load_bases()
        self.refresh_opened_bases()
        self.refresh_main_processes()
        self.expand_and_select_initial()

    def setup_menu(self):
        """Создание меню бара с привязкой всех действий и горячих клавиш."""
        menubar = self.menuBar()

        # ── Действия ──────────────────────────────────────────
        menu_actions = menubar.addMenu("Действия")

        a = QAction("Открыть / Активировать\t[Enter]", self)
        a.setShortcut("Return")
        a.triggered.connect(self.handle_enter)
        menu_actions.addAction(a)

        a = QAction("Открыть базу\t[F3]", self)
        a.setShortcut("F3")
        a.triggered.connect(self.handle_f3_open)
        menu_actions.addAction(a)

        a = QAction("Открыть конфигуратор\t[F4 / Shift+Enter]", self)
        a.setShortcuts(["F4", "Shift+Return"])
        a.triggered.connect(self.handle_f4_open)
        menu_actions.addAction(a)

        a = QAction("Инструменты ИР\t[F5]", self)
        a.setShortcut("F5")
        a.triggered.connect(self.handle_f5_ir_tools)
        menu_actions.addAction(a)

        a = QAction("Консоль сервера\t[F6]", self)
        a.setShortcut("F6")
        a.triggered.connect(self.handle_f6_server_console)
        menu_actions.addAction(a)

        menu_actions.addSeparator()

        a = QAction("Запустить DBM API", self)
        a.triggered.connect(self.run_dbm_app)
        menu_actions.addAction(a)

        menu_actions.addSeparator()

        a = QAction("Свернуть в трей\t[Esc]", self)
        a.setShortcut("Esc")
        a.triggered.connect(self.minimize_to_tray)
        menu_actions.addAction(a)

        a = QAction("Выход\t[Shift+Esc]", self)
        a.setShortcut("Shift+Esc")
        a.triggered.connect(self.quit_application)
        menu_actions.addAction(a)

        # ── Конфигурация ──────────────────────────────────────
        menu_cfg = menubar.addMenu("Конфигурация")

        a = QAction("Обновить конфигурацию БД\t[F7]", self)
        a.setShortcut("F7")
        a.triggered.connect(self.handle_f7_save_cfg)
        menu_cfg.addAction(a)

        a = QAction("Обновить из хранилища\t[Ctrl+F7]", self)
        a.setShortcut("Ctrl+F7")
        a.triggered.connect(self.handle_ctrl_f7_update_cfg_from_repository)
        menu_cfg.addAction(a)

        a = QAction("Выгрузить CF\t[F8]", self)
        a.setShortcut("F8")
        a.triggered.connect(self.handle_f8_dump_cf)
        menu_cfg.addAction(a)

        # ── Редактирование ────────────────────────────────────
        menu_edit = menubar.addMenu("Редактирование")

        a = QAction("Добавить базу\t[Shift+F10]", self)
        a.setShortcut("Shift+F10")
        a.triggered.connect(lambda: self.operations.add_database(
            Database1C, DatabaseSettingsDialog,
            lambda: self.operations.get_current_folder(self.model, self.tree)
        ))
        menu_edit.addAction(a)

        a = QAction("Дублировать базу\t[Ctrl+D]", self)
        a.setShortcut("Ctrl+D")
        a.triggered.connect(lambda: self.operations.duplicate_database(
            self.operations.get_selected_database(self.model, self.tree), Database1C
        ))
        menu_edit.addAction(a)

        a = QAction("Настройки базы\t[Ctrl+E]", self)
        a.setShortcut("Ctrl+E")
        a.triggered.connect(lambda: self.operations.edit_database_settings(
            self.operations.get_selected_database(self.model, self.tree), DatabaseSettingsDialog
        ))
        menu_edit.addAction(a)

        a = QAction("Копировать строку соединения\t[Ctrl+C]", self)
        a.setShortcut("Ctrl+C")
        a.triggered.connect(lambda: self.operations.copy_connection_string(
            self.operations.get_selected_database(self.model, self.tree)
        ))
        menu_edit.addAction(a)

        a = QAction("Редактировать ibases.v8i\t[Ctrl+I]", self)
        a.setShortcut("Ctrl+I")
        a.triggered.connect(self.edit_ibases_in_notepad)
        menu_edit.addAction(a)

        menu_edit.addSeparator()

        a = QAction("Удалить базу / Закрыть процесс\t[Del]", self)
        a.setShortcuts(["Del", "Backspace"])
        a.triggered.connect(self.handle_delete)
        menu_edit.addAction(a)

        a = QAction("Очистить кеш / Принудительно закрыть\t[Shift+Del]", self)
        a.setShortcut("Shift+Del")
        a.triggered.connect(self.handle_shift_delete)
        menu_edit.addAction(a)

        # ── Вид ───────────────────────────────────────────────
        menu_view = menubar.addMenu("Вид")

        a = QAction("Переключить тему\t[F10]", self)
        a.setShortcut("F10")
        a.triggered.connect(self.toggle_theme)
        menu_view.addAction(a)

        # ── Справка ───────────────────────────────────────────
        menu_help = menubar.addMenu("Справка")

        a = QAction("Помощь\t[F1]", self)
        a.setShortcut("F1")
        a.triggered.connect(self.show_help)
        menu_help.addAction(a)

    def nativeEvent(self, eventType, message):
        """Обработка нативных событий Windows (глобальные хоткеи)."""
        handled, result = self.hotkey_manager.handle_native_event(eventType, message)
        if handled:
            return True, 0
        return super().nativeEvent(eventType, message)
