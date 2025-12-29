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
import sys
import tempfile
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QTimer

from config import IR_TOOLS_PATH, CF_DUMP_PATH, LOG_PATH


# Fallback-текст PS1, если файл не найден (например, в собранном exe).
# Важно: пишем во временный файл в кодировке utf-8-sig (с BOM), как у исходника.
_PS1_START_1C_CONSOLE_FALLBACK = r'''﻿# Принимаем параметры из Python (или командной строки)
param(
    [Parameter(Mandatory=$true)]
    [string]$Ver,          # Например: "8.3.25.1234"

    [Parameter(Mandatory=$true)]
    [string]$IsX64String   # "true" или "false" (строкой надежнее при вызове извне)
)

# Преобразуем строку в boolean
$IsX64 = [System.Convert]::ToBoolean($IsX64String)

# --- Блок авто-повышения прав (Self-Elevation) ---
$Id = [Security.Principal.WindowsIdentity]::GetCurrent()
$Pr = [Security.Principal.WindowsPrincipal]$Id
if (-not $Pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    # Формируем строку аргументов, чтобы передать их в новую админскую сессию
    $NewArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Definition)`" -Ver `"$Ver`" -IsX64String `"$IsX64String`""
    
    Start-Process powershell -Verb RunAs -ArgumentList $NewArgs
    Exit
}

# --- Основная логика ---
try {
    # 1. Определяем корневой путь и имя оснастки
    if ($IsX64) {
        $Root = $env:ProgramFiles
        $MscName = "1CV8 Servers (x86-64).msc"
        $ArchName = "x64"
    } else {
        $Root = ${env:ProgramFiles(x86)}
        # Если запущено на 32-битной Windows, переменная (x86) пуста, берем просто ProgramFiles
        if ([string]::IsNullOrEmpty($Root)) { $Root = $env:ProgramFiles }
        $MscName = "1CV8 Servers.msc"
        $ArchName = "x86"
    }

    $Dll = Join-Path $Root "1cv8\$Ver\bin\radmin.dll"

    # 2. Ищем файл .msc (проверяем оба места, т.к. Common общий)
    $MscPath1 = Join-Path $env:ProgramFiles "1cv8\common\$MscName"
    $MscPath2 = Join-Path ${env:ProgramFiles(x86)} "1cv8\common\$MscName"

    if (Test-Path $MscPath1) { $Msc = $MscPath1 }
    elseif (Test-Path $MscPath2) { $Msc = $MscPath2 }
    else { throw "Файл консоли '$MscName' не найден в папках common!" }

    # 3. Регистрация
    if (-not (Test-Path $Dll)) { throw "DLL не найдена: $Dll" }
    
    Write-Host "Версия: $Ver ($ArchName)" -ForegroundColor Yellow
    Write-Host "Регистрация: $Dll" -ForegroundColor Cyan
    Start-Process "regsvr32.exe" -ArgumentList "/s `"$Dll`"" -Wait

    # 4. Запуск
    Write-Host "Запуск: $Msc" -ForegroundColor Green
    Start-Process "mmc.exe" -ArgumentList "`"$Msc`""

} catch {
    Write-Error $_.Exception.Message
    Read-Host "Нажмите Enter для выхода..."
}
'''


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
        """Инициализация менеджера действий."""
        self.window = window
        self.all_bases = all_bases
        self.last_launched_db = None
        self.save_callback = save_callback
        self.reload_callback = reload_callback

        # Чтобы не создавать временный ps1 при каждом запуске.
        self._temp_console_ps1_path = None

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

    def save_and_dump_cf(self, database):
        """Обновление конфигурации БД и выгрузка конфигурации в CF (Designer).

        Создаёт BAT по образцу (chcp 65001, set PLATFORM/BASE/LOG/DUMP/CREDENTIALS),
        затем запускает его через cmd.exe.
        """
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Выгрузка CF поддерживается только в Windows")
            return False

        executable = self._get_1c_executable(database, mode='DESIGNER')
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти 1cv8.exe для конфигуратора")
            return False

        try:
            dump_file = self._build_cf_dump_path(database)
            log_file = self._build_action_log_path(dump_file, action_name="save_and_dump_cf")

            dump_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            bat_text = self._build_save_and_dump_cf_bat(
                executable=Path(executable),
                database=database,
                dump_file=dump_file,
                log_file=log_file,
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='utf-8-sig'
            ) as bat_file:
                bat_file.write(bat_text)
                bat_path = bat_file.name

            # Запускаем без блокировки GUI (в отдельном процессе cmd)
            subprocess.Popen(["cmd", "/c", bat_path], shell=False)

            self.window.statusBar.showMessage(f"💾 Выгрузка CF запущена: {dump_file} (log: {log_file})")

            # Убираем BAT позже (даём cmd время начать выполнение)
            QTimer.singleShot(60_000, lambda: self._cleanup_temp_file(bat_path))
            return True

        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка подготовки выгрузки CF: {e}")
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

    def open_server_console(self, database):
        """Запускает консоль сервера 1С (MMC оснастка) для версии базы."""
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

        app_arch = (database.app_arch or '').lower().strip()
        is_x64 = app_arch in {"x86_64", "x64", "amd64"}
        x64_str = "true" if is_x64 else "false"

        script_path = self._ensure_console_ps1()
        if not script_path:
            self.window.statusBar.showMessage("❌ Не удалось подготовить Start-1C-Console.ps1")
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

    def _console_ps1_candidates(self):
        """Возвращает список возможных путей к Start-1C-Console.ps1."""
        candidates = []

        # 1) Обычный запуск из исходников: рядом с database_actions.py
        candidates.append(Path(__file__).resolve().parent / "Start-1C-Console.ps1")

        # 2) Если пользователь запускает из корня проекта и ps1 лежит в текущей папке
        candidates.append(Path.cwd() / "Start-1C-Console.ps1")
        candidates.append(Path.cwd() / "gui" / "actions" / "Start-1C-Console.ps1")

        # 3) PyInstaller: временная папка распаковки onefile / папка bundle
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            candidates.append(base / "Start-1C-Console.ps1")
            candidates.append(base / "gui" / "actions" / "Start-1C-Console.ps1")

        # 4) Рядом с exe (частый сценарий для onedir или ручного копирования ps1 рядом)
        try:
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir / "Start-1C-Console.ps1")
            candidates.append(exe_dir / "gui" / "actions" / "Start-1C-Console.ps1")
        except Exception:
            pass

        # Убираем дубли, сохраняя порядок
        uniq = []
        seen = set()
        for p in candidates:
            ps = str(p)
            if ps not in seen:
                uniq.append(p)
                seen.add(ps)
        return uniq

    def _ensure_console_ps1(self) -> Path | None:
        """Гарантирует наличие ps1: ищет, иначе создаёт временный файл."""
        # Если уже создавали — переиспользуем
        if self._temp_console_ps1_path:
            try:
                p = Path(self._temp_console_ps1_path)
                if p.exists():
                    return p
            except Exception:
                self._temp_console_ps1_path = None

        for candidate in self._console_ps1_candidates():
            if candidate.exists():
                return candidate

        # Файл не найден (типично: забыли добавить data files при сборке) — создаём во временной папке.
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="Start-1C-Console-", suffix=".ps1", text=True)
            os.close(fd)
            tmp = Path(tmp_path)

            # utf-8-sig важен, потому что исходный файл в репозитории с BOM.
            tmp.write_text(_PS1_START_1C_CONSOLE_FALLBACK, encoding="utf-8-sig")

            self._temp_console_ps1_path = str(tmp)
            return tmp
        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Не удалось создать временный PS1: {e}")
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
        except:
            pass

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

    def _build_cf_dump_path(self, database) -> Path:
        """Формирует путь к .cf для выгрузки в формате <ИМЯ_БАЗЫ>_<YYMMDD>_<HHMM>.cf"""
        base_name = (database.name or "database").strip()
        safe = self._sanitize_filename(base_name)
        if not safe:
            safe = "database"

        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M")

        return Path(CF_DUMP_PATH) / f"{safe}_{timestamp}.cf"

    def _build_action_log_path(self, dump_file: Path, action_name: str) -> Path:
        """Формирует имя лог-файла по шаблону CF + 'log' + имя действия.

        Пример: <ИМЯ_БАЗЫ>_<YYMMDD>_<HHMM>_log_save_and_dump_cf.txt

        Папку берём из LOG_PATH (если в конфиге указан файл, то используем его parent).
        Расширение берём из LOG_PATH (если нет — .txt).
        """
        base = Path(LOG_PATH)
        log_dir = base.parent if base.suffix else base
        ext = base.suffix if base.suffix else ".txt"

        safe_action = self._sanitize_filename(action_name) or "action"
        return log_dir / f"{dump_file.stem}_log_{safe_action}{ext}"

    def _sanitize_filename(self, value: str) -> str:
        # Windows: запрещены <>:"/\\|?* и управляющие символы
        value = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', value)
        value = value.strip().strip('.')
        value = re.sub(r'\s+', ' ', value)
        return value

    def _build_save_and_dump_cf_bat(self, executable: Path, database, dump_file: Path, log_file: Path) -> str:
        """Генерирует BAT-скрипт по образцу из задачи."""
        base_param = self._build_base_param_for_bat(database)
        credentials = self._build_credentials_for_bat(database)

        # В BAT задаём переменные уже с кавычками, чтобы дальше использовать /Out%LOG% и /DumpCfg%DUMP%
        bat = []
        bat.append('@echo off')
        bat.append('chcp 65001 >nul')
        bat.append(f'set PLATFORM="{executable}"')
        bat.append(f'set BASE={base_param}')
        bat.append(f'set LOG="{log_file}"')
        bat.append(f'set DUMP="{dump_file}"')
        bat.append(f'set CREDENTIALS={credentials}')
        bat.append('')

        bat.append('echo Обновление конфигурации БД...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /UpdateDBCfg /Out%LOG%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при обновлении конфигурации!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')

        bat.append('echo Выгрузка конфигурации...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /DumpCfg%DUMP% /Out%LOG%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при выгрузке!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')
        bat.append('exit /b 0')
        bat.append('')

        return '\n'.join(bat)

    def _build_base_param_for_bat(self, database) -> str:
        """Возвращает значение для переменной BASE в BAT (включая /S"..." если возможно)."""
        connect = (database.connect or '').strip()
        if not connect:
            return ''

        parsed = self._parse_server_connect_string(connect)
        return f'/S"{parsed}"'

    def _build_credentials_for_bat(self, database) -> str:
        """Возвращает значение для переменной CREDENTIALS в BAT."""
        usr = database.usr_configurator or database.usr
        pwd = database.pwd_configurator or database.pwd

        parts = []
        if usr:
            parts.append(f'/N"{usr}"')
        if pwd:
            parts.append(f'/P"{pwd}"')

        return ' '.join(parts)
