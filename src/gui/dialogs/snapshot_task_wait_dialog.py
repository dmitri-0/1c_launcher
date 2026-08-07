"""Модальное окно ожидания создания снапшота (как в DBM API).

Поллинг статуса задачи через QTimer, сетевые запросы — в фоновом QThread
(GUI не блокируется). В окне: описание, параметры задачи, **живой лог**
выполнения (обновляется на каждом опросе), progress bar (indeterminate,
по завершении — 100%). По завершении берётся connection string нового
снапшота и диалог завершается с Accept — вызывающий применяет F12.
"""

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QWidget, QSplitter,
)

import services.dbm_snapshots as dbm


class _NetworkWorker(QThread):
    """Выполняет блокирующий сетевой вызов в фоне, результат — сигналом."""

    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(("ok", self.fn()))
        except Exception as e:  # noqa: BLE001
            self.done.emit(("error", str(e)))


class SnapshotTaskWaitDialog(QDialog):
    """Ждёт завершения задачи создания снапшота, затем забирает connection string."""

    def __init__(self, parent=None, token=None, task_id=None, db_id=None, base_ref=None,
                 description="", initial_connect="", task_status_fetcher=None,
                 snapshots_fetcher=None, poll_interval_ms=2000, max_polls=150):
        super().__init__(parent)
        self.token = token
        self.task_id = task_id
        self.db_id = db_id
        self.base_ref = base_ref
        self.description = description
        self.initial_connect = initial_connect  # из ответа создания (запасной вариант)
        self.task_status_fetcher = task_status_fetcher or (
            lambda t, tid: dbm.get_task_status(t, tid))
        self.snapshots_fetcher = snapshots_fetcher or (
            lambda t, db: dbm.get_db_snapshots(t, db))
        self._connection_string = ""
        self._polls = 0
        self._max_polls = max_polls
        self._state = "waiting"
        self._workers = set()          # живые QThread-воркеры (защита от GC)
        self._status_in_flight = False

        self.setWindowTitle("Создание снапшота DBM API")
        self.setModal(True)
        self.resize(760, 480)
        self._build_ui()
        self._add_param("Task ID", str(self.task_id or ""))

        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            self.description or f"Создание копии: задача {self.task_id}")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.info_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate пока задача выполняется
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Статус: …")
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # параметры задачи (Task ID, Snapshot ID/Name/Connection String — как DBM API)
        self.params_table = QTableWidget(0, 2)
        self.params_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.setEditTriggers(QTableWidget.NoEditTriggers)
        params_header = self.params_table.horizontalHeader()
        params_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        params_header.setSectionResizeMode(1, QHeaderView.Stretch)
        splitter.addWidget(self.params_table)

        # живой лог выполнения
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("Лог выполнения:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        splitter.addWidget(log_container)

        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ #
    #  Вспомогательное                                                    #
    # ------------------------------------------------------------------ #

    def _add_param(self, name, value):
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        self.params_table.setItem(row, 0, QTableWidgetItem(name))
        self.params_table.setItem(row, 1, QTableWidgetItem(value))

    def connection_string(self):
        """connection string нового снапшота (после Accept)."""
        return self._connection_string

    def _run_worker(self, fn, callback):
        """Запускает сетевой вызов в фоне, держит ссылку на воркер до завершения."""
        worker = _NetworkWorker(fn)
        worker.done.connect(callback)
        worker.finished.connect(lambda w=worker: self._workers.discard(w))
        self._workers.add(worker)
        worker.start()

    def closeEvent(self, event):
        """При закрытии ждём завершения воркеров, чтобы QThread не умирал во время работы.

        Ожидание ограничено сверху сетевым таймаутом запросов (get_task_status —
        20 с), так что GUI не зависнет надолго.
        """
        self._timer.stop()
        for worker in list(self._workers):
            worker.wait(25000)
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    #  Поллинг статуса задачи                                             #
    # ------------------------------------------------------------------ #

    def _poll(self):
        if self._state != "waiting" or self._status_in_flight:
            return
        self._polls += 1
        if self._polls > self._max_polls:
            self._state = "failed"
            self._timer.stop()
            QMessageBox.warning(
                self, "Создание снапшота",
                "Время ожидания истекло — задача всё ещё выполняется.\n"
                "Повторите «Обновить копию» позже.",
            )
            self.reject()
            return
        self._status_in_flight = True
        self._run_worker(
            lambda: self.task_status_fetcher(self.token, self.task_id),
            self._on_status,
        )

    def _on_status(self, payload):
        self._status_in_flight = False
        if self._state != "waiting":
            return
        kind, data = payload
        if kind == "error":
            # сеть/сервер временно недоступны — продолжаем ждать
            self.status_label.setText(f"Статус: ошибка запроса ({data})")
            return
        task_info = dbm.task_info_from_status(data)
        state = str(task_info.get("state") or task_info.get("status") or "").lower()
        message = str(task_info.get("message") or "")
        logs = task_info.get("log") or task_info.get("logs") or []

        self.status_label.setText(f"Статус: {state or '…'}" + (f" — {message}" if message else ""))
        # живой лог
        if logs:
            self.log_view.clear()
            self.log_view.append("\n".join(str(line) for line in logs))
            scrollbar = self.log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        if state in dbm.TASK_DONE_STATES:
            self._state = "done"
            self._timer.stop()
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.progress.setTextVisible(True)
            self.status_label.setText("Готово! Снапшот создан.")
            self._fetch_connection_string()
        elif state in dbm.TASK_FAILED_STATES:
            self._state = "failed"
            self._timer.stop()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setTextVisible(True)
            QMessageBox.critical(
                self, "Создание снапшота",
                f"Задача завершилась с ошибкой: {state}\n{message}",
            )
            self.reject()

    # ------------------------------------------------------------------ #
    #  Получение connection string нового снапшота                        #
    # ------------------------------------------------------------------ #

    def _fetch_connection_string(self):
        self._run_worker(
            lambda: self.snapshots_fetcher(self.token, self.db_id),
            self._on_snapshots,
        )

    def _on_snapshots(self, payload):
        kind, data = payload
        if kind == "error":
            QMessageBox.warning(
                self, "Создание снапшота",
                f"Снапшот создан, но не удалось получить строку подключения:\n{data}",
            )
            self.reject()
            return
        connect = dbm.find_newer_snapshot_connect(data or [], self.base_ref)
        if not connect:
            # новый снапшот ещё не виден в списке — используем строку из ответа создания
            connect = self.initial_connect
        if not connect:
            QMessageBox.warning(
                self, "Создание снапшота",
                "Снапшот создан, но новая строка подключения не найдена.\n"
                "Обновите «Мои снапшоты» (F11) и повторите.",
            )
            self.reject()
            return
        self._connection_string = connect
        self.accept()
