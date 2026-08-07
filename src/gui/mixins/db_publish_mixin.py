"""Миксин публикации базы на Apache (webinst.exe).

Действие для базы: "Опубликовать" (F9) / "Отменить публикацию" (Shift+F9).
Вся логика вынесена в отдельный модуль services.web_publisher — здесь
только GUI-обвязка (статус-бар, диалоги).
"""

import platform

from PySide6.QtWidgets import QInputDialog, QMessageBox

from services.web_publisher import WebPublisher, PublishError, is_admin


class DbPublishMixin:
    """Публикация выбранной базы на веб-сервере Apache."""

    def _require_admin(self) -> bool:
        """True, если процесс под администратором; иначе предупреждение и False."""
        if is_admin():
            return True
        QMessageBox.warning(
            self.window,
            "Требуются права администратора",
            "Операция требует прав администратора: webinst.exe пишет в "
            "conf/httpd.conf и каталог публикации, а Apache работает как "
            "служба Windows (её устанавливает/перезапускает лаунчер).\n\n"
            "Запустите лаунчер от имени администратора (правый клик по ярлыку → "
            "«Запуск от имени администратора») и повторите действие.",
        )
        return False

    def publish_database(self, database):
        """F9: опубликовать базу на Apache (webinst.exe -publish).

        Экземпляр Apache выбирается по версии платформы базы — каждая
        версия платформы публикуется в свой Apache (свой wsap24.dll).
        """
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Публикация поддерживается только в Windows")
            return False

        publisher = WebPublisher()
        try:
            instance = publisher.select_instance(database.version)
        except PublishError as e:
            self.window.statusBar.showMessage(f"❌ {e}")
            QMessageBox.warning(self.window, "Публикация базы", str(e))
            return False

        if not self._require_admin():
            return False

        default_wsdir = WebPublisher.build_wsdir(database)
        wsdir, ok = QInputDialog.getText(
            self.window,
            "Опубликовать базу",
            f"Псевдоним публикации (wsdir), база: {database.name}\n"
            f"Apache: {instance.name} (порт {instance.port}, версии: {', '.join(instance.versions) or 'любые'})",
            text=default_wsdir,
        )
        if not ok or not wsdir.strip():
            self.window.statusBar.showMessage("Публикация отменена")
            return False

        try:
            # Авто-копирование и настройка Apache, если его каталога ещё нет
            if publisher.ensure_instance_ready(instance):
                if not instance.conf_path.exists():
                    self.window.statusBar.showMessage(
                        f"🛠 Apache {instance.name} скопирован и настроен ({instance.apache_root})"
                    )
        except PublishError as e:
            self.window.statusBar.showMessage(f"❌ {e}")
            QMessageBox.warning(self.window, "Публикация базы", str(e))
            return False

        try:
            result = publisher.publish(database, wsdir=wsdir.strip(), instance=instance)
        except PublishError as e:
            self.window.statusBar.showMessage(f"❌ {e}")
            QMessageBox.critical(self.window, "Публикация базы", str(e))
            return False

        restart_note = ""
        if result.ok:
            restart = publisher.ensure_apache_running(instance)
            if not restart.ok:
                restart_note = (
                    "\n⚠ Не удалось поднять Apache автоматически — "
                    "запустите его вручную (httpd.exe -k restart от администратора)"
                )
            elif restart.stdout:
                restart_note = f"\n{restart.stdout}"

            # Проверка после публикации: слушает ли Apache порт, отвечает ли публикация
            if not publisher.is_port_listening(instance.port):
                restart_note += (
                    f"\n⚠ Apache не слушает порт {instance.port} — откройте "
                    "«Управление Apache» (Ctrl+F2) и запустите/перезапустите его"
                )
            elif result.publication_url:
                username = getattr(database, "usr_enterprise", None)
                password = getattr(database, "pwd_enterprise", None)
                ok_url = publisher.verify(
                    database, instance=instance, wsdir=wsdir.strip(),
                    username=username, password=password,
                )
                if ok_url:
                    restart_note += f"\n✅ Публикация отвечает: {result.publication_url}"
                else:
                    restart_note += (
                        f"\n⚠ Публикация не отвечает ({result.publication_url}) — "
                        "проверьте «Управление Apache» (Ctrl+F2)"
                    )

        if result.ok:
            message = f"✅ База опубликована: {result.publication_url}{restart_note}"
            self.window.statusBar.showMessage(message)
            QMessageBox.information(self.window, "Публикация базы", message)
            return True

        details = (result.stdout or "").strip() or (result.stderr or "").strip()
        message = f"❌ webinst.exe завершился с кодом {result.returncode}"
        if details:
            message += f"\n\n{details}"
        self.window.statusBar.showMessage(message)
        QMessageBox.critical(self.window, "Публикация базы", message)
        return False

    def unpublish_database(self, database):
        """Shift+F9: отменить публикацию базы (webinst.exe -unpublish)."""
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Публикация поддерживается только в Windows")
            return False

        publisher = WebPublisher()
        try:
            instance = publisher.select_instance(database.version)
        except PublishError as e:
            self.window.statusBar.showMessage(f"❌ {e}")
            QMessageBox.warning(self.window, "Отмена публикации", str(e))
            return False

        if not self._require_admin():
            return False

        default_wsdir = WebPublisher.build_wsdir(database)
        wsdir, ok = QInputDialog.getText(
            self.window,
            "Отменить публикацию",
            f"Псевдоним публикации (wsdir), база: {database.name}\n"
            f"Apache: {instance.name} (порт {instance.port})",
            text=default_wsdir,
        )
        if not ok or not wsdir.strip():
            self.window.statusBar.showMessage("Отмена публикации отменена")
            return False

        try:
            result = publisher.unpublish(database, wsdir=wsdir.strip(), instance=instance)
        except PublishError as e:
            self.window.statusBar.showMessage(f"❌ {e}")
            QMessageBox.critical(self.window, "Отмена публикации", str(e))
            return False

        if result.ok:
            message = f"✅ Публикация базы отменена (wsdir={wsdir.strip()})"
            self.window.statusBar.showMessage(message)
            QMessageBox.information(self.window, "Отмена публикации", message)
            return True

        details = (result.stdout or "").strip() or (result.stderr or "").strip()
        message = f"❌ webinst.exe завершился с кодом {result.returncode}"
        if details:
            message += f"\n\n{details}"
        self.window.statusBar.showMessage(message)
        QMessageBox.critical(self.window, "Отмена публикации", message)
        return False
