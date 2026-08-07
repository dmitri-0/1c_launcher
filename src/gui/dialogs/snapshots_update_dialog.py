"""Диалог: полный список баз из раздела «Мои снапшоты» DBM API.

Каждая строка — база лаунчера, чей Ref совпадает со снапшотом пользователя.
Если для неё можно обновиться (в DBM API есть более новый снапшот «голубой»,
а в имени базы нет даты) — показывается кнопка «Обновить копию»: она запускает
процесс получения нового снапшота через DBM API, берёт его connection string
и выполняет обновление копии (как F12) через on_update_clicked(base).
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox,
)
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import Qt


class SnapshotsUpdateDialog(QDialog):
    """Таблица баз из «Мои снапшоты» с кнопкой обновления на строку."""

    def __init__(self, parent=None, candidates=None, on_update_clicked=None,
                 on_create_snapshot=None):
        super().__init__(parent)
        self.rows = list(candidates or [])
        self.on_update_clicked = on_update_clicked  # callable(base) -> str|None (сообщение)
        self.on_create_snapshot = on_create_snapshot  # callable() — мастер создания снапшота
        self._display_rows = []
        self.setWindowTitle("Снапшоты DBM API: мои копии")
        self.resize(1200, 460)
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        self.hide_dated_check = QCheckBox("Скрыть копии с датой в имени (<дата>)")
        self.hide_dated_check.setChecked(True)  # по умолчанию включён
        self.hide_dated_check.toggled.connect(self._refresh_table)
        layout.addWidget(self.hide_dated_check)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["База 1С", "Снапшот", "Строка соединения", "Истекает (текущий)",
             "Истекает (новый)", ""]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        # строка соединения занимает свободное место, остальное — по содержимому
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 150)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.update_all = QPushButton("Обновить все")
        self.update_all.clicked.connect(self._update_all)
        buttons.addWidget(self.update_all)
        create_new = QPushButton("Создать новый снапшот…")
        create_new.clicked.connect(lambda: self._create_snapshot())
        buttons.addWidget(create_new)
        buttons.addStretch()
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _refresh_table(self):
        self.table.setRowCount(0)
        hide_dated = self.hide_dated_check.isChecked()
        display = [r for r in self.rows if not (hide_dated and r.get("dated"))]
        self._display_rows = display
        updatable_count = 0
        for row_data in display:
            base = row_data["base"]
            row = self.table.rowCount()
            self.table.insertRow(row)

            if row_data["updatable"]:
                updatable_count += 1

            values = [
                base.name,
                str(row_data.get("snapshot_name") or ""),
                str(getattr(base, "connect", "") or ""),
                str(row_data.get("snapshot_exp") or ""),
                str(row_data.get("new_expiration") or ""),
            ]
            for col, text in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(text))

            # кнопка — только если можно обновиться
            if row_data["updatable"]:
                button = QPushButton("Обновить копию")
                button.clicked.connect(lambda _=False, r=row: self._update_row(r))
                self.table.setCellWidget(row, 5, button)

        if self.rows:
            self.summary_label.setText(
                f"Баз из «Мои снапшоты»: {len(self.rows)} (показано {len(display)}), "
                f"обновлений доступно: {updatable_count}"
            )
        else:
            self.summary_label.setText("Нет баз, привязанных к вашим снапшотам")
        self.update_all.setEnabled(updatable_count > 0)

    def _update_all(self):
        for row in range(self.table.rowCount() - 1, -1, -1):
            if self._display_rows[row]["updatable"] and not self._update_row(row):
                return

    def keyPressEvent(self, event):
        """Enter на строке: обновить копию, если можно; иначе — ничего."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            row = self.table.currentRow()
            if 0 <= row < len(self._display_rows) and self._display_rows[row]["updatable"]:
                self._update_row(row)
                return
        super().keyPressEvent(event)

    def _create_snapshot(self):
        """Открыть мастер создания снапшота (если передан обработчик)."""
        if self.on_create_snapshot is not None:
            self.on_create_snapshot()

    def _update_row(self, row) -> bool:
        """Кнопка «Обновить копию»: получить новый снапшот и применить (как F12)."""
        if row >= len(self._display_rows):
            return False
        row_data = self._display_rows[row]
        base = row_data["base"]
        if not row_data["updatable"]:
            return False
        try:
            message = self.on_update_clicked(base) if self.on_update_clicked else "Обновлено"
        except Exception as e:
            QMessageBox.critical(self, "Снапшоты", f"Ошибка обновления '{base.name}': {e}")
            return False
        if not message:
            return False  # пользователь прервал / снапшот ещё создаётся
        row_data["updatable"] = False
        self._refresh_table()
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "statusBar"):
            parent.statusBar.showMessage(message)
        # итог успешного обновления — понятное окно с результатом
        QMessageBox.information(self, "Обновление копии", message)
        return True
