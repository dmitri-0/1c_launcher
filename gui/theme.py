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
            # Цвета в стиле VS Code Dark
            # Основной фон VS Code: #1e1e1e (30, 30, 30)
            # Боковая панель/списки: #252526 (37, 37, 38)
            # Выделение: #04395e или #094771 (используем более яркий #007acc для видимости)
            
            dark_palette = QPalette()
            
            # Общий фон окна
            dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))         # #1e1e1e
            dark_palette.setColor(QPalette.WindowText, QColor(204, 204, 204))  # #cccccc
            
            # Фон для ввода текста, списков (Base)
            dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))           # #1e1e1e (как редактор)
            dark_palette.setColor(QPalette.AlternateBase, QColor(37, 37, 38))  # #252526
            
            dark_palette.setColor(QPalette.ToolTipBase, QColor(37, 37, 38))    # #252526
            dark_palette.setColor(QPalette.ToolTipText, QColor(204, 204, 204)) # #cccccc
            
            dark_palette.setColor(QPalette.Text, QColor(204, 204, 204))        # #cccccc
            dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))         # #2d2d2d
            dark_palette.setColor(QPalette.ButtonText, QColor(204, 204, 204))  # #cccccc
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            
            # Цвет ссылок (VS Code Blue)
            dark_palette.setColor(QPalette.Link, QColor(55, 148, 255))         # #3794ff
            
            # Цвет выделения (VS Code Selection)
            dark_palette.setColor(QPalette.Highlight, QColor(0, 122, 204))     # #007acc
            dark_palette.setColor(QPalette.HighlightedText, Qt.white)
            
            # Disabled цвета
            dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(100, 100, 100))
            dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(100, 100, 100))
            dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(100, 100, 100))
            
            app.setPalette(dark_palette)
            
            # CSS стили с цветами VS Code
            app.setStyleSheet("""
                QToolTip {
                    color: #cccccc;
                    background-color: #252526;
                    border: 1px solid #454545;
                }
                QTreeView {
                    background-color: #1e1e1e; /* Основной фон редактора */
                    color: #cccccc;
                    border: 1px solid #3e3e42;
                }
                QTreeView::item:selected {
                    background-color: #094771; /* Темно-синий фон выделения списка */
                    color: #ffffff;
                }
                QTreeView::item:hover {
                    background-color: #2a2d2e; /* Цвет при наведении */
                }
                QHeaderView::section {
                    background-color: #252526; /* Цвет заголовков */
                    color: #cccccc;
                    border: none;
                    padding: 4px;
                }
                QMainWindow {
                    background-color: #1e1e1e;
                }
                QStatusBar {
                    background-color: #007acc; /* Синий статус бар как в VS Code */
                    color: white;
                }
            """)
        else:
            # Светлая тема (сброс к стандартной палитре Fusion)
            app.setPalette(QPalette())
            app.setStyleSheet("")

    @classmethod
    def get_help_css(cls):
        if cls._is_dark:
            # Цвета для HTML справки в стиле VS Code
            return """
            <style>
                table { width: 100%; border-collapse: collapse; color: #cccccc; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #3e3e42; }
                th { background-color: #252526; font-weight: bold; color: #cccccc; }
                tr:hover { background-color: #2a2d2e; }
                .key { font-weight: bold; color: #3794ff; }
                .section { background-color: #2d2d2d; font-weight: bold; padding: 8px; color: #cccccc; }
                h2, h3, p { color: #cccccc; }
                code { background-color: #2d2d2d; padding: 2px 4px; border-radius: 3px; font-family: monospace; }
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
