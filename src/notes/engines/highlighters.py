"""Подсветка синтаксиса для движков (палитра под тёмную тему).

BSL — ключевые слова 1С (список — из config), директивы (&НаКлиенте),
комментарии //, строки, числа. JSON — ключи, строки, числа, true/false/null.
XML — теги, атрибуты, значения, комментарии.
"""

import re

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

try:
    from config import BSL_KEYWORDS
except ImportError:  # pragma: no cover — standalone (вне лаунчера)
    BSL_KEYWORDS = [
        "Процедура КонецПроцедуры Функция КонецФункции Если ИначеЕсли Иначе КонецЕсли "
        "Тогда Для Каждого По Цикл КонецЦикла Пока Возврат Новый Перем Экспорт И Или Не "
        "Истина Ложь Неопределено Попытка Исключение КонецПопытки Перейти Продолжить "
        "Прервать Выполнить ВызватьИсключение ИначеИначе"
    ].split()


def _fmt(color: str, bold: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    return f


class BslHighlighter(QSyntaxHighlighter):
    """Подсветка BSL (1С) — тёмная тема.

    Ключевые слова берутся из config ([highlighting] bsl_keywords) — правка
    без пересборки; если config недоступен — встроенный набор.
    """

    KEYWORDS = tuple(BSL_KEYWORDS)

    def __init__(self, document):
        super().__init__(document)
        self._keyword_fmt = _fmt("#FFC66D", bold=True)   # оранжевый
        self._comment_fmt = _fmt("#6A8759")              # зелёный
        self._string_fmt = _fmt("#A5C261")               # жёлто-зелёный
        self._number_fmt = _fmt("#6897BB")               # синий
        self._directive_fmt = _fmt("#C586C0")            # фиолетовый (&НаКлиенте)
        self._method_fmt = _fmt("#87CEEB")               # вызовы методов

    def highlightBlock(self, text: str):
        # строки "..."
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '"':
                j = text.find('"', i + 1)
                if j == -1:
                    self.setFormat(i, len(text) - i, self._string_fmt)
                    return
                self.setFormat(i, j - i + 1, self._string_fmt)
                i = j + 1
                continue
            if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
                self.setFormat(i, len(text) - i, self._comment_fmt)
                return
            if ch == "&":
                # директива компиляции: &НаКлиенте (поиск слова НАЧИНАЯ со следующего символа)
                j = i + 1
                while j < len(text) and (text[j].isalpha() or text[j] == "_"):
                    j += 1
                self.setFormat(i, j - i, self._directive_fmt)
                i = j
                continue
            if ch.isdigit():
                j = i
                while j < len(text) and (text[j].isdigit() or text[j] in ".,%"):
                    j += 1
                self.setFormat(i, j - i, self._number_fmt)
                i = j
                continue
            if ch.isalpha() or ch == "_":
                j = i
                while j < len(text) and (text[j].isalpha() or text[j].isdigit() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                if word in self.KEYWORDS:
                    self.setFormat(i, j - i, self._keyword_fmt)
                else:
                    # вызов метода: слово, за которым идёт '('
                    k = j
                    while k < len(text) and text[k].isspace():
                        k += 1
                    if k < len(text) and text[k] == "(":
                        self.setFormat(i, j - i, self._method_fmt)
                i = j
                continue
            i += 1


class JsonHighlighter(QSyntaxHighlighter):
    """Подсветка JSON — тёмная тема."""

    def __init__(self, document):
        super().__init__(document)
        self._key_fmt = _fmt("#9CDCFE")       # ключи
        self._string_fmt = _fmt("#CE9178")    # строки
        self._number_fmt = _fmt("#B5CEA8")    # числа
        self._const_fmt = _fmt("#569CD6", bold=True)  # true/false/null

    def highlightBlock(self, text: str):
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '"':
                j = text.find('"', i + 1)
                if j == -1:
                    self.setFormat(i, len(text) - i, self._string_fmt)
                    return
                # ключ, если за строкой идёт ':'
                k = j + 1
                while k < len(text) and text[k].isspace():
                    k += 1
                fmt = self._key_fmt if k < len(text) and text[k] == ":" else self._string_fmt
                self.setFormat(i, j - i + 1, fmt)
                i = j + 1
                continue
            if ch == "-" or ch.isdigit():
                j = i
                while j < len(text) and (text[j].isdigit() or text[j] in "-+.eE"):
                    j += 1
                self.setFormat(i, j - i, self._number_fmt)
                i = j
                continue
            if ch.isalpha():
                j = i
                while j < len(text) and (text[j].isalpha()):
                    j += 1
                word = text[i:j]
                if word in ("true", "false", "null"):
                    self.setFormat(i, j - i, self._const_fmt)
                i = j
                continue
            i += 1


class XmlHighlighter(QSyntaxHighlighter):
    """Подсветка XML — тёмная тема (теги, атрибуты, значения, комментарии)."""

    _TAG_RE = re.compile(r"</?[^>]*>")
    _ATTR_RE = re.compile(r"""([\w:.-]+)\s*=\s*("[^"]*"|'[^']*')""")
    _COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

    def __init__(self, document):
        super().__init__(document)
        self._tag_fmt = _fmt("#569CD6")       # <tag>
        self._attr_fmt = _fmt("#9CDCFE")      # имя атрибута
        self._value_fmt = _fmt("#CE9178")     # значение "..."
        self._comment_fmt = _fmt("#6A8759")   # <!-- ... -->
        self._text_fmt = _fmt("#D4D4D4")      # текст между тегами

    def highlightBlock(self, text: str):
        for m in self._TAG_RE.finditer(text):
            start, end = m.span()
            self.setFormat(start, end - start, self._tag_fmt)
            for am in self._ATTR_RE.finditer(text, start, end):
                self.setFormat(am.start(1), len(am.group(1)), self._attr_fmt)
                self.setFormat(am.start(2), len(am.group(2)), self._value_fmt)
        # комментарии — поверх тегов (иначе подсветятся как теги)
        for m in self._COMMENT_RE.finditer(text):
            start, end = m.span()
            self.setFormat(start, end - start, self._comment_fmt)
