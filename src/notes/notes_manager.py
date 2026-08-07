"""Хранилище заметок лаунчера (SQLite, stdlib sqlite3).

Модель дерева — как у FlashNote: таблица notes со смежным списком (pid),
папка = узел с type=1, заметка = узел с type=0 (дети допускаются у обоих,
но в UI папки — те, у кого type=1).

Тело заметки — plain text. Формат для preview определяется функцией
guess_note_format: пока понимаем только Markdown, остальное — plain text.
"""

import sqlite3
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from config import NOTES_PATH
except ImportError:  # pragma: no cover
    NOTES_PATH = ""


@dataclass
class Note:
    """Одна запись дерева заметок."""
    id: int
    pid: int
    name: str
    note: str
    pos: int
    created: str
    modified: str
    trash: int
    type: int   # 0 = заметка, 1 = папка
    caret: int = 0  # позиция курсора (восстанавливается при входе в редактирование)

    @property
    def is_folder(self) -> bool:
        return self.type == 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _default_db_path() -> Path:
    """По умолчанию notes.db рядом с exe (сборка) / рядом с модулем (исходники)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "notes.db"
    return Path(__file__).resolve().parent / "notes.db"


# Маркеры Markdown для эвристики (на случай, если имя без расширения .md)
_MD_MARKERS = ("# ", "## ", "### ", "- ", "* ", "> ", "```", "**", "`", "- [", "1. ", "| ")


def guess_note_format(name: str, text: str) -> str:
    """Определяет формат заметки для preview.

    Пока движок понимает только Markdown; если формат не распознан —
    заметка показывается как plain text (в будущем добавим другие форматы).
    """
    if name.lower().endswith(".md") or name.lower().endswith(".markdown"):
        return "md"
    for line in text[:4000].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(marker) for marker in _MD_MARKERS):
            return "md"
        break  # проверяем только первую непустую строку
    return "plain"


class NotesManager:
    """SQLite-хранилище заметок: CRUD, дерево, корзина."""

    def __init__(self, db_path: Optional[Path] = None):
        path = Path(db_path) if db_path else (Path(NOTES_PATH) if NOTES_PATH else _default_db_path())
        self.db_path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self):
        with self._lock, self._conn:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS notes(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pid INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    pos INTEGER NOT NULL DEFAULT 0,
                    created TEXT NOT NULL DEFAULT '',
                    modified TEXT NOT NULL DEFAULT '',
                    trash INTEGER NOT NULL DEFAULT 0,
                    type INTEGER NOT NULL DEFAULT 0,
                    caret INTEGER NOT NULL DEFAULT 0
                )"""
            )
            # Миграция: старые БД без колонки caret (позиция курсора)
            cols = [row[1] for row in self._conn.execute("PRAGMA table_info(notes)").fetchall()]
            if "caret" not in cols:
                self._conn.execute("ALTER TABLE notes ADD COLUMN caret INTEGER NOT NULL DEFAULT 0")
            self._conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
            self._conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '2')")
            self._conn.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")

    # ── чтение ──────────────────────────────────────────────────────
    def load_all(self, include_trash: bool = False) -> List[Note]:
        """Все заметки (по умолчанию — без корзины), отсортированы по (pos, name)."""
        sql = "SELECT * FROM notes"
        if not include_trash:
            sql += " WHERE trash = 0"
        sql += " ORDER BY pos, name"
        with self._lock:
            rows = self._conn.execute(sql).fetchall()
        return [Note(**dict(row)) for row in rows]

    def get(self, note_id: int) -> Optional[Note]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return Note(**dict(row)) if row else None

    # ── запись ──────────────────────────────────────────────────────
    def create(self, name: str, note: str = "", pid: int = 0, type_: int = 0) -> int:
        now = _now()
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO notes(pid, name, note, pos, created, modified, trash, type, caret) "
                "VALUES(?, ?, ?, 0, ?, ?, 0, ?, 0)",
                (pid, name, note, now, now, type_),
            )
            return int(cur.lastrowid)

    def update(self, note_id: int, name: Optional[str] = None, note: Optional[str] = None,
               caret: Optional[int] = None) -> None:
        sets, params = [], []
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if note is not None:
            sets.append("note = ?")
            params.append(note)
        if caret is not None:
            sets.append("caret = ?")
            params.append(caret)
        if not sets:
            return
        sets.append("modified = ?")
        params.append(_now())
        params.append(note_id)
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", params)

    def delete_to_trash(self, note_id: int) -> None:
        """Переместить узел и ВСЕХ его потомков в корзину (trash = 1).

        Каскад нужен, чтобы дети осиротевшей папки не «пропадали» из дерева
        навсегда с trash=0.
        """
        ids = self._collect_subtree(note_id)
        with self._lock, self._conn:
            self._conn.executemany(
                "UPDATE notes SET trash = 1, modified = ? WHERE id = ?",
                [(_now(), i) for i in ids],
            )

    def restore(self, note_id: int) -> None:
        ids = self._collect_subtree(note_id)
        with self._lock, self._conn:
            self._conn.executemany(
                "UPDATE notes SET trash = 0, modified = ? WHERE id = ?",
                [(_now(), i) for i in ids],
            )

    def purge(self, note_id: int) -> None:
        """Полное удаление узла и всех его потомков."""
        ids = self._collect_subtree(note_id)
        with self._lock, self._conn:
            self._conn.executemany("DELETE FROM notes WHERE id = ?", [(i,) for i in ids])

    def _collect_subtree(self, note_id: int) -> List[int]:
        with self._lock:
            children = [row["id"] for row in self._conn.execute(
                "SELECT id FROM notes WHERE pid = ?", (note_id,))]
        result = [note_id]
        for child_id in children:
            result.extend(self._collect_subtree(child_id))
        return result

    def close(self):
        with self._lock:
            self._conn.close()
