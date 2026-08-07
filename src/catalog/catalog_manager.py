"""Менеджер каталога файлов: сканирование, чтение текста, маска расширений."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


@dataclass
class CatalogFile:
    """Элемент каталога: папка или файл."""
    path: Path
    name: str
    is_dir: bool


def parse_mask(mask: str) -> Set[str]:
    """'.md,.json' → {'.md', '.json'}; пусто → пустой набор (все файлы)."""
    return {part.strip().lower() for part in mask.split(",") if part.strip()}


class CatalogManager:
    """Сканирует корневую папку и читает файлы как текст."""

    def __init__(self, root: str = "", mask: str = ""):
        self._root_str = root or ""               # важно: Path("") == Path(".")
        self.root = Path(root) if root else Path()
        self.mask = parse_mask(mask)

    def is_configured(self) -> bool:
        return bool(self._root_str) and self.root.is_dir()

    def scan(self) -> List[CatalogFile]:
        """Все папки и файлы (маска применяется только к файлам), отсортированы."""
        if not self.is_configured():
            return []
        result = []
        try:
            entries = list(self.root.rglob("*"))
        except OSError:
            return []
        for entry in sorted(entries, key=lambda p: (0 if p.is_dir() else 1, str(p).lower())):
            try:
                if entry.is_dir():
                    result.append(CatalogFile(entry, entry.name, True))
                elif entry.is_file():
                    if self.mask and entry.suffix.lower() not in self.mask:
                        continue
                    result.append(CatalogFile(entry, entry.name, False))
            except OSError:
                continue
        return result

    def read_text(self, path) -> Optional[str]:
        """Текст файла (utf-8, затем cp1251) или None, если файл бинарный/нечитаем."""
        result = self.read_text_with_encoding(path)
        return result[0] if result else None

    def read_text_with_encoding(self, path) -> Optional[tuple]:
        """(текст, кодировка) для текстовых файлов; None — бинарный/нечитаем.

        Кодировка возвращается, чтобы при сохранении файл не перекодировался
        (cp1251-модули 1С должны оставаться cp1251).
        """
        try:
            data = Path(path).read_bytes()
        except OSError:
            return None
        # NUL-байты — почти наверняка бинарный файл (картинка, pdf, dll…)
        if b"\x00" in data:
            return None
        for enc in ("utf-8", "cp1251"):
            try:
                return data.decode(enc), enc
            except UnicodeDecodeError:
                continue
        return None

    def write_text(self, path, text: str, encoding: str = "utf-8") -> None:
        """Записать текст в файл в указанной кодировке (по умолчанию utf-8)."""
        Path(path).write_text(text, encoding=encoding)
