from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING


class BasesDataMixin:
    """Миксин для загрузки и сохранения данных баз 1С."""

    def load_bases(self):
        """Загрузка баз из ibases.v8i."""
        reader = BaseReader(IBASES_PATH, ENCODING)
        self.all_bases.clear()
        self.all_bases.extend(reader.read_bases())
        self.tree_builder.build_tree(self.all_bases)

    def save_bases(self):
        """Сохранение баз в ibases.v8i."""
        try:
            with open(IBASES_PATH, 'w', encoding=ENCODING) as f:
                for base in self.all_bases:
                    f.write(f"[{base.name}]\n")
                    f.write(f"ID={base.id}\n")
                    f.write(f"Connect={base.connect}\n")
                    f.write(f"Folder={base.folder}\n")
                    if base.is_recent:
                        f.write("IsRecent=1\n")
                    if base.last_run_time:
                        f.write(f"LastRunTime={base.last_run_time.isoformat()}\n")
                    if base.app:
                        f.write(f"App={base.app}\n")
                    if base.version:
                        f.write(f"Version={base.version}\n")
                    if base.app_arch:
                        f.write(f"AppArch={base.app_arch}\n")
                    if base.client_type:
                        f.write(f"ClientType={base.client_type}\n")
                    if base.order_in_tree is not None:
                        f.write(f"OrderInTree={base.order_in_tree}\n")
                    if base.usr:
                        f.write(f"Usr={base.usr}\n")
                    if base.pwd:
                        f.write(f"Pwd={base.pwd}\n")
                    if base.storage_path:
                        f.write(f"StoragePath={base.storage_path}\n")
                    if base.usr_enterprise:
                        f.write(f"UsrEnterprise={base.usr_enterprise}\n")
                    if base.pwd_enterprise:
                        f.write(f"PwdEnterprise={base.pwd_enterprise}\n")
                    if base.usr_configurator:
                        f.write(f"UsrConfigurator={base.usr_configurator}\n")
                    if base.pwd_configurator:
                        f.write(f"PwdConfigurator={base.pwd_configurator}\n")
                    if base.usr_storage:
                        f.write(f"UsrStorage={base.usr_storage}\n")
                    if base.pwd_storage:
                        f.write(f"PwdStorage={base.pwd_storage}\n")
                    f.write("\n")
        except Exception as e:
            self.statusBar.showMessage(f"\u274c Ошибка сохранения: {e}")

    def reload_and_navigate(self):
        """Перечитать базы и обновить дерево с навигацией."""
        self.load_bases()
        self.refresh_opened_bases()
        self.refresh_main_processes()
        self.expand_and_select_initial()
