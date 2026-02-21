"""Миксин для запуска баз 1С: предприятие, конфигуратор, ИР-инструменты."""

import os
import re
import tempfile
import platform
from pathlib import Path
from PySide6.QtCore import QTimer

from config import IR_TOOLS_PATH


class DbLaunchMixin:
    """Запуск 1С-процессов: предприятие, конфигуратор, ИР-инструменты."""

    def open_database(self, database):
        """Открывает базу в режиме предприятия."""
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
        """Открывает базу в режиме конфигуратора."""
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
        """Открывает базу с запуском инструментов ИР (F5)."""
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

    def _get_1c_executable(self, database, mode=None):
        """Определяет путь к исполняемому файлу 1C с учетом разрядности и типа клиента."""
        bitness = database.app_arch or 'x86'
        client_type = database.client_type or 'thick'

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

            if client_type == 'thick':
                common_paths = [
                    Path(r"C:\Program Files\1cv8\common\1cestart.exe"),
                    Path(r"C:\Program Files (x86)\1cv8\common\1cestart.exe"),
                ]

                for path in common_paths:
                    if path.exists():
                        return path

        return None

    def _parse_server_connect_string(self, connect_string):
        """Парсит строку подключения серверной базы."""
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
        """Формирует командную строку для запуска 1С."""
        try:
            params = [mode if mode != 'IR_TOOLS' else 'ENTERPRISE']

            if database.connect:
                parsed_connect = self._parse_server_connect_string(database.connect)
                params.append(f'/S"{parsed_connect}"')

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

            if mode == 'IR_TOOLS':
                params.extend([
                    '/RunModeOrdinaryApplication',
                    '/Debug -attach',
                    '/DebuggerURL tcp://localhost',
                    '/UC""',
                    f'/Execute"{IR_TOOLS_PATH}"',
                    '/WA-',
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
        """Запускает процесс 1С через временный BAT-файл."""
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
        """Удаляет временный файл."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
