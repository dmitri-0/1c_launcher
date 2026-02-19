from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle
from PySide6.QtGui import QAction


class TrayMixin:
    """Миксин для управления иконкой в системном трее."""

    def setup_tray_icon(self):
        """Настройка иконки в системном трее."""
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()

        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)

        edit_ibases_action = QAction("Редактировать ibases.v8i", self)
        edit_ibases_action.triggered.connect(self.edit_ibases_in_notepad)
        tray_menu.addAction(edit_ibases_action)

        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        """Обработка активации иконки в трее."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        """Показать окно из трея."""
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.refresh_opened_bases()
        self.refresh_main_processes()
        self.expand_and_select_initial()

    def minimize_to_tray(self):
        """Свернуть окно в трей."""
        self.hide()

    def quit_application(self):
        """Полный выход из приложения."""
        self.hotkey_manager.unregister()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        """При закрытии окна сворачиваем в трей вместо выхода."""
        event.ignore()
        self.minimize_to_tray()
