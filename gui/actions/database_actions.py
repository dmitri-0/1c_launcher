"""Действия для запуска и взаимодействия с базами 1С.

Отвечает за:
- Запуск предприятия и конфигуратора
- Парсинг строк подключения
- Поиск исполняемых файлов 1С
- Работу с недавними базами
- Запуск консоли сервера 1С (MMC)
"""

import os
import re
import tempfile
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QTimer

from config import IR_TOOLS_PATH


class DatabaseActions:
    """Класс для работы с действиями над базами данных 1С.

    Attributes:
        window: Ссылка на главное окно приложения
        all_bases: Список всех баз данных
        last_launched_db: Последняя запущенная база
        save_callback: Функция обратного вызова для сохранения баз
        reload_callback: Функция обратного вызова для перезагрузки UI
    """

    def __init__(self, window, all_bases, save_callback, reload_callback):
        """Инициализация менеджера действий.

        Args:
            window: Объект главного окна
            all_bases: Список всех баз данных
            save_callback: Функция для сохранения баз
            reload_callback: Функция для перезагрузки UI
        """
        self.window = window
        self.all_bases = all_bases
        self.last_launched_db = None
        self.save_callback = save_callback
        self.reload_callback = reload_callback

    def open_database(self, database):
        """Открывает базу в режиме предприятия.

        Args:
            database: Объект базы данных

        Returns:
            bool: True если запуск успешен
        """
        executable = self._get_1c_executable(database)
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти исполняемый файл 1C")
            return False

        if self._launch_1c_process(executable, "ENTERPRISE", database):
            self._move_to_recent(database)
            self._delayed_reload_after_launch()
            return True
        else:
            self.window.statusBar.showMessage(f"❌ Ошибка при запуске базы {database.name}")
            return False

    def open_configurator(self, database):
        """Открывает базу в режиме конфигуратора.

        Args:
            database: Объект базы данных

        Returns:
            bool: True если запуск успешен
        """
        executable = self._get_1c_executable(database, mode='DESIGNER')
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти исполняемый файл 1C")
            return False

        if self._launch_1c_process(executable, "DESIGNER", database):
            self._move_to_recent(database)
            self._delayed_reload_after_launch()
            return True
        else:
            self.window.statusBar.showMessage(f"❌ Ошибка при запуске конфигуратора для {database.name}")
            return False

    def open_ir_tools(self, database):
        """Открывает базу с запуском инструментов ИР (F5).

        Используется толстый клиент и специальный набор параметров.
        """
        executable = self._get_1c_executable(database, mode='IR_TOOLS')
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти исполняемый файл 1C")
            return False

        if self._launch_1c_process(executable, "IR_TOOLS", database):
            self._move_to_recent(database)
            self._delayed_reload_after_launch()
            return True
        else:
            self.window.statusBar.showMessage(f"❌ Ошибка при запуске инструментов ИР для {database.name}")
            return False

    def open_server_console(self, database):
        """Запускает консоль сервера 1С (MMC оснастка) для версии базы.

        Для запуска используется PowerShell-скрипт gui/actions/Start-1C-Console.ps1,
        которому передаются:
        - -Ver: версия платформы (например, 8.3.23.2040)
        - -IsX64String: "true"/"false" (строка)

        Returns:
            bool: True если команда сформирована и процесс запуска инициирован.
        """
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Консоль сервера 1С доступна только в Windows")
            return False

        version = (database.version or '').strip()
        if not version:
            self.window.statusBar.showMessage("❌ У базы не указана версия платформы (Version=...)")
            return False

        # В проекте разрядность хранится как AppArch; в _get_1c_executable проверяется x86_64
        app_arch = (database.app_arch or '').lower().strip()
        is_x64 = app_arch in {"x86_64", "x64", "amd64"}
        x64_str = "true" if is_x64 else "false"

        script_path = Path(__file__).resolve().parent / "Start-1C-Console.ps1"
        if not script_path.exists():
            self.window.statusBar.showMessage(f"❌ Не найден скрипт: {script_path}")
            return False

        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script_path),
            "-Ver", version,
            "-IsX64String", x64_str
        ]

        self.window.statusBar.showMessage(f"🛠️ Запуск консоли сервера 1С: {version}, x64={x64_str}")

        try:
            # Не блокируем GUI: PS-скрипт сам поднимает UAC и запускает mmc.exe
            subprocess.Popen(cmd, shell=False)
            return True
        except FileNotFoundError:
            self.window.statusBar.showMessage("❌ Не найден powershell.exe")
            return False
        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка запуска консоли сервера 1С: {e}")
            return False

    def _parse_server_connect_string(self, connect_string):
        """Парсит строку подключения серверной базы.

        Преобразует формат вида Srvr="server";Ref="base" в server\\base

        Args:
            connect_string: Строка подключения

        Returns:
            str: Преобразованная строка подключения
        """
        try:
            srvr_match = re.search(r'Srvr="([^"]+)"', connect_string, re.IGNORECASE)
            ref_match = re.search(r'Ref="([^"]+)"', connect_string, re.IGNORECASE)

            if srvr_match and ref_match:
                server = srvr_match.group(1)
                ref = ref_match.group(1)
                return f"{server}\\{ref}"

            return connect_string

        except Exception as e:
            print(f"Ошибка парсинга строки подключения: {e}")
            return connect_string

    def _build_launch_command(self, executable, mode, database):
        """Формирует командную строку для запуска 1С.

        Args:
            executable: Путь к исполняемому файлу 1С
            mode: Режим запуска ('ENTERPRISE', 'DESIGNER' или 'IR_TOOLS')
            database: Объект базы данных

        Returns:
            str: Командная строка для запуска или None при ошибке
        """
        try:
            params = [mode if mode != 'IR_TOOLS' else 'ENTERPRISE']

            if database.connect:
                parsed_connect = self._parse_server_connect_string(database.connect)
                params.append(f'/S"{parsed_connect}"')

            # Используем учетные данные в зависимости от режима
            usr = None
            pwd = None

            if mode == 'ENTERPRISE' or mode == 'IR_TOOLS':
                usr = database.usr_enterprise or database.usr
                pwd = database.pwd_enterprise or database.pwd
            elif mode == 'DESIGNER':
                usr = database.usr_configurator or database.usr
                pwd = database.pwd_configurator or database.pwd

            if usr:
                params.append(f'/N"{usr}"')
            if pwd:
                params.append(f'/P"{pwd}"')

            # Для запуска инструментов ИР добавляем специальные параметры
            if mode == 'IR_TOOLS':
                params.extend([
                    '/RunModeOrdinaryApplication',
                    '/Debug -attach',
                    '/DebuggerURL tcp://localhost',
                    '/UC""',
                    f'/Execute"{IR_TOOLS_PATH}"',
                    '/WA-'
                ])

            if mode == 'ENTERPRISE':
                params.extend([
                    '/Debug -attach',
                    '/DebuggerURL tcp://localhost'
                ])

            cmd_line = f'"{executable}" ' + ' '.join(
                f'"{p}"' if ' ' in p and not p.startswith('/') else p
                for p in params
            )

            return cmd_line

        except Exception as e:
            print(f"Ошибка формирования командной строки: {e}")
            return None

    def _launch_1c_process(self, executable, mode, database):
        """Запускает процесс 1С через временный BAT-файл.

        Args:
            executable: Путь к исполняемому файлу
            mode: Режим запуска
            database: База данных

        Returns:
            bool: True если запуск успешен
        """
        try:
            cmd_line = self._build_launch_command(executable, mode, database)

            if not cmd_line:
                return False

            self.window.statusBar.showMessage(f"🚀 Запуск: {cmd_line}")

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='cp866'
            ) as bat_file:
                bat_file.write('@echo off\n')
                bat_file.write(f'start "" {cmd_line}\n')
                bat_file.write('exit\n')
                bat_path = bat_file.name

            os.startfile(bat_path)
            QTimer.singleShot(3000, lambda: self._cleanup_temp_file(bat_path))

            return True

        except Exception as e:
            print(f"Ошибка запуска через BAT: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _cleanup_temp_file(self, filepath):
        """Удаляет временный файл.

        Args:
            filepath: Путь к файлу
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass

    def _move_to_recent(self, database):
        """Помечает базу как недавнюю и перемещает в начало списка.

        Args:
            database: База данных
        """
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

    def _get_1c_executable(self, database, mode=None):
        """Определяет путь к исполняемому файлу 1C с учетом разрядности и типа клиента.

        Args:
            database: База данных
            mode: Режим запуска (ENTERPRISE, DESIGNER, CREATEINFOBASE и т.д.)

        Returns:
            Path: Путь к исполняемому файлу или None
        """
        bitness = database.app_arch or 'x86'
        client_type = database.client_type or 'thick'

        # Определяем имя файла в зависимости от типа клиента
        if client_type == 'thin':
            exe_name = '1cv8c.exe'
        else:
            exe_name = '1cv8.exe'

        if mode == 'IR_TOOLS' or mode == 'DESIGNER':
            exe_name = '1cv8.exe'

        if database.app:
            path = Path(database.app)
            if path.exists():
                return path

        if platform.system() == 'Windows':
            if database.version:
                version = database.version
                if bitness == 'x86_64':
                    path = Path(rf"C:\Program Files\1cv8\{version}\bin\{exe_name}")
                else:
                    path = Path(rf"C:\Program Files (x86)\1cv8\{version}\bin\{exe_name}")

                if path.exists():
                    return path

            # Проверяем общие пути (только для толстого клиента)
            if client_type == 'thick':
                common_paths = [
                    Path(r"C:\Program Files\1cv8\common\1cestart.exe"),
                    Path(r"C:\Program Files (x86)\1cv8\common\1cestart.exe"),
                ]

                for path in common_paths:
                    if path.exists():
                        return path

        return None
