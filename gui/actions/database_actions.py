"""Действия для запуска и взаимодействия с базами 1С.

Отвечает за:
- Запуск предприятия и конфигуратора
- Парсинг строк подключения
- Поиск исполняемых файлов 1С
- Работу с недавними базами
- Запуск консоли сервера 1С (MMC)

Реализация разнесена по миксинам:
    _db_launch_mixin.py          — запуск баз (ENTERPRISE / DESIGNER / IR_TOOLS)
    _db_server_console_mixin.py  — консоль сервера 1С (MMC + PowerShell)
    _db_designer_mixin.py        — bat-операции конфигуратора (UpdateDBCfg, DumpCfg …)
    _db_recent_mixin.py          — управление недавними базами
"""

from ._db_launch_mixin import DbLaunchMixin
from ._db_server_console_mixin import DbServerConsoleMixin
from ._db_designer_mixin import DbDesignerMixin
from ._db_recent_mixin import DbRecentMixin


class DatabaseActions(
    DbLaunchMixin,
    DbServerConsoleMixin,
    DbDesignerMixin,
    DbRecentMixin,
):
    """Класс для работы с действиями над базами данных 1С.

    Attributes:
        window: Ссылка на главное окно приложения
        all_bases: Список всех баз данных
        last_launched_db: Последняя запущенная база
        save_callback: Функция обратного вызова для сохранения баз
        reload_callback: Функция обратного вызова для перезагрузки UI
    """

    def __init__(self, window, all_bases, save_callback, reload_callback):
        """Инициализация менеджера действий."""
        self.window = window
        self.all_bases = all_bases
        self.last_launched_db = None
        self.save_callback = save_callback
        self.reload_callback = reload_callback

        # Чтобы не создавать временный ps1 при каждом запуске.
        self._temp_console_ps1_path = None
