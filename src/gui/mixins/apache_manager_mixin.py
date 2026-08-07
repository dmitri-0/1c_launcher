"""Миксин управления экземплярами Apache (меню, Ctrl+F2)."""

from PySide6.QtWidgets import QMessageBox

from services.web_publisher import WebPublisher, PublishError
from ..dialogs.apache_manager_dialog import ApacheManagerDialog


class ApacheManagerMixin:
    """Управление Apache: запуск/остановка/службы/необходимость по публикациям."""

    def open_apache_manager(self):
        """Ctrl+F2: диалог управления экземплярами Apache."""
        try:
            publisher = WebPublisher()
        except PublishError as e:
            QMessageBox.critical(self, "Управление Apache", str(e))
            return
        dialog = ApacheManagerDialog(self, bases=self.all_bases, publisher=publisher)
        dialog.exec()
