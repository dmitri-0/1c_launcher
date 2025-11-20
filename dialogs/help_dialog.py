# dialogs/help_dialog.py

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton
from PySide6.QtCore import Qt


class HelpDialog(QDialog):
    """Диалог помощи по горячим клавишам"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка по горячим клавишам")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("<h2>Горячие клавиши</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Текстовое поле с подсказками
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <style>
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; font-weight: bold; }
            tr:hover { background-color: #f5f5f5; }
            .key { font-weight: bold; color: #0066cc; }
        </style>
        <table>
            <tr>
                <th>Клавиша</th>
                <th>Действие</th>
            </tr>
            <tr>
                <td><span class="key">F1</span></td>
                <td>Показать это окно справки</td>
            </tr>
            <tr>
                <td><span class="key">F3</span></td>
                <td>Открыть выбранную базу данных (режим предприятия)</td>
            </tr>
            <tr>
                <td><span class="key">F4</span></td>
                <td>Открыть конфигуратор для выбранной базы</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+C</span></td>
                <td>Скопировать строку подключения в буфер обмена</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+D</span></td>
                <td>Копировать выбранную базу (создать дубликат)</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+E</span></td>
                <td>Редактировать настройки выбранной базы</td>
            </tr>
            <tr>
                <td><span class="key">Del</span></td>
                <td>Удалить базу (в Недавних - сброс флага, иначе полное удаление)</td>
            </tr>
            <tr>
                <td><span class="key">Shift+Del</span></td>
                <td>Очистить кэш выбранной базы (программный и пользовательский)</td>
            </tr>
            <tr>
                <td><span class="key">Shift+F10</span></td>
                <td>Добавить новую базу (папка заполняется по курсору)</td>
            </tr>
            <tr>
                <td><span class="key">Esc</span></td>
                <td>Выход из программы</td>
            </tr>
        </table>
        <br>
        <p><b>Примечание:</b> Для работы горячих клавиш (кроме Esc) необходимо выбрать базу данных в дереве, а не папку.</p>
        <p><b>Копирование базы (Ctrl+D):</b> Создаёт копию выбранной базы с новым ID. К имени исходной базы добавляется текущая дата.</p>
        <p><b>Очистка кэша (Shift+Del):</b> Удаляет программный кэш из AppData\Local\1C\1cv8\ и пользовательский кэш из AppData\Roaming\1C\1Cv82\</p>
        """)
        layout.addWidget(help_text)
        
        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)
