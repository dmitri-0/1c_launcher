"""Миксин для запуска консоли сервера 1С (MMC-оснастка через PowerShell)."""

import os
import sys
import tempfile
import platform
import subprocess
from pathlib import Path

# Fallback-текст PS1, если файл не найден (например, в собранном exe).
# Важно: пишем во временный файл в кодировке utf-8-sig (с BOM), как у исходника.
_PS1_START_1C_CONSOLE_FALLBACK = r'''# Принимаем параметры из Python (или командной строки)
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


class DbServerConsoleMixin:
    """Запуск консоли сервера 1С (MMC) через PowerShell-скрипт."""

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

        # 1) Обычный запуск из исходников: рядом с _db_server_console_mixin.py
        candidates.append(Path(__file__).resolve().parent / "Start-1C-Console.ps1")

        # 2) Если пользователь запускает из корня проекта
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

        # Файл не найден — создаём временный
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="Start-1C-Console-", suffix=".ps1")
            os.close(fd)
            tmp = Path(tmp_path)
            # Записываем с явным указанием utf-8-sig (BOM важен для PowerShell)
            tmp.write_text(_PS1_START_1C_CONSOLE_FALLBACK, encoding="utf-8-sig")
            self._temp_console_ps1_path = str(tmp)
            return tmp
        except Exception as e:
            self.window.statusBar.showMessage(f"❌ Не удалось создать временный PS1: {e}")
            return None
