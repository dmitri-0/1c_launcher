import sys
from PySide6.QtWidgets import QApplication
from gui.tree_window import TreeWindow
from gui.theme import ThemeManager

def main():
    app = QApplication(sys.argv)
    
    # Применение темной темы по умолчанию
    ThemeManager.apply_theme(app, dark=True)
    
    window = TreeWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
