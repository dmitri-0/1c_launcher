import os
from pathlib import Path

# Путь к файлу со списком баз 1С
IBASES_PATH = Path(os.getenv('USERPROFILE')) / 'AppData' / 'Roaming' / '1C' / '1CEStart' / 'ibases.v8i'

# Кодировка файла ibases.v8i
ENCODING = 'utf-8-sig'

# Путь к обработке инструментов ИР
IR_TOOLS_PATH = r"c:\ROOT\CodeBase\1C\Обработки\ИР_Портативный\ирПортативный.epf"

# Путь для выгрузки CF (папка)
CF_DUMP_PATH = Path(r"D:\CF")

# Путь к лог-файлу операций
LOG_PATH = Path(r"D:\CF\log.txt")

# Пути для запуска DBM API
DBM_PYTHON_EXE = r"c:\ROOT\CodeBase\Py\dbm_api\venv\Scripts\python.exe"
DBM_SCRIPT_PATH = r"c:\ROOT\CodeBase\Py\dbm_api\app.py"
