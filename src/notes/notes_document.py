"""QTextDocument для панели заметок: умеет грузить вложенные картинки из notes.db.

Markdown-заметки могут ссылаться на картинку placeholder-ом `![name](noteimg:<id>)`.
Документ перехватывает loadResource и достаёт blob из БД через loader
(callable(image_id:int) -> bytes | None), задаётся из NotesMixin.
"""

from PySide6.QtGui import QTextDocument, QImage
from PySide6.QtCore import QUrl


class NoteTextDocument(QTextDocument):
    """Документ с загрузчиком вложенных картинок из notes.db."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loader = None  # callable(image_id: int) -> bytes | None

    def loadResource(self, type_, url: QUrl):
        if type_ == QTextDocument.ImageResource and self.loader is not None:
            s = url.toString()
            if s.startswith("noteimg:"):
                try:
                    image_id = int(s.split(":", 1)[1])
                except ValueError:
                    image_id = -1
                data = self.loader(image_id) if image_id > 0 else None
                if data:
                    image = QImage()
                    if image.loadFromData(data):
                        return image
        return super().loadResource(type_, url)
