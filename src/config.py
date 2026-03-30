import os
from pathlib import Path

# Путь к файлу со списком баз 1С
IBASES_PATH = Path(os.getenv('USERPROFILE')) / 'AppData' / 'Roaming' / '1C' / '1CEStart' / 'ibases.v8i'

# Кодировка файла ibases.v8i
ENCODING = 'utf-8-sig'

# Путь к обработке инструментов ИР
IR_TOOLS_PATH = r"c:\ROOT\CodeBase\1C\data\Tools\ИР_Портативный\ирПортативный.epf"

# Путь для выгрузки CF (папка)
CF_DUMP_PATH = Path(r"D:\CF")

# Путь к лог-файлу операций
LOG_PATH = Path(r"D:\CF\log.txt")

# Пути для запуска DBM API
DBM_PYTHON_EXE = r"c:\ROOT\CodeBase\Py\dbm_api\venv\Scripts\python.exe"
DBM_SCRIPT_PATH = r"c:\ROOT\CodeBase\Py\dbm_api\app.py"

# Отслеживаемые приложения для узла "Основное"
# Формат: {
#     "process_name": "имя процесса (например, Code.exe)",
#     "display_name": "отображаемое имя",
#     "icon": "emoji иконка",
#     "launch_path": "путь для запуска приложения"
# }
TRACKED_APPLICATIONS = [
    {
        "process_name": "WindowsTerminal.exe",
        "display_name": "Terminal",
        "icon": "❯_",
        "launch_path": r"wt.exe"  # Windows Terminal можно запустить через wt.exe
    },
    {
        "process_name": "TOTALCMD.EXE",
        "display_name": "Total Commander",
        "icon": "💾",
        "launch_path": r"c:\ROOT\TCPU73\TOTALCMD.EXE"
    },
    {
        "process_name": "Code.exe",
        "display_name": "VS Code",
        "icon": "🔷",
        "launch_path": r"C:\Users\{username}\AppData\Local\Programs\Microsoft VS Code\Code.exe"
    },
    {
        "process_name": "msedge.exe",
        "display_name": "MS Edge",
        "icon": " ",
        "launch_path": r"c:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    },
    {
        "process_name": "Telegram.exe",
        "display_name": "Telegram",
        "icon": " ",
        "launch_path": r"c:\Users\{username}\AppData\Roaming\Telegram Desktop\Telegram.exe"
    },
    {
        "process_name": "max.exe",
        "display_name": "Max",
        "icon": " ",
        "launch_path": r"c:\Program Files\MAX\max.exe"
    },
    {
        "process_name": "thunderbird.exe",
        "display_name": "Thunderbird",
        "icon": " ",
        "launch_path": r"c:\Program Files\Mozilla Thunderbird\thunderbird.exe"
    },
]

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
