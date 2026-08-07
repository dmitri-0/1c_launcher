"""Движок изображений: preview картинки (путь — в text).

Картинка встраивается в документ как ресурс; если ширина больше виджета —
масштабируется по ширине. Редактирование недоступно (supports_editing=False),
открытие — внешним приложением (F4).
"""

from PySide6.QtGui import QTextDocument, QPixmap
from PySide6.QtCore import Qt, QUrl

from .base import PreviewEngine


class ImageEngine(PreviewEngine):
    name = "image"

    def render(self, widget, text: str, name: str) -> None:
        pixmap = QPixmap(text)  # text = путь к файлу
        if pixmap.isNull():
            widget.setPlainText(f"[Не удалось загрузить изображение: {name}]")
            return
        viewport_w = widget.viewport().width() - 8 if widget.viewport() else 0
        if viewport_w > 0 and pixmap.width() > viewport_w:
            pixmap = pixmap.scaledToWidth(viewport_w, Qt.TransformationMode.SmoothTransformation)
        url = QUrl("catalog-image://embedded")
        widget.document().addResource(QTextDocument.ImageResource, url, pixmap)
        widget.setHtml(f'<img src="{url.toString()}">')

    def supports_editing(self) -> bool:
        return False
