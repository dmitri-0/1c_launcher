import os
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QProcess, QProcessEnvironment
from config import DBM_PYTHON_EXE, DBM_SCRIPT_PATH


class DbmMixin:
    """Миксин для запуска внешнего приложения DBM."""

    def run_dbm_app(self):
        """Запуск внешнего приложения DBM с очисткой окружения."""
        if not os.path.exists(DBM_PYTHON_EXE):
            QMessageBox.warning(self, "Ошибка", f"Не найден интерпретатор:\n{DBM_PYTHON_EXE}")
            return

        if not os.path.exists(DBM_SCRIPT_PATH):
            QMessageBox.warning(self, "Ошибка", f"Не найден скрипт:\n{DBM_SCRIPT_PATH}")
            return

        proc = QProcess()
        proc.setProgram(DBM_PYTHON_EXE)
        proc.setArguments([DBM_SCRIPT_PATH])

        env = QProcessEnvironment.systemEnvironment()
        keys_to_remove = [
            "QT_QPA_PLATFORM_PLUGIN_PATH",
            "QT_PLUGIN_PATH",
            "PYTHONPATH",
            "PYTHONHOME",
        ]
        for key in keys_to_remove:
            env.remove(key)

        proc.setProcessEnvironment(env)
        success = proc.startDetached()

        if success:
            self.statusBar.showMessage("\U0001f680 DBM API запущен", 3000)
        else:
            QMessageBox.critical(self, "Ошибка запуска", "Не удалось запустить процесс DBM.")
