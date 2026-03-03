from PySide6.QtWidgets import QStyledItemDelegate

class NumberPrefixDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.column() != 0:
            return

        n = index.row() + 1
        if 1 <= n <= 10:
            key = 0 if n == 10 else n
            option.text = f"{key}. {option.text}"
