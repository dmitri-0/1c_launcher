"""Миксин для управления недавними базами 1С."""

from datetime import datetime


class DbRecentMixin:
    """Перемещение баз в список недавних и перезагрузка UI после запуска."""

    def _move_to_recent(self, database):
        """Помечает базу как недавнюю и перемещает в начало списка."""
        if not database.is_recent and not database.original_folder:
            database.original_folder = database.folder

        database.is_recent = True
        database.last_run_time = datetime.now()

        if database in self.all_bases:
            self.all_bases.remove(database)

        self.all_bases.insert(0, database)
        self.save_callback()
        self.last_launched_db = database

    def _delayed_reload_after_launch(self):
        """Перезагружает UI после запуска базы."""
        self.reload_callback()
