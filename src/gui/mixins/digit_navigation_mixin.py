from PySide6.QtCore import QTimer, QModelIndex
from PySide6.QtGui import QKeySequence, QShortcut

class DigitNavigationMixin:
    DIGIT_NAV_TIMEOUT_MS = 300

    def setup_digit_navigation(self):
        self._digit_seq = []
        self._digit_timer = QTimer(self)
        self._digit_timer.setSingleShot(True)
        self._digit_timer.timeout.connect(self._execute_digit_sequence)

        for d in range(10):
            sc = QShortcut(QKeySequence(str(d)), self)
            sc.activated.connect(lambda d=d: self._on_digit_pressed(d))

    def _on_digit_pressed(self, d: int):
        self._digit_seq.append(d)
        # Перезапускаем таймер на каждое нажатие (продлеваем время)
        self._digit_timer.start(self.DIGIT_NAV_TIMEOUT_MS)

    def _execute_digit_sequence(self):
        seq = self._digit_seq
        self._digit_seq = []
        if not seq:
            return

        parent = QModelIndex()  # Всегда идем от корня
        for i, d in enumerate(seq):
            pos = 9 if d == 0 else (d - 1)

            rows = self.model.rowCount(parent)
            if pos < 0 or pos >= rows:
                self.statusBar.showMessage("Нет такого пункта в текущем уровне", 2000)
                return

            idx = self.model.index(pos, 0, parent)
            self.tree.setCurrentIndex(idx)
            self.tree.scrollTo(idx)

            # Сворачиваем остальные узлы на этом уровне
            for r in range(rows):
                sib = self.model.index(r, 0, parent)
                if sib != idx:
                    self.tree.collapse(sib)

            has_children = self.model.hasChildren(idx)

            # Если дошли до листа до окончания последовательности — выполняем Enter
            if not has_children and i < len(seq) - 1:
                self.handle_enter()
                return

            # Если мы не на последнем шаге — раскрываем узел и спускаемся в него
            if i < len(seq) - 1:
                if has_children:
                    self.tree.expand(idx)
                    parent = idx
            # Если это последний шаг: если узел — раскрываем, если лист — выполняем Enter
            else:
                if has_children:
                    self.tree.expand(idx)
                else:
                    self.handle_enter()
