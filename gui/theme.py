from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

class ThemeManager:
    _is_dark = False

    @classmethod
    def is_dark(cls):
        return cls._is_dark

    @classmethod
    def toggle_theme(cls, app):
        cls.apply_theme(app, not cls._is_dark)

    @classmethod
    def apply_theme(cls, app, dark=True):
        cls._is_dark = dark
        app.setStyle("Fusion")
        
        if dark:
            # Создание темной палитры
            dark_palette = QPalette()
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
                QHeaderView::section {
                    background-color: #353535;
                    color: white;
                    border: 1px solid #2a2a2a;
                }
            """)
        else:
            # Светлая тема (сброс к стандартной палитре Fusion)
            app.setPalette(QPalette())
            app.setStyleSheet("")

    @classmethod
    def get_help_css(cls):
        if cls._is_dark:
            return """
            <style>
                table { width: 100%; border-collapse: collapse; color: #ffffff; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #444; }
                th { background-color: #2a2a2a; font-weight: bold; color: #ffffff; }
                tr:hover { background-color: #3a3a3a; }
                .key { font-weight: bold; color: #4fa5e8; }
                .section { background-color: #333333; font-weight: bold; padding: 8px; color: #ffffff; }
                h2, h3, p { color: #ffffff; }
            </style>
            """
        else:
            return """
            <style>
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; font-weight: bold; }
                tr:hover { background-color: #f5f5f5; }
                .key { font-weight: bold; color: #0066cc; }
                .section { background-color: #e8f4f8; font-weight: bold; padding: 8px; }
            </style>
            """
