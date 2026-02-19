from PySide6.QtCore import Qt
from services.process_manager import Process1C


class TreeNavigationMixin:
    """Миксин для обновления и навигации по дереву баз/процессов."""

    def refresh_opened_bases(self):
        """Обновление папки с открытыми базами (запущенными процессами 1С)."""
        result = self.opened_bases_builder.build_tree()
        if result:
            folder_item, process_count = result
            folder_index = self.tree.model().indexFromItem(folder_item)
            self.tree.setFirstColumnSpanned(folder_index.row(), folder_index.parent(), True)
            for proc_row in range(process_count):
                self.tree.setFirstColumnSpanned(proc_row, folder_index, True)

    def refresh_main_processes(self):
        """Обновление папки Основное с процессами."""
        result = self.main_processes_builder.build_tree()
        if result:
            folder_item, process_count = result
            folder_index = self.tree.model().indexFromItem(folder_item)
            self.tree.setFirstColumnSpanned(folder_index.row(), folder_index.parent(), True)
            for proc_row in range(process_count):
                self.tree.setFirstColumnSpanned(proc_row, folder_index, True)

    def expand_and_select_initial(self):
        """Разворачивает нужные папки и устанавливает курсор."""
        opened_folder_idx = None
        main_folder_idx = None
        recent_folder_idx = None

        for folder_idx in range(self.model.rowCount()):
            folder_item = self.model.item(folder_idx, 0)
            if not folder_item:
                continue
            if "Открытые базы" in folder_item.text():
                opened_folder_idx = folder_idx
            elif "Основное" in folder_item.text():
                main_folder_idx = folder_idx
            elif "Недавние" in folder_item.text():
                recent_folder_idx = folder_idx

        # Раскрываем узлы "Открытые базы" и "Основное"
        if opened_folder_idx is not None:
            folder_item = self.model.item(opened_folder_idx, 0)
            if folder_item and folder_item.rowCount() > 0:
                self.tree.expand(self.model.index(opened_folder_idx, 0))

        if main_folder_idx is not None:
            folder_item = self.model.item(main_folder_idx, 0)
            if folder_item and folder_item.rowCount() > 0:
                self.tree.expand(self.model.index(main_folder_idx, 0))

        # Приоритет 1: папка "Открытые базы"
        if opened_folder_idx is not None:
            folder_item = self.model.item(opened_folder_idx, 0)
            folder_index = self.model.index(opened_folder_idx, 0)
            if folder_item.rowCount() > 0:
                if self.last_activated_process and isinstance(self.last_activated_process, Process1C):
                    for proc_idx in range(folder_item.rowCount()):
                        proc_item = folder_item.child(proc_idx, 0)
                        if proc_item:
                            proc = proc_item.data(Qt.UserRole)
                            if (
                                proc
                                and isinstance(proc, Process1C)
                                and proc.pid == self.last_activated_process.pid
                            ):
                                proc_index = self.model.index(proc_idx, 0, folder_index)
                                self.tree.setCurrentIndex(proc_index)
                                self.tree.scrollTo(proc_index)
                                return
                first_proc_index = self.model.index(0, 0, folder_index)
                self.tree.setCurrentIndex(first_proc_index)
                self.tree.scrollTo(first_proc_index)
                return

        # Приоритет 2: папка "Основное"
        if main_folder_idx is not None:
            folder_item = self.model.item(main_folder_idx, 0)
            folder_index = self.model.index(main_folder_idx, 0)
            if folder_item.rowCount() > 0:
                if self.last_activated_main_process and hasattr(self.last_activated_main_process, 'pid'):
                    for proc_idx in range(folder_item.rowCount()):
                        proc_item = folder_item.child(proc_idx, 0)
                        if proc_item:
                            proc = proc_item.data(Qt.UserRole)
                            if (
                                proc
                                and hasattr(proc, 'pid')
                                and proc.pid == self.last_activated_main_process.pid
                            ):
                                proc_index = self.model.index(proc_idx, 0, folder_index)
                                self.tree.setCurrentIndex(proc_index)
                                self.tree.scrollTo(proc_index)
                                return
                first_proc_index = self.model.index(0, 0, folder_index)
                self.tree.setCurrentIndex(first_proc_index)
                self.tree.scrollTo(first_proc_index)
                return

        # Приоритет 3: папка "Недавние"
        if recent_folder_idx is not None:
            folder_item = self.model.item(recent_folder_idx, 0)
            folder_index = self.model.index(recent_folder_idx, 0)
            self.tree.expand(folder_index)
            if self.last_launched_db:
                for db_idx in range(folder_item.rowCount()):
                    db_item = folder_item.child(db_idx, 0)
                    if db_item:
                        db = db_item.data(Qt.UserRole)
                        if db and db.id == self.last_launched_db.id:
                            db_index = self.model.index(db_idx, 0, folder_index)
                            self.tree.setCurrentIndex(db_index)
                            self.tree.scrollTo(db_index)
                            return
            if folder_item.rowCount() > 0:
                first_db_index = self.model.index(0, 0, folder_index)
                self.tree.setCurrentIndex(first_db_index)
                self.tree.scrollTo(first_db_index)
