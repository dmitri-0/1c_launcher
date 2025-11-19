import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    """Запуск GUI приложения"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
