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

        # Имя глобальной горячей клавиши — читается динамически из hotkey_manager
        # (значения берутся из src/launcher.toml), чтобы справка всегда показывала
        # реально зарегистрированную комбинацию.
        hotkey_name = "Alt+D"
        parent_window = self.parent()
        if parent_window is not None:
            hm = getattr(parent_window, "hotkey_manager", None)
            if hm is not None and hasattr(hm, "get_hotkey_name"):
                hotkey_name = hm.get_hotkey_name()
        
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
        content = fr"""
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
                    <td><b>Предприятие (чистый запуск):</b> Открыть базу <b>без отладки</b> или активировать процесс</td>
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

            <h3>🌐 Публикация на Apache</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">F9</span></td>
                    <td>📡 Опубликовать базу на Apache (<span class="cmd">webinst.exe</span>). Псевдоним и каталог берутся из настроек базы (<span class="key">Ctrl+E</span> → «Публикация»). Apache и каталог копируются/создаются автоматически, служба поднимается при необходимости</td>
                </tr>
                <tr>
                    <td><span class="key">Shift+F9</span></td>
                    <td>🚫 Отменить публикацию базы</td>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+F2</span></td>
                    <td>🖥 <b>Управление Apache:</b> список экземпляров, запуск/остановка, службы, публикации, справка (<span class="key">F1</span> внутри окна)</td>
                </tr>
            </table>

            <h3>📸 Снапшоты DBM API</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">Ctrl+U</span></td>
                    <td>🔄 <b>Обновить копии:</b> полный список баз из «Мои снапшоты» + кнопка «Обновить копию» (получить новый снапшот через DBM API → connection string → F12). Чекбокс скрывает копии с датой</td>
                </tr>
                <tr>
                    <td><span class="key">F11</span></td>
                    <td>🚀 Запустить DBM API (там же «Мои снапшоты» с голубой подсветкой устаревших)</td>
                </tr>
                <tr>
                    <td><span class="key">F12</span></td>
                    <td>📸 Обновить копию из снапшота (новая строка подключения)</td>
                </tr>
                <tr>
                    <td><i>меню «Редактирование»</i></td>
                    <td>⬇ <b>«Откатить к снапшоту (downgrade)…»</b> — обратное F12: для «&lt;имя&gt; &lt;дата1&gt; &lt;дата2&gt;» переносит строку подключения в «&lt;имя&gt; &lt;дата1&gt;» и удаляет копию. Если база не найдена — сообщает и ничего не делает</td>
                </tr>
                <tr>
                    <td><i>меню «Действия»</i></td>
                    <td><b>«Создать снапшот DBM API…»</b> — мастер: БД → снапшот-мастер → ERP-сервер → описание (создание только через DBM API)</td>
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
                    <td>Редактировать параметры базы (включая поля «Публикация»: имя и каталог)</td>
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
                    <td><i>меню «Действия»</i></td>
                    <td>🗑 <b>«Очистить „Недавние“ от копий с датой…»</b> — убрать из «Недавних» все копии с датой в имени (вместо Del по каждой)</td>
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
            </table>

            <h3>🖥️ Окно</h3>
            <table width="100%" cellspacing="0" cellpadding="4">
                <tr>
                    <th width="25%">Клавиша</th>
                    <th width="75%">Действие</th>
                </tr>
                <tr>
                    <td><span class="key">F10</span></td>
                    <td>🌓 Переключить тему оформления (Светлая / Тёмная)</td>
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
                    <td><span class="key">{hotkey_name}</span></td>
                    <td>📢 <b>Global Hotkey:</b> Вызвать окно из любого места · ⏹️ Отменить затянувшееся ожидание закрытия (после <span class="key">Del</span>)</td>
                </tr>
            </table>

            <br>
            <div class="note">
                <b>💡 Полезно знать:</b><br><br>
                1. <b>Кэш (Shift+Del):</b> Чистит папки <i>AppData\Local\1C\1cv8\</i> и <i>AppData\Roaming\1C\1Cv82\</i><br>
                2. <b>Копия (Ctrl+D):</b> Создает клон записи в списке с уникальным ID. Безопасно для экспериментов.<br>
                3. <b>Процессы:</b> В папке "Открытые базы" клавиша <span class="key">Del</span> работает как завершение задачи.<br>
                4. <b>Публикация (F9):</b> один Apache на версию платформы; разрядность Apache должна совпадать с разрядностью платформы (wsap24.dll). Если для версии нет Apache — он копируется автоматически.<br>
                5. <b>Снапшоты (Ctrl+U):</b> «Обновить копию» создаёт новый снапшот только через DBM API (номер вида <i>…_2</i> присваивается независимо от сервера), ждёт завершения задачи (живой лог, прогресс) и выполняет F12 автоматически.<br>
                6. <b>DBM API:</b> токен запрашивается раз в час; если DBM API не запущен (F11) — интеграция недоступна.
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
