import os
from pathlib import Path

# Путь к файлу со списком баз 1С
IBASES_PATH = Path(os.getenv('USERPROFILE')) / 'AppData' / 'Roaming' / '1C' / '1CEStart' / 'ibases.v8i'

# Кодировка файла ibases.v8i
ENCODING = 'utf-8-sig'

# Путь к обработке инструментов ИР
IR_TOOLS_PATH = r"C:\ROOT\7_90.1\wp\Портативный.erf"