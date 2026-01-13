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
        
        palette = QPalette()
        
        if dark:
            # === ТЕМНАЯ ТЕМА (VS Code Style) ===
            # Основной фон VS Code: #1e1e1e (30, 30, 30)
            # Боковая панель/списки: #252526 (37, 37, 38)
            
            # Общий фон окна
            palette.setColor(QPalette.Window, QColor(30, 30, 30))         # #1e1e1e
            palette.setColor(QPalette.WindowText, QColor(204, 204, 204))  # #cccccc
            
            # Фон для ввода текста, списков (Base)
            palette.setColor(QPalette.Base, QColor(30, 30, 30))           # #1e1e1e
            palette.setColor(QPalette.AlternateBase, QColor(37, 37, 38))  # #252526
            
            palette.setColor(QPalette.ToolTipBase, QColor(37, 37, 38))    # #252526
            palette.setColor(QPalette.ToolTipText, QColor(204, 204, 204)) # #cccccc
            
            palette.setColor(QPalette.Text, QColor(204, 204, 204))        # #cccccc
            palette.setColor(QPalette.Button, QColor(45, 45, 45))         # #2d2d2d
            palette.setColor(QPalette.ButtonText, QColor(204, 204, 204))  # #cccccc
            palette.setColor(QPalette.BrightText, Qt.red)
            
            # Цвет ссылок (VS Code Blue)
            palette.setColor(QPalette.Link, QColor(55, 148, 255))         # #3794ff
            
            # Цвет выделения (VS Code Selection)
            palette.setColor(QPalette.Highlight, QColor(0, 122, 204))     # #007acc
            palette.setColor(QPalette.HighlightedText, Qt.white)
            
            # Disabled цвета
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor(100, 100, 100))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(100, 100, 100))
            palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(100, 100, 100))
            
            app.setPalette(palette)
            
            # CSS стили с цветами VS Code
            # Статус бар теперь без синей заливки, используется цвет Window
            app.setStyleSheet("""
                QToolTip {
                    color: #cccccc;
                    background-color: #252526;
                    border: 1px solid #454545;
                }
                QTreeView {
                    background-color: #1e1e1e;
                    color: #cccccc;
                    border: 1px solid #3e3e42;
                }
                QTreeView::item:selected {
                    background-color: #094771;
                    color: #ffffff;
                }
                QTreeView::item:hover {
                    background-color: #2a2d2e;
                }
                QHeaderView::section {
                    background-color: #252526;
                    color: #cccccc;
                    border: none;
                    padding: 4px;
                }
                QMainWindow {
                    background-color: #1e1e1e;
                }
                QStatusBar {
                    background-color: #007acc; /* Возвращаем синий только для акцента, если нужно, или убираем совсем */
                    color: white;
                }
                /* Переопределяем статус бар на прозрачный/стандартный фон, чтобы не было "голубой заливки" */
                QStatusBar {
                    background: transparent;
                    color: #cccccc;
                }
            """)
            
        else:
            # === СВЕТЛАЯ ТЕМА ===
            # Явное задание стандартных светлых цветов
            palette.setColor(QPalette.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, Qt.white)
            palette.setColor(QPalette.AlternateBase, QColor(233, 231, 227))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.black)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, Qt.black)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            
            # Disabled цвета
            palette.setColor(QPalette.Disabled, QPalette.Text, QColor(190, 190, 190))
            palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(190, 190, 190))
            palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(190, 190, 190))
            
            app.setPalette(palette)
            
            # Сброс стилей или явная установка светлых стилей
            app.setStyleSheet("""
                QToolTip {
                    color: black;
                    background-color: #f0f0f0;
                    border: 1px solid #767676;
                }
                QTreeView {
                    background-color: white;
                    color: black;
                }
                QTreeView::item:selected {
                    background-color: #3399ff;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: black;
                    border: 1px solid #d0d0d0;
                    padding: 4px;
                }
                QMainWindow {
                    background-color: #f0f0f0;
                }
                QStatusBar {
                    background: transparent;
                    color: black;
                }
            """)

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
                table { width: 100%; border-collapse: collapse; color: black; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; font-weight: bold; color: black; }
                tr:hover { background-color: #f5f5f5; }
                .key { font-weight: bold; color: #0066cc; }
                .section { background-color: #e8f4f8; font-weight: bold; padding: 8px; color: black; }
                h2, h3, p { color: black; }
            </style>
            """
