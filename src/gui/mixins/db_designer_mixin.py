"""Миксин для Designer bat-операций: UpdateDBCfg, DumpCfg, RepositoryUpdateCfg."""

import os
import re
import tempfile
import platform
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QTimer

from config import CF_DUMP_PATH, LOG_PATH


class DbDesignerMixin:
    """Операции конфигуратора через временные BAT-файлы."""

    # ------------------------------------------------------------------ #
    #  Публичные методы                                                    #
    # ------------------------------------------------------------------ #

    def save_cfg(self, database):
        """F7: обновление конфигурации БД (Designer /UpdateDBCfg)."""
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Операция поддерживается только в Windows")
            return False

        executable = self._get_1c_executable(database, mode='DESIGNER')
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти 1cv8.exe для конфигуратора")
            return False

        try:
            base_stem = self._build_base_stem(database)
            log_file = self._build_action_log_path(base_stem, action_name="UpdateDBCfg")

            log_file.parent.mkdir(parents=True, exist_ok=True)

            bat_text = self._build_update_db_cfg_bat(
                executable=Path(executable),
                database=database,
                log_file=log_file,
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='utf-8'
            ) as bat_file:
                bat_file.write(bat_text)
                bat_path = bat_file.name

            self.window.statusBar.showMessage(f"💾 Обновление конфигурации запущено (log: {log_file})")
            self._run_bat_and_cleanup(bat_path)
            return True

        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка подготовки UpdateDBCfg: {e}")
            return False

    def update_cfg_from_repository(self, database):
        """Ctrl+F7: обновление конфигурации из хранилища и сохранение (Designer).

        Делает ConfigurationRepositoryUpdateCfg и затем UpdateDBCfg в одном вызове,
        как в предоставленном примере BAT.
        """
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Операция поддерживается только в Windows")
            return False

        executable = self._get_1c_executable(database, mode='DESIGNER')
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти 1cv8.exe для конфигуратора")
            return False

        try:
            base_stem = self._build_base_stem(database)
            log_file = self._build_action_log_path(base_stem, action_name="RepositoryUpdateCfg")

            log_file.parent.mkdir(parents=True, exist_ok=True)

            bat_text = self._build_repo_update_cfg_bat(
                executable=Path(executable),
                database=database,
                log_file=log_file,
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='utf-8'
            ) as bat_file:
                bat_file.write(bat_text)
                bat_path = bat_file.name

            self.window.statusBar.showMessage(f"📥 Обновление из хранилища запущено (log: {log_file})")
            self._run_bat_and_cleanup(bat_path)
            return True

        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка подготовки RepositoryUpdateCfg: {e}")
            return False

    def dump_cf(self, database):
        """Выгрузка конфигурации в CF (Designer /DumpCfg)."""
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
            log_file = self._build_action_log_path(dump_file.stem, action_name="DumpCfg")

            dump_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            bat_text = self._build_dump_cf_bat(
                executable=Path(executable),
                database=database,
                dump_file=dump_file,
                log_file=log_file,
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='utf-8'
            ) as bat_file:
                bat_file.write(bat_text)
                bat_path = bat_file.name

            self.window.statusBar.showMessage(f"📦 Выгрузка CF запущена: {dump_file} (log: {log_file})")
            self._run_bat_and_cleanup(bat_path)
            return True

        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка подготовки DumpCfg: {e}")
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

            # Готовим директории
            dump_file.parent.mkdir(parents=True, exist_ok=True)
            log_dir = self._get_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)

            bat_text = self._build_save_and_dump_cf_bat(
                executable=Path(executable),
                database=database,
                dump_file=dump_file
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='utf-8'
            ) as bat_file:
                bat_file.write(bat_text)
                bat_path = bat_file.name

            self.window.statusBar.showMessage(f"💾 Обновление и выгрузка CF запущена: {dump_file}")
            self._run_bat_and_cleanup(bat_path)
            return True

        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка подготовки выгрузки CF: {e}")
            return False

    def update_cfg_from_repository_and_dump_cf(self, database):
        """Обновление конфигурации из хранилища, сохранение БД и выгрузка конфигурации в CF (Designer)."""
        if not database:
            self.window.statusBar.showMessage("❌ База не выбрана")
            return False

        if platform.system() != 'Windows':
            self.window.statusBar.showMessage("❌ Операция поддерживается только в Windows")
            return False

        executable = self._get_1c_executable(database, mode='DESIGNER')
        if not executable:
            self.window.statusBar.showMessage("❌ Не удалось найти 1cv8.exe для конфигуратора")
            return False

        try:
            dump_file = self._build_cf_dump_path(database)
            
            # Готовим директории
            dump_file.parent.mkdir(parents=True, exist_ok=True)
            log_dir = self._get_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)

            base_stem = dump_file.stem
            log_update = self._build_action_log_path(base_stem, "RepositoryUpdateCfg")
            log_dump = self._build_action_log_path(base_stem, "DumpCfg")

            bat_text = self._build_repo_update_and_dump_cf_bat(
                executable=Path(executable),
                database=database,
                dump_file=dump_file,
                log_update=log_update,
                log_dump=log_dump,
            )

            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.bat',
                delete=False,
                encoding='utf-8'
            ) as bat_file:
                bat_file.write(bat_text)
                bat_path = bat_file.name

            self.window.statusBar.showMessage(f"📥 Обновление из хранилища и выгрузка CF запущена (log: {log_update})")
            self._run_bat_and_cleanup(bat_path)
            return True

        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Ошибка подготовки RepositoryUpdateCfg+DumpCfg: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Вспомогательные методы путей / имён файлов                         #
    # ------------------------------------------------------------------ #

    def _build_base_stem(self, database) -> str:
        """Формирует базовую часть имени файла: <ИМЯ_БАЗЫ>_<YYMMDD>_<HHMM>."""
        base_name = (database.name or "database").strip()
        safe = self._sanitize_filename(base_name)
        if not safe:
            safe = "database"

        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M")
        return f"{safe}_{timestamp}"

    def _build_cf_dump_path(self, database) -> Path:
        """Формирует путь к .cf для выгрузки в формате <ИМЯ_БАЗЫ>_<YYMMDD>_<HHMM>.cf"""
        stem = self._build_base_stem(database)
        return Path(CF_DUMP_PATH) / f"{stem}.cf"

    def _get_log_dir(self) -> Path:
        base = Path(LOG_PATH)
        return base.parent if base.suffix else base

    def _build_action_log_path(self, base_stem: str, action_name: str) -> Path:
        """Формирует имя лог-файла: <STEM>_log_<ACTION><ext>."""
        base = Path(LOG_PATH)
        log_dir = base.parent if base.suffix else base
        ext = base.suffix if base.suffix else ".txt"

        safe_action = self._sanitize_filename(action_name) or "action"
        return log_dir / f"{base_stem}_log_{safe_action}{ext}"

    def _sanitize_filename(self, value: str) -> str:
        """Очищает строку от символов, запрещённых в именах файлов Windows."""
        value = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', value)
        value = value.strip().strip('.')
        value = re.sub(r'\s+', ' ', value)
        return value

    # ------------------------------------------------------------------ #
    #  BAT-билдеры и запуск                                                #
    # ------------------------------------------------------------------ #

    def _run_bat_and_cleanup(self, bat_path: str):
        """Запускает BAT-файл в фоновом потоке и удаляет его только после полного завершения."""
        def worker():
            try:
                subprocess.run(["cmd", "/c", bat_path], shell=False)
            finally:
                try:
                    if hasattr(self, '_cleanup_temp_file'):
                        self._cleanup_temp_file(bat_path)
                    elif os.path.exists(bat_path):
                        os.remove(bat_path)
                except Exception as e:
                    print(f"Ошибка удаления временного файла {bat_path}: {e}")
                    
        threading.Thread(target=worker, daemon=True).start()

    def _build_update_db_cfg_bat(self, executable: Path, database, log_file: Path) -> str:
        """Генерирует BAT для Designer /UpdateDBCfg."""
        base_param = self._build_base_param_for_bat(database)
        credentials = self._build_credentials_for_bat(database)

        bat = []
        bat.append('@echo off')
        bat.append('chcp 65001 >nul')
        bat.append(f'set PLATFORM="{executable}"')
        bat.append(f'set BASE={base_param}')
        bat.append(f'set LOG="{log_file}"')
        bat.append(f'set CREDENTIALS={credentials}')
        bat.append('')

        bat.append('echo Обновление конфигурации БД...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /UpdateDBCfg /Out%LOG%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при обновлении конфигурации!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')
        bat.append('exit /b 0')
        bat.append('')

        return '\n'.join(bat)

    def _build_repo_update_cfg_bat(self, executable: Path, database, log_file: Path) -> str:
        """Генерирует BAT для обновления конфигурации из хранилища и сохранения.

        Выполняет:
        - /ConfigurationRepositoryUpdateCfg -v -1 -revised -force
        - /UpdateDBCfg
        """
        base_param = self._build_base_param_for_bat(database)
        credentials = self._build_credentials_for_bat(database)

        bat = []
        bat.append('@echo off')
        bat.append('chcp 65001 >nul')
        bat.append(f'set PLATFORM="{executable}"')
        bat.append(f'set BASE={base_param}')
        bat.append(f'set LOG="{log_file}"')
        bat.append(f'set CREDENTIALS={credentials}')
        bat.append('')

        bat.append('echo Обновление конфигурации из хранилища...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /ConfigurationRepositoryUpdateCfg -v -1 -revised -force /UpdateDBCfg /Out%LOG%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при обновлении конфигурации!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')
        bat.append('exit /b 0')
        bat.append('')

        return '\n'.join(bat)

    def _build_dump_cf_bat(self, executable: Path, database, dump_file: Path, log_file: Path) -> str:
        """Генерирует BAT для Designer /DumpCfg."""
        base_param = self._build_base_param_for_bat(database)
        credentials = self._build_credentials_for_bat(database)

        bat = []
        bat.append('@echo off')
        bat.append('chcp 65001 >nul')
        bat.append(f'set PLATFORM="{executable}"')
        bat.append(f'set BASE={base_param}')
        bat.append(f'set LOG="{log_file}"')
        bat.append(f'set DUMP="{dump_file}"')
        bat.append(f'set CREDENTIALS={credentials}')
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

    def _build_save_and_dump_cf_bat(self, executable: Path, database, dump_file: Path) -> str:
        """Генерирует BAT-скрипт по образцу из задачи (UpdateDBCfg + DumpCfg)."""
        base_param = self._build_base_param_for_bat(database)
        credentials = self._build_credentials_for_bat(database)

        base_stem = dump_file.stem

        # Получаем пути к разным лог-файлам для каждого действия
        log_update = self._build_action_log_path(base_stem, "UpdateDBCfg")
        log_dump = self._build_action_log_path(base_stem, "DumpCfg")

        bat = []
        bat.append('@echo off')
        bat.append('chcp 65001 >nul')
        bat.append(f'set PLATFORM="{executable}"')
        bat.append(f'set BASE={base_param}')
        bat.append(f'set LOG_UPDATE="{log_update}"')
        bat.append(f'set LOG_DUMP="{log_dump}"')
        bat.append(f'set DUMP="{dump_file}"')
        bat.append(f'set CREDENTIALS={credentials}')
        bat.append('')

        bat.append('echo Обновление конфигурации БД...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /UpdateDBCfg /Out%LOG_UPDATE%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при обновлении конфигурации!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')

        bat.append('echo Выгрузка конфигурации...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /DumpCfg%DUMP% /Out%LOG_DUMP%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при выгрузке!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')
        bat.append('exit /b 0')
        bat.append('')

        return '\n'.join(bat)
        
    def _build_repo_update_and_dump_cf_bat(self, executable: Path, database, dump_file: Path, log_update: Path, log_dump: Path) -> str:
        """Генерирует BAT для обновления конфигурации из хранилища и выгрузки CF (Ctrl+F7 + F8)."""
        base_param = self._build_base_param_for_bat(database)
        credentials = self._build_credentials_for_bat(database)

        bat = []
        bat.append('@echo off')
        bat.append('chcp 65001 >nul')
        bat.append(f'set PLATFORM="{executable}"')
        bat.append(f'set BASE={base_param}')
        bat.append(f'set LOG_UPDATE="{log_update}"')
        bat.append(f'set LOG_DUMP="{log_dump}"')
        bat.append(f'set DUMP="{dump_file}"')
        bat.append(f'set CREDENTIALS={credentials}')
        bat.append('')

        bat.append('echo Обновление конфигурации из хранилища...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /ConfigurationRepositoryUpdateCfg -v -1 -revised -force /UpdateDBCfg /Out%LOG_UPDATE%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при обновлении из хранилища!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')

        bat.append('echo Выгрузка конфигурации...')
        bat.append('%PLATFORM% DESIGNER %BASE% %CREDENTIALS% /DumpCfg%DUMP% /Out%LOG_DUMP%')
        bat.append('if errorlevel 1 (')
        bat.append('    echo ОШИБКА при выгрузке!')
        bat.append('    exit /b 1')
        bat.append(')')
        bat.append('')
        bat.append('exit /b 0')
        bat.append('')

        return '\n'.join(bat)

    def _build_base_param_for_bat(self, database) -> str:
        """Возвращает значение для переменной BASE в BAT (включая /S\"...\" если возможно)."""
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
