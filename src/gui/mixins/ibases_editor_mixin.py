from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QProcess
from config import IBASES_PATH


class IbasesEditorMixin:
    """Миксин для редактирования файла ibases.v8i во внешнем редакторе."""

    def edit_ibases_in_notepad(self):
        """Открыть ibases.v8i в Notepad и после закрытия перечитать дерево."""
        if (
            self._ibases_editor_process
            and self._ibases_editor_process.state() != QProcess.NotRunning
        ):
            self.statusBar.showMessage("\u26a0\ufe0f ibases.v8i уже открыт в редакторе", 4000)
            return

        if not IBASES_PATH.exists():
            QMessageBox.warning(
                self,
                "Файл не найден",
                f"Не найден файл ibases.v8i по пути:\n{IBASES_PATH}",
            )
            return

        proc = QProcess(self)
        proc.setProgram("notepad.exe")
        proc.setArguments([str(IBASES_PATH)])
        proc.finished.connect(self._on_ibases_editor_closed)
        proc.errorOccurred.connect(self._on_ibases_editor_error)

        proc.start()
        if not proc.waitForStarted(2000):
            QMessageBox.warning(
                self,
                "Ошибка запуска",
                "Не удалось запустить notepad.exe для редактирования ibases.v8i",
            )
            return

        self._ibases_editor_process = proc
        self.statusBar.showMessage("\U0001f4dd Открыт ibases.v8i в Notepad (Ctrl+I)", 4000)

    def _on_ibases_editor_closed(self, exitCode, exitStatus):
        self._ibases_editor_process = None
        self.reload_and_navigate()
        self.statusBar.showMessage("\u2705 ibases.v8i закрыт — дерево обновлено", 5000)

    def _on_ibases_editor_error(self, error):
        self._ibases_editor_process = None
        QMessageBox.warning(
            self,
            "Ошибка запуска",
            "Не удалось открыть ibases.v8i в Notepad",
        )
