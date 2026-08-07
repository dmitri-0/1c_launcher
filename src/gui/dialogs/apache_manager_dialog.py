"""Диалог управления экземплярами Apache: запуск/остановка/службы/публикации."""

from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QTextEdit,
)

from services.web_publisher import WebPublisher, PublishError, is_admin


class ApacheHelpDialog(QDialog):
    """Справка: что такое «Управление Apache» и зачем оно нужно (F1)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка: Управление Apache")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
<h3>🖥 Управление Apache — что это и зачем</h3>
<p>Базы 1С публикуются на веб-сервере Apache через <b>webinst.exe</b> (F9).
Модуль расширения веб-сервера 1С (<code>wsap24.dll</code>) привязан к <b>версии
платформы</b>: один Apache может загрузить только одну версию модуля. Поэтому
базы на разных версиях платформы должны публиковаться в <b>разные экземпляры
Apache</b> — каждый на своём порту (иначе на второй базе будет ошибка
<code>409 Conflict</code> «Различаются версии клиента и сервера»).</p>

<h4>Что показывает таблица</h4>
<ul>
<li><b>Инстанс / Порт / Версии</b> — настроенный экземпляр Apache из
конфига <code>%APPDATA%\\1c_launcher\\web_publish.json</code> (по умолчанию —
один универсальный: C:\\Apache24, порт 80).</li>
<li><b>Служба</b> — состояние службы Windows: <code>running</code> /
<code>stopped</code> / <code>absent</code> (не установлена).</li>
<li><b>Порт слушается</b> — отвечает ли Apache на порту прямо сейчас.</li>
<li><b>Базы (публикации)</b> — какие базы (по версии платформы) публикуются
в этот экземпляр; сверху — предупреждение, если такой Apache не запущен.</li>
</ul>

<h4>Кнопки</h4>
<ul>
<li><b>Запустить / Остановить / Перезапустить</b> — управление службой
Windows (или скрытым процессом, если службы нет).</li>
<li><b>Установить службу</b> — ставит Apache как службу Windows с автозапуском
(без окон, работает после перезагрузки).</li>
</ul>

<h4>Права администратора</h4>
<p>Запуск/остановка служб и их установка требуют <b>прав администратора</b>
(ограничение Windows). Без них кнопки управления отключены — запустите
лаунчер от имени администратора. Просмотр статусов и публикаций работает
без прав.</p>
""")
        layout.addWidget(text)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)


class ApacheManagerDialog(QDialog):
    """Таблица экземпляров Apache с действиями запуска/остановки.

    Колонка «Базы» показывает, какие базы (по версии платформы) публикуются
    в этот экземпляр — то есть какие Apache «необходимы исходя из публикаций».
    """

    def __init__(self, parent=None, bases=None, publisher=None):
        super().__init__(parent)
        self.bases = list(bases or [])
        self.publisher = publisher or WebPublisher()
        self.setWindowTitle("Управление Apache")
        self.resize(950, 420)
        self.is_admin = is_admin()
        self._build_ui()
        self.refresh()

        # Справка по диалогу — клавиша F1
        self.help_shortcut = QShortcut(QKeySequence("F1"), self)
        self.help_shortcut.activated.connect(self.show_help)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        # Предупреждение о правах: без админа службы не запускаются/не останавливаются
        if not self.is_admin:
            self.admin_label = QLabel(
                "⚠ Запуск/остановка/перезапуск и установка служб требуют прав "
                "администратора. Запустите лаунчер от имени администратора, "
                "чтобы управлять Apache (просмотр статусов работает и без прав)."
            )
            self.admin_label.setStyleSheet("color: #d08020;")
            layout.addWidget(self.admin_label)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Инстанс", "Порт", "Версии", "Служба", "Порт слушается", "Базы (публикации)"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        admin_hint = "Требуются права администратора (запустите лаунчер от имени администратора)"
        for text, handler, needs_admin in (
            ("Обновить", self.refresh, False),
            ("Запустить", self._start, True),
            ("Остановить", self._stop, True),
            ("Перезапустить", self._restart, True),
            ("Установить службу", self._install_service, True),
            ("Справка (F1)", self.show_help, False),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            if needs_admin and not self.is_admin:
                button.setEnabled(False)
                button.setToolTip(admin_hint)
            buttons.addWidget(button)
        buttons.addStretch()
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ #
    #  Отображение                                                        #
    # ------------------------------------------------------------------ #

    def refresh(self):
        try:
            per_instance = self.publisher.bases_per_instance(self.bases)
        except PublishError:
            per_instance = {}

        self.table.setRowCount(0)
        warnings = []
        for instance in self.publisher.apache_instances:
            status = self.publisher.get_status(instance)
            bases = per_instance.get(instance.name, [])

            row = self.table.rowCount()
            self.table.insertRow(row)

            base_text = str(len(bases))
            if bases:
                names = ", ".join(b.name for b in bases[:3])
                if len(bases) > 3:
                    names += "…"
                base_text += f": {names}"
            values = [
                instance.name,
                str(instance.port),
                ", ".join(instance.versions) or "любые",
                status["service"],
                "да" if status["port_listening"] else "нет",
                base_text,
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 5 and bases:
                    item.setToolTip("\n".join(b.name for b in bases))
                self.table.setItem(row, col, item)

            if bases and not status["port_listening"]:
                warnings.append(f"{instance.name} (порт {instance.port})")

        if warnings:
            self.summary_label.setText(
                "⚠ Необходимы по публикациям, но не запущены: " + ", ".join(warnings)
            )
        else:
            self.summary_label.setText("")

    # ------------------------------------------------------------------ #
    #  Действия                                                           #
    # ------------------------------------------------------------------ #

    def _selected_instance(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Управление Apache", "Выберите экземпляр в таблице")
            return None
        return self.publisher.apache_instances[row]

    def _run_action(self, title, func):
        instance = self._selected_instance()
        if not instance:
            return
        try:
            result = func(instance)
        except PublishError as e:
            QMessageBox.critical(self, title, str(e))
            return
        message = result.stdout or result.stderr or ("OK" if result.ok else "Ошибка")
        if result.ok:
            QMessageBox.information(self, title, message)
        else:
            QMessageBox.critical(self, title, message)
        self.refresh()

    def _start(self):
        self._run_action("Запуск Apache", lambda i: self.publisher.ensure_apache_running(i))

    def _stop(self):
        self._run_action("Остановка Apache", self.publisher.stop_apache)

    def _restart(self):
        self._run_action("Перезапуск Apache", lambda i: self.publisher.restart_apache(i))

    def _install_service(self):
        instance = self._selected_instance()
        if not instance:
            return
        if not is_admin():
            QMessageBox.warning(
                self,
                "Установка службы",
                "Нужны права администратора.\n\n"
                "Запустите лаунчер от имени администратора и повторите — служба "
                "установится автоматически (автозапуск, без окон).",
            )
            return
        self._run_action("Установка службы", lambda i: self.publisher.install_service(i))

    def show_help(self):
        """F1: справка по диалогу управления Apache."""
        ApacheHelpDialog(self).exec()
