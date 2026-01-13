import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gui.tree_window import TreeWindow
from gui.theme import ThemeManager

def get_icon_path():
    """Получить путь к иконке приложения.
    
    Работает как в режиме разработки, так и после сборки PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Запуск из собранного exe (PyInstaller)
        base_path = sys._MEIPASS
    else:
        # Запуск из исходников
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, 'app_icon.ico')

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