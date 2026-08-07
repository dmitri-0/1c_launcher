"""Движок Markdown: preview рендерится QTextEdit::setMarkdown."""

from .base import PreviewEngine


class MarkdownEngine(PreviewEngine):
    name = "md"

    # Маркеры для эвристики (на случай, если имя без расширения .md)
    MARKERS = ("# ", "## ", "### ", "- ", "* ", "> ", "```", "**", "`", "- [", "1. ", "| ", "![")

    def render(self, widget, text: str, name: str) -> None:
        widget.setMarkdown(text)
