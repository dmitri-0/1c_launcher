import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt
from gui.tree_window import TreeWindow

def setup_dark_theme(app):
    """Настройка темной темы Fusion для приложения."""
    app.setStyle("Fusion")
    
    # Создание темной палитры
    dark_palette = QPalette()
    
    # Основные цвета
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    
    # Disabled цвета
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    
    app.setPalette(dark_palette)
    
    # Дополнительные стили через CSS
    app.setStyleSheet("""
        QToolTip {
            color: #ffffff;
            background-color: #2a2a2a;
            border: 1px solid white;
        }
        QTreeView {
            background-color: #191919;
            alternate-background-color: #2a2a2a;
        }
        QTreeView::item:selected {
            background-color: #2a82da;
        }
        QTreeView::item:hover {
            background-color: #3a3a3a;
        }
    """)

def main():
    app = QApplication(sys.argv)
    setup_dark_theme(app)
    window = TreeWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
