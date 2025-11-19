import sys
from PySide6.QtWidgets import QApplication
from gui.main_tree_window import TreeWindow

def main():
    app = QApplication(sys.argv)
    window = TreeWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
