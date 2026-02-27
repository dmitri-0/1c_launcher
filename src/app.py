import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gui.tree_window import TreeWindow
from gui.theme import ThemeManager

def get_icon_path():
    """Получить путь к иконке приложения (dev + PyInstaller)."""
    if getattr(sys, 'frozen', False):
        # В сборке PyInstaller иконку нужно добавить через --add-data
        base_path = sys._MEIPASS
        return os.path.join(base_path, 'resources', 'app_icon.ico')
    else:
        # Запуск из исходников: src/resources/app_icon.ico
        base_path = os.path.dirname(os.path.abspath(__file__))
        # __file__ сейчас где-то внутри src (например src/main.py)
        return os.path.abspath(os.path.join(base_path, 'resources', 'app_icon.ico'))
    
def main():
    app = QApplication(sys.argv)
    
    # Установка иконки приложения
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Применение темной темы по умолчанию
    ThemeManager.apply_theme(app, dark=True)
    
    window = TreeWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()