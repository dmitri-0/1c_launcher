"""Мастер создания снапшота DBM API: база → снапшот-мастер → ERP-сервер."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QPushButton, QLabel, QMessageBox,
)

import services.dbm_snapshots as dbm


class CreateSnapshotDialog(QDialog):
    """Создание снапшота через DBM API (как в DBM API: имя/мастер → сервер).

    Шаги:
    1. выбор БД DBM API → загружаются её снапшоты;
    2. выбор снапшота-мастера (имя);
    3. выбор ERP-сервера;
    4. описание (автозаполняется «Создание копии <мастер> на <сервер>»);
    5. «Создать снапшот» → POST /api/v1/snapshots.
    """

    def __init__(self, parent=None, token=None, databases_loader=None,
                 snapshots_loader=None, servers_loader=None, creator=None,
                 prefill_db_id=None, prefill_ref="", prefill_server_hint=""):
        super().__init__(parent)
        self.token = token
        self.prefill_db_id = prefill_db_id
        self.prefill_ref = prefill_ref
        self.prefill_server_hint = prefill_server_hint
        self.databases_loader = databases_loader or (lambda: dbm.get_databases(token))
        self.snapshots_loader = snapshots_loader or (lambda db_id: dbm.get_db_snapshots(token, db_id))
        self.servers_loader = servers_loader or (lambda: dbm.get_erp_servers(token))
        self.creator = creator or (lambda m, s, d: dbm.create_snapshot(token, m, s, d))

        self._databases = []
        self._snapshots = []
        self._servers = []
        self._last_result = None
        self._last_description = None

        self.setWindowTitle("Создать снапшот DBM API")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load_databases()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.db_combo = QComboBox()
        self.db_combo.currentIndexChanged.connect(self._on_db_changed)
        form.addRow("База DBM API:", self.db_combo)

        self.snap_combo = QComboBox()
        form.addRow("Снапшот-мастер (имя):", self.snap_combo)

        self.server_combo = QComboBox()
        form.addRow("ERP-сервер:", self.server_combo)

        self.desc_edit = QLineEdit()
        self.desc_edit.returnPressed.connect(self._create_from_enter)
        form.addRow("Описание:", self.desc_edit)
        layout.addLayout(form)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        create = QPushButton("Создать снапшот")
        create.clicked.connect(self._create)
        buttons.addWidget(create)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ #
    #  Загрузка                                                           #
    # ------------------------------------------------------------------ #

    def _load_databases(self):
        self._databases = self.databases_loader() or []
        self.db_combo.clear()
        for db in self._databases:
            self.db_combo.addItem(
                f"{db.get('id')}. {db.get('name', '')} ({db.get('description', '')})",
                db,
            )
        if self._databases:
            idx = 0
            if self.prefill_db_id:
                for i, db in enumerate(self._databases):
                    if db.get("id") == self.prefill_db_id:
                        idx = i
                        break
            self.db_combo.setCurrentIndex(idx)  # триггерит загрузку снапшотов
            self._apply_prefill_snapshot()
        else:
            self.status_label.setText("⚠ Базы DBM API не загрузились (проверьте токен/сеть)")

    def task_result(self):
        """Результат create_snapshot: {'taskId': ..., 'snapshot': {...}} или None."""
        return self._last_result

    def last_description(self):
        """Описание задачи («Создание копии <мастер> на <сервер>»)."""
        return self._last_description or ""

    def _apply_prefill_snapshot(self):
        """Предвыбрать снапшот-мастер = текущий снапшот базы (если есть)."""
        if not self.prefill_ref:
            return
        for i in range(self.snap_combo.count()):
            data = self.snap_combo.itemData(i)
            if data and data.get("name") == self.prefill_ref:
                self.snap_combo.setCurrentIndex(i)
                break

    def _on_db_changed(self, _index):
        db = self.db_combo.currentData()
        if not db:
            return
        self._snapshots = self.snapshots_loader(db.get("id")) or []
        self.snap_combo.clear()
        for snap in self._snapshots:
            self.snap_combo.addItem(
                f"{snap.get('name', '')} (истечение: {snap.get('expirationDate', '')})",
                snap,
            )
        self._load_servers()
        self._update_description()

    def _load_servers(self):
        self._servers = self.servers_loader() or []
        self.server_combo.clear()
        for server in self._servers:
            self.server_combo.addItem(
                f"{server.get('name', '')} ({server.get('description', '')})",
                server,
            )
        self.server_combo.currentIndexChanged.connect(self._update_description)
        self._apply_prefill_server()

    def _apply_prefill_server(self):
        """Предвыбрать сервер, ближайший к строке соединения базы (по умолчанию)."""
        hint = (self.prefill_server_hint or "").strip().lower()
        if not hint or not self._servers:
            return
        for i, server in enumerate(self._servers):
            name = (server.get("name") or "").lower()
            desc = (server.get("description") or "").lower()
            if hint in name or name in hint or hint in desc:
                self.server_combo.setCurrentIndex(i)
                break

    def _update_description(self):
        snap = self.snap_combo.currentData()
        server = self.server_combo.currentData()
        if snap and server:
            self.desc_edit.setText(
                f"Создание копии {snap.get('name', '')} на {server.get('name', '')}"
            )

    # ------------------------------------------------------------------ #
    #  Создание                                                           #
    # ------------------------------------------------------------------ #

    def _create_from_enter(self):
        """Enter в строке описания: создать, если всё выбрано, иначе — ничего."""
        snap = self.snap_combo.currentData()
        server = self.server_combo.currentData()
        if not snap or not server:
            return
        self._create()

    def _create(self):
        snap = self.snap_combo.currentData()
        server = self.server_combo.currentData()
        if not snap or not server:
            QMessageBox.warning(self, "Создать снапшот", "Выберите снапшот-мастер и ERP-сервер")
            return
        description = self.desc_edit.text().strip() or "Копия базы"
        try:
            result = self.creator(snap.get("id"), server.get("id"), description)
        except Exception as e:
            QMessageBox.critical(self, "Создать снапшот", f"Ошибка: {e}")
            return
        self._last_result = result
        self._last_description = description
        # интерактивное ожидание — в отдельном окне (как DBM API), здесь не блокируем
        self.status_label.setText("✅ Задача на создание снапшота отправлена — ожидание…")
        self.accept()
