"""Диалог справки по горячим клавишам"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

class HelpDialog(QDialog):
    """Диалог помощи по горячим клавишам"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справка по горячим клавишам")
        self.setMinimumWidth(800)
        self.setMinimumHeight(650)
        
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setFrameShape(QTextEdit.NoFrame)
        
        # --- Определение цветовой схемы ---
        # Проверяем яркость фона окна, чтобы понять, темная тема или светлая
        window_color = self.palette().color(QPalette.Window)
        is_dark = window_color.lightness() < 128
        
        if is_dark:
            # Цвета для ТЁМНОЙ темы
            c_text_header = "#FF9900"    # Оранжевый заголовок
            c_text_sub = "#5dade2"       # Светло-синий подзаголовок
            c_th_bg = "#2c3e50"          # Темный фон шапки
            c_th_text = "#ecf0f1"        # Светлый текст шапки
            c_border = "#566573"         # Серые границы
            c_key_bg = "#424949"         # Темно-серые клавиши
            c_key_text = "#ecf0f1"       # Светлый текст на клавишах
            c_key_border = "#7f8c8d"
            c_cmd = "#58d68d"            # Зеленые команды
            c_note_bg = "#2e2e2e"        # Темный фон заметки
            c_note_border = "#d35400"    # Оранжевая граница заметки
            c_note_text = "#dcdcdc"      # Светло-серый текст заметки
        else:
            # Цвета для СВЕТЛОЙ темы
            c_text_header = "#FF9900"
            c_text_sub = "#2980b9"
            c_th_bg = "#34495e"
            c_th_text = "#ffffff"
            c_border = "#bdc3c7"
            c_key_bg = "#f7f9f9"
            c_key_text = "#c0392b"
            c_key_border = "#95a5a6"
            c_cmd = "#16a085"
            c_note_bg = "#fff9c4"
            c_note_border = "#f1c40f"
            c_note_text = "#2c3e50"

        # CSS Стили
        css = f"""
        <style>
            h2 {{ color: {c_text_header}; font-family: Segoe UI, sans-serif; margin-bottom: 5px; }}
            h3 {{ color: {c_text_sub}; font-size: 14pt; margin-top: 20px; text-decoration: underline; }}
            p {{ font-family: Segoe UI, sans-serif; }}
            
            /* Таблица */
            th {{
                background-color: {c_th_bg};
                color: {c_th_text};
                padding: 6px;
                font-weight: bold;
            }}
            td {{
                padding: 5px;
                border-bottom: 1px solid {c_border};
            }}
            
            /* Клавиши */
            .key {{
                background-color: {c_key_bg};
                border: 1px solid {c_key_border};
                border-radius: 4px;
                color: {c_key_text};
                font-weight: bold;
                font-family: Consolas, monospace;
                padding: 2px 5px;
                white-space: nowrap;
                font-size: 10pt;
            }}
            
            /* Команды и пути */
            .cmd {{ color: {c_cmd}; font-weight: bold; font-family: Consolas, monospace; }}
            
            /* Блок заметки */
            .note {{
                background-color: {c_note_bg};
                color: {c_note_text};
                padding: 10px;
                border-left: 5px solid {c_note_border};
            }}
        </style>
        """

        # HTML Контент
        # ВАЖНО: width="100%" в теге table обязателен для Qt RichText
        content = r"""
        <div style="padding: 10px;">
            <h2 align="center">🎹 Горячие клавиши</h2>
            <hr>

            <h3>🚀 Основные действия</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">F1</span></td>
                    <td>Показать эту справку</td>
                </tr>
                <tr>
                    <td><span class="key">Enter</span></td>
                    <td><b>Предприятие:</b> Открыть базу или активировать процесс</td>
                </tr>
                <tr>
                    <td><span class="key">F3</span></td>
                    <td><b>Отладка:</b> Предприятие + <span class="cmd">/debug -attach</span> (свернуть)</td>
                </tr>
                <tr>
                    <td><span class="key">F4</span></td>
                    <td><b>Конфигуратор:</b> Открыть и свернуть в трей</td>
                </tr>
                <tr>
                    <td><span class="key">F5</span></td>
                    <td><b>Инструменты (ИР):</b> Portable Tools + <span class="cmd">/debug</span></td>
                </tr>
                <tr>
                    <td><span class="key">F6</span></td>
                    <td><b>Консоль сервера:</b> Открыть для версии платформы</td>
                </tr>
            </table>
            
            <h3>🛠️ Конфигурация</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">F7</span></td>
                    <td>Обновить конфигурацию БД <span class="cmd">(/UpdateDBCfg)</span></td>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+F7</span></td>
                    <td>Обновить из хранилища и принять</td>
                </tr>
                <tr>
                    <td><span class="key">F8</span></td>
                    <td>Выгрузить CF файл <span class="cmd">(/DumpCfg)</span></td>
                </tr>
            </table>
            
            <h3>🗄️ Список баз</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">Shift+F10</span></td>
                    <td>Добавить новую базу (авто-папка)</td>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+E</span></td>
                    <td>Редактировать параметры</td>
                </tr>
                 <tr>
                    <td><span class="key">Ctrl+I</span></td>
                    <td>📝 Редактировать <b>ibases.v8i</b> в блокноте</td>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+D</span></td>
                    <td><b>Дублировать:</b> Копия с новым ID и датой</td>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+C</span></td>
                    <td>Копировать строку подключения</td>
                </tr>
                <tr>
                    <td><span class="key">Del</span></td>
                    <td>
                        • <b>Базы:</b> Удалить из списка<br>
                        • <b>Процессы:</b> Закрыть окно 1С
                    </td>
                </tr>
                <tr>
                    <td><span class="key">Shift+Del</span></td>
                    <td>
                        • <b>Базы:</b> 🔥 Очистить КЭШ (Local + Roaming)<br>
                        • <b>Процессы:</b> Принудительно убить процесс
                    </td>
                </tr>
                <tr>
                    <td><span class="key">F10</span></td>
                    <td>🌓 Сменить тему</td>
                </tr>
            </table>
            
            <h3>🖥️ Окно</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">Esc</span></td>
                    <td>Свернуть в трей</td>
                </tr>
                <tr>
                    <td><span class="key">Shift+Esc</span></td>
                    <td>Полный выход</td>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+Shift+Ё</span></td>
                    <td>📢 <b>Global Hotkey:</b> Вызвать из любого места</td>
                </tr>
                <tr>
                    <td><span class="key">F10</span></td>
                    <td>🌓 Переключить тему оформления (Светлая / Тёмная)</td>
                </tr>
            </table>
            
            <br>
            <div class="note">
                <b>💡 Полезно знать:</b><br><br>
                1. <b>Кэш (Shift+Del):</b> Чистит папки <i>AppData\Local\1C\1cv8\</i> и <i>AppData\Roaming\1C\1Cv82\</i><br>
                2. <b>Копия (Ctrl+D):</b> Создает клон записи в списке с уникальным ID. Безопасно для экспериментов.<br>
                3. <b>Процессы:</b> В папке "Открытые базы" клавиша <span class="key">Del</span> работает как завершение задачи.
            </div>
        </div>
        """
        
        help_text.setHtml(css + content)
        layout.addWidget(help_text)
        
        # Кнопка закрытия
        close_btn_layout = QVBoxLayout()
        close_btn_layout.setContentsMargins(10, 0, 10, 10)
        
        close_button = QPushButton("Закрыть")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setMinimumHeight(35)
        # Стили кнопки пусть берутся из основной темы приложения, 
        # чтобы не создавать конфликтов, или можно задать нейтральный стиль
        
        close_button.clicked.connect(self.accept)
        close_btn_layout.addWidget(close_button)
        layout.addLayout(close_btn_layout)
        
        self.setLayout(layout)
