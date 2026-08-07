"""
Конфигурация лаунчера 1С.

Настройки хранятся во ВНЕШНЕМ файле `launcher.toml` (рядом с exe в сборке,
в исходниках — рядом с этим модулем) и читаются динамически при каждом запуске.
Благодаря этому настройки меняются без пересборки проекта.

Если файл не найден или повреждён — используются встроенные значения ниже.
Все модули обращаются к константам этого модуля, API не изменился.
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None

# Имя внешнего файла настроек
CONFIG_FILE_NAME = "launcher.toml"


# ------------------------------------------------------------------ #
#  Встроенные значения по умолчанию (используются, если launcher.toml
#  отсутствует или в нём не задан нужный ключ)                      #
# ------------------------------------------------------------------ #
def _default_settings() -> dict:
    return {
        "ibases_path": str(
            Path(os.getenv('USERPROFILE', '')) / 'AppData' / 'Roaming' / '1C' / '1CEStart' / 'ibases.v8i'
        ),
        "encoding": 'utf-8-sig',
        "ir_tools_path": r"c:\ROOT\CodeBase\1C\Tools\ИР_Портативный\ирПортативный.epf",
        "cf_dump_path": r"D:\CF",
        "log_path": r"D:\CF\Logs",
        "dbm_python_exe": r"c:\ROOT\CodeBase\Py\dbm_api\venv\Scripts\python.exe",
        "dbm_script_path": r"c:\ROOT\CodeBase\Py\dbm_api\app.py",
        "dbm_api_dir": r"c:\ROOT\CodeBase\Py\dbm_api",
        "hotkey": {
            "modifiers": 0x0001,  # MOD_ALT
            "vk": 0x44,           # D
        },
        "notes": {
            "path": "",  # пусто = notes.db рядом с exe
            "panel_width_percent": 80,  # доля ширины окна для панели заметок
        },
        # Отслеживаемые приложения для узла "Основное"
        "tracked_applications": [
            {
                "process_name": "reasonix-desktop.exe",
                "display_name": "Rx",
                "icon": "❯_",
                "launch_path": r"c:\ROOT\Reasonix-windows-amd64\Reasonix.exe",
            },
            {
                "process_name": "WindowsTerminal.exe",
                "display_name": "Terminal",
                "icon": "❯_",
                "launch_path": r"wt.exe",
            },
            {
                "process_name": "TOTALCMD64.EXE",
                "display_name": "Total Commander",
                "icon": "💾",
                "launch_path": r"c:\ROOT\TCPU75\TOTALCMD64.EXE",
            },
            {
                "process_name": "Code.exe",
                "display_name": "VS Code",
                "icon": "🔷",
                "launch_path": r"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
            },
            {
                "process_name": "msedge.exe",
                "display_name": "MS Edge",
                "icon": " ",
                "launch_path": r"c:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            },
            {
                "process_name": "Telegram.exe",
                "display_name": "Telegram",
                "icon": " ",
                "launch_path": r"c:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe",
            },
            {
                "process_name": "thunderbird.exe",
                "display_name": "Thunderbird",
                "icon": " ",
                "launch_path": r"c:\Program Files\Mozilla Thunderbird\thunderbird.exe",
            },
        ],
    }


# ------------------------------------------------------------------ #
#  Поиск и чтение внешнего файла настроек                            #
# ------------------------------------------------------------------ #
def find_config_file() -> Optional[Path]:
    """
    Найти launcher.toml.

    Приоритет:
      1) рядом с exe (сборка PyInstaller) — настройки меняются без пересборки;
      2) рядом с этим модулем (исходники, src/launcher.toml);
      3) текущая рабочая директория.
    """
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / CONFIG_FILE_NAME)
    candidates.append(Path(__file__).resolve().parent / CONFIG_FILE_NAME)
    candidates.append(Path.cwd() / CONFIG_FILE_NAME)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


# Модификаторы Windows: MOD_ALT=0x0001, MOD_CONTROL=0x0002, MOD_SHIFT=0x0004, MOD_WIN=0x0008
_MODIFIER_BITS = {
    "win": 0x0008,
    "alt": 0x0001,
    "ctrl": 0x0002,
    "control": 0x0002,
    "shift": 0x0004,
}


def _parse_modifiers(value) -> int:
    """Модификаторы: число (1|2|4|8) или строка вида 'Alt+Ctrl+Shift'."""
    if isinstance(value, int):
        return value & 0xFFFF
    if isinstance(value, str):
        result = 0
        for part in value.replace(" ", "").lower().split("+"):
            if not part:
                continue
            bit = _MODIFIER_BITS.get(part)
            if bit:
                result |= bit
            else:
                print(f"{CONFIG_FILE_NAME}: неизвестный модификатор '{part}' — проигнорирован")
        return result
    return 0x0001


def _parse_vk(value) -> int:
    """Виртуальный код клавиши: число, '0x44' или '68'."""
    if isinstance(value, int):
        return value
    try:
        return int(str(value), 0)
    except ValueError:
        print(f"{CONFIG_FILE_NAME}: неверный VK '{value}' — используется 0x44 (D)")
        return 0x44


def _merge(settings: dict, data: dict) -> None:
    """Накладывает прочитанный TOML поверх встроенных значений.

    Путевые ключи читаются из секции [base] (или из корня, если секции нет);
    [hotkey] и [[tracked_applications]] — корневые таблицы TOML.
    """
    sources = [data.get("base")] if isinstance(data.get("base"), dict) else []
    sources.append(data)

    for key in ("ibases_path", "encoding", "ir_tools_path", "cf_dump_path", "log_path",
                "dbm_python_exe", "dbm_script_path", "dbm_api_dir"):
        for src in sources:
            if key in src:
                settings[key] = str(src[key])
                break

    hotkey = data.get("hotkey")
    if isinstance(hotkey, dict):
        if "modifiers" in hotkey:
            settings["hotkey"]["modifiers"] = _parse_modifiers(hotkey["modifiers"])
        if "vk" in hotkey:
            settings["hotkey"]["vk"] = _parse_vk(hotkey["vk"])

    notes = data.get("notes")
    if isinstance(notes, dict):
        if "path" in notes:
            settings["notes"]["path"] = str(notes["path"])
        if "panel_width_percent" in notes:
            try:
                settings["notes"]["panel_width_percent"] = int(notes["panel_width_percent"])
            except (TypeError, ValueError):
                pass  # некорректное значение — оставляем дефолт

    apps = data.get("tracked_applications")
    if isinstance(apps, list) and apps:
        normalized = []
        for app in apps:
            if not isinstance(app, dict):
                continue
            normalized.append({
                "process_name": str(app.get("process_name", "")),
                "display_name": str(app.get("display_name", app.get("process_name", ""))),
                "icon": str(app.get("icon", " ")),
                "launch_path": str(app.get("launch_path", "")),
            })
        if normalized:
            settings["tracked_applications"] = normalized


def load_settings(config_path: Optional[os.PathLike] = None) -> dict:
    """
    Загрузить настройки: внешний launcher.toml поверх встроенных значений.

    Args:
        config_path: Явный путь к файлу (для тестов). Если None — ищется автоматически.

    Returns:
        Словарь настроек (всегда полный, с дефолтами для отсутствующих ключей).
    """
    settings = _default_settings()

    path = Path(config_path) if config_path else find_config_file()
    if path is None or not path.is_file():
        return settings

    if tomllib is None:
        print("Для чтения launcher.toml нужен Python 3.11+ (tomllib) — используются встроенные настройки.")
        return settings

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        _merge(settings, data)
        print(f"Настройки загружены из: {path}")
    except Exception as e:
        print(f"Ошибка чтения настроек {path}: {e} — используются встроенные значения")
    return settings


# ------------------------------------------------------------------ #
#  Публичный API модуля (не менять — используется по всему коду)     #
# ------------------------------------------------------------------ #
_SETTINGS = load_settings()

# Путь к файлу со списком баз 1С
IBASES_PATH = Path(_SETTINGS["ibases_path"])

# Кодировка файла ibases.v8i
ENCODING = _SETTINGS["encoding"]

# Путь к обработке инструментов ИР
IR_TOOLS_PATH = _SETTINGS["ir_tools_path"]

# Путь для выгрузки CF (папка)
CF_DUMP_PATH = Path(_SETTINGS["cf_dump_path"])

# Путь к лог-файлу операций
LOG_PATH = Path(_SETTINGS["log_path"])

# Пути для запуска DBM API
DBM_PYTHON_EXE = _SETTINGS["dbm_python_exe"]
DBM_SCRIPT_PATH = _SETTINGS["dbm_script_path"]
DBM_API_DIR = _SETTINGS["dbm_api_dir"]

# Глобальная горячая клавиша вызова окна / аварийного сброса ожидания закрытия (Del).
# Настраивается в launcher.toml ([hotkey]) — читается динамически.
GLOBAL_HOTKEY_MODIFIERS = _SETTINGS["hotkey"]["modifiers"]
GLOBAL_HOTKEY_VK = _SETTINGS["hotkey"]["vk"]

# Путь к БД заметок (SQLite). Пустая строка = notes.db рядом с exe/модулем.
NOTES_PATH = _SETTINGS["notes"].get("path", "")

# Доля ширины окна для панели заметок (в процентах, 20–95).
NOTES_PANEL_WIDTH_PERCENT = _SETTINGS["notes"].get("panel_width_percent", 80)

# Отслеживаемые приложения для узла "Основное"
TRACKED_APPLICATIONS = _SETTINGS["tracked_applications"]


def get_launch_path(app_config):
    """
    Получить путь запуска приложения с подстановкой переменных окружения

    Args:
        app_config: Словарь конфигурации приложения

    Returns:
        Обработанный путь запуска
    """
    launch_path = app_config.get("launch_path", "")
    # Подставляем имя пользователя
    if "{username}" in launch_path:
        username = os.getenv('USERNAME', '')
        launch_path = launch_path.replace("{username}", username)
    return launch_path
