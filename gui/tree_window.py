# gui/tree_window.py

from PySide6.QtWidgets import (
    QMainWindow, QTreeView, QVBoxLayout, QWidget,
    QStatusBar, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING
from dialogs import HelpDialog, DatabaseSettingsDialog
from collections import defaultdict
import os
from pathlib import Path
import platform
import re
import uuid
from datetime import datetime
import shutil
import tempfile
import sys

# Проверка доступности Windows API для глобальных горячих клавиш
if platform.system() == 'Windows':
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_HOTKEY_AVAILABLE = True
    except ImportError:
        WINDOWS_HOTKEY_AVAILABLE = False
        print("⚠️ Предупреждение: ctypes/wintypes недоступны. Глобальные горячие клавиши будут отключены.")
else:
    WINDOWS_HOTKEY_AVAILABLE = False


class TreeWindow(QMainWindow):
    """
    Главное окно приложения с деревом баз данных 1С.

    Поддерживает глобальную горячую клавишу для быстрого вызова окна программы -
    по умолчанию Ctrl+Shift+` (тильда, буква "Ё", VK_OEM_3).

    Для изменения комбинации горячей клавиши отредактируйте константы:
    HOTKEY_MODIFIERS и HOTKEY_VK:

        HOTKEY_MODIFIERS = 0x0006  # MOD_CONTROL (0x0002) + MOD_SHIFT (0x0004)
        HOTKEY_VK = 0xC0  # VK_OEM_3 (тильда/ё)

        # Модификаторы:
        # MOD_ALT     = 0x0001
        # MOD_CONTROL = 0x0002
        # MOD_SHIFT   = 0x0004
        # MOD_WIN     = 0x0008
        # Можно складывать для комбинаций
    """
    
    HOTKEY_ID = 1
    HOTKEY_MODIFIERS = 0x0006  # MOD_CONTROL (0x0002) + MOD_SHIFT (0x0004)
    HOTKEY_VK = 0xC0  # VK_OEM_3 (клавиша тильды/ё)

    # ... остальной код без изменений ...

