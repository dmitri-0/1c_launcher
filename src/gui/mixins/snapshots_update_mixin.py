"""Миксин: диалог «Снапшоты: обновить копии» (интеграция с DBM API)."""

import re

from PySide6.QtWidgets import QMessageBox, QDialog

import services.dbm_snapshots as dbm
from services.web_publisher import PublishError
from ..dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
from ..dialogs.create_snapshot_dialog import CreateSnapshotDialog
from ..dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog
from models.database import Database1C


class SnapshotsUpdateMixin:
    """Показывает, какие базы пора обновить (есть новый снапшот DBM API)."""

    def open_snapshots_update(self):
        """Меню «Действия»: снапшоты — обновить копии.

        Логика «голубых» строк как в DBM API: если у базы данных есть снапшот
        с бОльшим сроком истечения, чем у текущего — есть более новый снапшот.
        База лаунчера без даты в имени, ссылающаяся на такой снапшот, — пора
        обновить (создать копию с датой и подключить новый снапшот).
        """
        token = dbm.get_valid_token()
        if not token:
            QMessageBox.warning(
                self,
                "Снапшоты DBM API",
                "Не удалось получить токен DBM API.\n\n"
                "Запустите DBM API (F11), авторизуйтесь и повторите.",
            )
            return

        snapshots = dbm.get_my_snapshots(token)
        if not snapshots:
            QMessageBox.information(self, "Снапшоты DBM API", "Нет снапшотов (или нет доступа к DBM API)")
            return

        rows = dbm.build_update_candidates(
            snapshots,
            self.all_bases,
            lambda db_id: self._get_db_snapshots(token, db_id),
        )
        if not rows:
            answer = QMessageBox.question(
                self,
                "Снапшоты DBM API",
                "Нет баз, привязанных к вашим снапшотам.\n\n"
                "Создать новый снапшот через DBM API?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.open_create_snapshot()
            return

        dialog = SnapshotsUpdateDialog(
            self,
            candidates=rows,
            on_update_clicked=self._update_copy_flow,
            on_create_snapshot=self.open_create_snapshot,
        )
        dialog.exec()

    def _update_copy_flow(self, base):
        """Кнопка «Обновить копию»: получить новый снапшот → применить (как F12).

        1. если в DBM API уже есть свободный более новый снапшот (не занят другой
           базой) — берём его connection string сразу;
        2. иначе — мастер создания снапшота DBM API (база → мастер → сервер),
           ждём появления нового снапшота и забираем его connection string;
        3. создаём копию с датой и подставляем строку подключения (как F12).
        """
        token = dbm.get_valid_token()
        if not token:
            QMessageBox.warning(
                self,
                "Снапшоты DBM API",
                "Не удалось получить токен DBM API.\n\n"
                "Запустите DBM API (F11), авторизуйтесь и повторите.",
            )
            return None

        base_ref = dbm._ref_from_connect(getattr(base, "connect", "") or "")
        db_id = self._snapshot_db_id(token, base_ref)
        server_hint = _server_host_from_connect(getattr(base, "connect", "") or "")
        used_refs = {dbm._ref_from_connect(getattr(b, "connect", "") or "")
                     for b in getattr(self, "all_bases", []) or []}

        # 1) быстрый путь: уже есть свободный более новый снапшот
        new_connect = self._find_free_newer_connect(token, db_id, base_ref, used_refs)
        if new_connect:
            return self._apply_snapshot_update(base, new_connect)

        # 2) создать новый снапшот через DBM API
        create_dialog = CreateSnapshotDialog(
            self, token=token, prefill_db_id=db_id, prefill_ref=base_ref,
            prefill_server_hint=server_hint,
        )
        if create_dialog.exec() != QDialog.Accepted:
            return None
        result = create_dialog.task_result() or {}
        early_connect = ((result.get("snapshot") or {}).get("connectionString") or "")
        early_connect = early_connect.replace('\\"', '"') if early_connect else ""

        # дождаться завершения задачи интерактивно (как DBM API), затем F12
        task_id = result.get("taskId")
        if not task_id:
            QMessageBox.critical(
                self, "Снапшоты DBM API",
                "Ответ DBM API не содержит taskId — невозможно дождаться завершения.",
            )
            return None
        wait = SnapshotTaskWaitDialog(
            self, token=token, task_id=task_id, db_id=db_id, base_ref=base_ref,
            description=create_dialog.last_description(),
            initial_connect=early_connect,
        )
        if wait.exec() == QDialog.Accepted and wait.connection_string():
            return self._apply_snapshot_update(base, wait.connection_string())
        return None

    def _snapshot_db_id(self, token, base_ref):
        """id БД DBM API, в которой живёт снапшот базы."""
        for snap in dbm.get_my_snapshots(token) or []:
            if snap.get("name") == base_ref:
                return snap.get("databaseId")
        return None

    def _find_free_newer_connect(self, token, db_id, base_ref, used_refs):
        """Connection string более нового снапшота, не занятого другими базами."""
        if not db_id:
            return None
        snaps = dbm.get_db_snapshots(token, db_id) or []
        cur_exp = next((dbm._parse_date(s.get("expirationDate"))
                        for s in snaps if s.get("name") == base_ref), None)
        if cur_exp is None:
            return None
        best = None
        for s in snaps:
            exp = dbm._parse_date(s.get("expirationDate"))
            if (s.get("name") != base_ref and s.get("connectionString")
                    and exp and exp > cur_exp and s.get("name") not in used_refs):
                if best is None or exp > dbm._parse_date(best.get("expirationDate")):
                    best = s
        return best.get("connectionString") if best else None

    def open_create_snapshot(self):
        """Меню «Действия»: создать снапшот DBM API (база → мастер → сервер)."""
        token = dbm.get_valid_token()
        if not token:
            QMessageBox.warning(
                self,
                "Создать снапшот DBM API",
                "Не удалось получить токен DBM API.\n\n"
                "Запустите DBM API (F11), авторизуйтесь и повторите.",
            )
            return
        dialog = CreateSnapshotDialog(self, token=token)
        dialog.exec()

    def _get_db_snapshots(self, token, db_id):
        """Все снапшоты базы данных (для логики «более новый»)."""
        try:
            return dbm.get_db_snapshots(token, db_id)
        except Exception:
            return []

    def _apply_snapshot_update(self, base, new_connect):
        """Создаёт копию с датой и подключает новый снапшот (как F12).

        Исходная база (включая уже датированные копии) каскадно дополняется
        новой датой в имени — её состояние на старом снапшоте сохраняется,
        свежая копия под исходным именем получает новый снапшот.
        """
        new_database = self.operations.create_copy_with_connect(base, Database1C, new_connect)
        return f"✅ Создана копия '{new_database.name}' → {new_connect}"


def _server_host_from_connect(connect: str) -> str:
    """Хост из Srvr= строки соединения (для предвыбора ERP-сервера)."""
    m = re.search(r'(?i)Srvr\s*=\s*"?([^":;"\s]+)', connect or "")
    return m.group(1) if m else ""
