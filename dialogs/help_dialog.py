"""Диалог справки по горячим клавишам"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton
from PySide6.QtCore import Qt


class HelpDialog(QDialog):
    """Диалог помощи по горячим клавишам"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка по горячим клавишам")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
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
            .section { background-color: #e8f4f8; font-weight: bold; padding: 8px; }
        </style>
        
        <h3>Основные действия</h3>
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
                <td><span class="key">Enter</span></td>
                <td>Активировать выбранный процесс 1С или открыть выбранную базу в режиме предприятия</td>
            </tr>
            <tr>
                <td><span class="key">F3</span></td>
                <td>Открыть выбранную базу данных (режим предприятия) с попыткой отладки (/debug -attach) и свернуть окно в трей</td>
            </tr>
            <tr>
                <td><span class="key">F4</span></td>
                <td>Открыть конфигуратор для выбранной базы и свернуть окно в трей</td>
            </tr>
            <tr>
                <td><span class="key">F5</span></td>
                <td>Запустить портативные инструменты разработчика (ИР) для выбранной базы с попыткой отладки (/debug -attach) и свернуть окно в трей</td>
            </tr>
            <tr>
                <td><span class="key">F6</span></td>
                <td>Запустить консоль сервера 1С для выбранной базы и свернуть окно в трей</td>
            </tr>
        </table>
        
        <h3>Работа с конфигурацией</h3>
        <table>
            <tr>
                <th>Клавиша</th>
                <th>Действие</th>
            </tr>
            <tr>
                <td><span class="key">F7</span></td>
                <td>Обновление конфигурации БД (/UpdateDBCfg) для выбранной базы</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+F7</span></td>
                <td>Обновление конфигурации из хранилища и сохранение (/UpdateDBCfg)</td>
            </tr>
            <tr>
                <td><span class="key">F8</span></td>
                <td>Выгрузка CF (/DumpCfg) для выбранной базы</td>
            </tr>
        </table>
        
        <h3>Управление базами</h3>
        <table>
            <tr>
                <th>Клавиша</th>
                <th>Действие</th>
            </tr>
            <tr>
                <td><span class="key">Shift+F10</span></td>
                <td>Добавить новую базу данных (папка заполняется автоматически по позиции курсора)</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+E</span></td>
                <td>Редактировать настройки выбранной базы</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+D</span></td>
                <td>Дублировать выбранную базу (создаёт копию с новым ID и датой в имени)</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+C</span></td>
                <td>Скопировать строку подключения (Connect) в буфер обмена</td>
            </tr>
            <tr>
                <td><span class="key">Del</span></td>
                <td><b>Для баз:</b> Удалить базу из списка (в папке "Недавние" - сброс флага, в других папках - полное удаление)<br>
                    <b>Для процессов:</b> Корректно закрыть выбранный процесс 1С</td>
            </tr>
            <tr>
                <td><span class="key">Shift+Del</span></td>
                <td><b>Для баз:</b> Очистить программный и пользовательский кэш выбранной базы<br>
                    <b>Для процессов:</b> Принудительно завершить выбранный процесс 1С</td>
            </tr>
        </table>
        
        <h3>Управление окном</h3>
        <table>
            <tr>
                <th>Клавиша</th>
                <th>Действие</th>
            </tr>
            <tr>
                <td><span class="key">Esc</span></td>
                <td>Свернуть окно в системный трей (не закрывает приложение)</td>
            </tr>
            <tr>
                <td><span class="key">Shift+Esc</span></td>
                <td>Полный выход из приложения</td>
            </tr>
            <tr>
                <td><span class="key">Ctrl+Shift+Ё</span></td>
                <td><b>Глобальная горячая клавиша:</b> Вызвать окно программы из системного трея (работает даже когда окно свёрнуто или скрыто)</td>
            </tr>
        </table>
        
        <br>
        <h3>Дополнительная информация</h3>
        <p><b>Работа с процессами 1С:</b> В папке "Открытые базы" отображаются запущенные процессы 1С. Для них клавиши <span class="key">Enter</span>, <span class="key">Del</span> и <span class="key">Shift+Del</span> выполняют действия над процессами, а не над базами данных.</p>
        
        <p><b>Копирование базы (Ctrl+D):</b> Создаёт полную копию выбранной базы с новым уникальным ID. К имени исходной базы автоматически добавляется текущая дата для различения копий.</p>
        
        <p><b>Очистка кэша (Shift+Del):</b> Удаляет:<br>
        • Программный кэш из <code>AppData\Local\1C\1cv8\</code><br>
        • Пользовательский кэш из <code>AppData\Roaming\1C\1Cv82\</code></p>
        
        <p><b>Системный трей:</b> Программа работает в фоновом режиме через иконку в системном трее. Используйте <span class="key">Ctrl+Shift+Ё</span> для быстрого вызова окна или дважды щёлкните по иконке в трее.</p>
        """)
        layout.addWidget(help_text)
        
        # Кнопка закрытия
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)
