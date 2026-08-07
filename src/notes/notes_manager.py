"""Хранилище заметок лаунчера (SQLite, stdlib sqlite3).

Модель дерева — как у FlashNote: таблица notes со смежным списком (pid),
папка = узел с type=1, заметка = узел с type=0 (дети допускаются у обоих,
но в UI папки — те, у кого type=1).

Тело заметки — plain text. Формат для preview определяется функцией
guess_note_format: пока понимаем только Markdown, остальное — plain text.
"""

import os
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
    """По умолчанию notes.db в %APPDATA%\\1c_launcher — вне каталога исходников.

    Одинаков для скриптовой и exe-версии; переопределяется в launcher.toml
    ([notes] path). Раньше (src/) данные могли попасть в git и терялись
    при пересборке.
    """
    base = os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "1c_launcher" / "notes.db"


def _legacy_db_candidates() -> List[Path]:
    """Старые места notes.db (до переезда в %APPDATA%): рядом с пакетом notes
    (скриптовая версия) и рядом с exe (старые сборки)."""
    candidates = [Path(__file__).parent / "notes.db"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "notes.db")
    return [c for c in candidates if c.is_file() and c.stat().st_size > 0]


def migrate_legacy_db(target: Path) -> bool:
    """Один раз перенести данные из старой notes.db в новый путь (%APPDATA%).

    Условия: db_path не задан явно (это дефолт); legacy-БД найдена; в target
    ещё НЕТ заметок (пустая/отсутствующая — например созданная смоук-прогоном),
    а в legacy они есть. Источник НЕ удаляется (копия-бэкап).
    """
    source = next(iter(_legacy_db_candidates()), None)
    if source is None:
        return False
    try:
        with sqlite3.connect(str(source)) as conn:
            legacy_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    except sqlite3.Error:
        return False
    if legacy_count == 0:
        return False
    if target.exists():
        if target.stat().st_size == 0:
            pass  # пустой файл — заменяем
        else:
            try:
                with sqlite3.connect(str(target)) as conn:
                    target_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            except sqlite3.Error:
                return False
            if target_count > 0:
                return False  # в target уже есть заметки — не трогаем
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(str(source), str(target))
        return True
    except OSError:
        return False  # не блокируем запуск, если копия не вышла


def guess_note_format(name: str, text: str) -> str:
    """Определяет формат заметки для preview (устаревшая обёртка).

    Логика вынесена в notes.engines.detect_engine — здесь оставлена для
    совместимости API/тестов.
    """
    from notes.engines import detect_engine
    return detect_engine(name, text)


class NotesManager:
    """SQLite-хранилище заметок: CRUD, дерево, корзина."""

    def __init__(self, db_path: Optional[Path] = None):
        explicit = bool(db_path or NOTES_PATH)
        path = Path(db_path) if db_path else (Path(NOTES_PATH) if NOTES_PATH else _default_db_path())
        # Путь может указывать на КАТАЛОГ (например "...\1c_launcher\") —
        # тогда берём notes.db внутри него (частый случай: пользователь
        # указывает «куда положить БД», а не сам файл).
        if path.is_dir():
            path = path / "notes.db"
        if not explicit:
            # дефолтный путь: один раз переносим данные старой БД (если была)
            migrate_legacy_db(path)
        self.db_path = path
        self.init_error = None  # если явный путь не открылся — причина (заметки не отключаем)
        self._lock = threading.Lock()
        self._conn = None
        try:
            self._open(path)
        except Exception as e:
            # Битый/занятый файл по ЯВНОМУ пути: не отключаем заметки целиком —
            # откатываемся на дефолтный путь (данные в нём появятся заново).
            if path != _default_db_path():
                try:
                    migrate_legacy_db(_default_db_path())  # перенести старые данные
                    self._open(_default_db_path())
                    self.init_error = (
                        f"не удалось открыть {path} ({e}); используется "
                        f"{_default_db_path()}"
                    )
                    return
                except Exception:
                    pass  # и дефолтный не открылся — ниже пробрасываем исходную ошибку
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            raise

    def _open(self, path: Path):
        """Открыть БД и привести схему к актуальной (timeout против блокировок)."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        path.parent.mkdir(parents=True, exist_ok=True)
        # timeout=15 — второй экземпляр лаунчера ждёт лок до 15 с, а не
        # падает «database is locked» (заметки «отключались» при запуске
        # двух копий/остаточного процесса).
        self._conn = sqlite3.connect(str(path), timeout=15.0)
        self._conn.row_factory = sqlite3.Row
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
            # Вложенные картинки заметок хранятся в БД (blob), а не файлами:
            # портативно, работает и в exe-сборке, placeholder рендерится в preview.
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS images(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL DEFAULT 0,
                    name TEXT NOT NULL DEFAULT '',
                    data BLOB NOT NULL,
                    created TEXT NOT NULL DEFAULT ''
                )"""
            )
            self._conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
            self._conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '3')")
            self._conn.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")

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
        """Полное удаление узла и всех его потомков (вместе с их картинками)."""
        ids = self._collect_subtree(note_id)
        with self._lock, self._conn:
            self._conn.executemany("DELETE FROM notes WHERE id = ?", [(i,) for i in ids])
            # не оставлять осиротевшие blob-картинки удалённых заметок
            self._conn.executemany("DELETE FROM images WHERE note_id = ?", [(i,) for i in ids])
            # и их скролл-позиции (caret у заметок — колонка, чистить нечего)
            self._conn.executemany(
                "DELETE FROM meta WHERE key = ?", [(f"scroll:{i}",) for i in ids])

    def _collect_subtree(self, note_id: int) -> List[int]:
        with self._lock:
            children = [row["id"] for row in self._conn.execute(
                "SELECT id FROM notes WHERE pid = ?", (note_id,))]
        result = [note_id]
        for child_id in children:
            result.extend(self._collect_subtree(child_id))
        return result

    # ── вложенные картинки (blob в БД) ───────────────────────────────
    def add_image(self, note_id: int, name: str, data: bytes) -> int:
        """Сохранить картинку в БД; вернуть id для placeholder `![name](noteimg:<id>)`."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO images(note_id, name, data, created) VALUES(?, ?, ?, ?)",
                (note_id, name, data, _now()),
            )
            return int(cur.lastrowid)

    def get_image(self, image_id: int) -> Optional[bytes]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM images WHERE id = ?", (image_id,)).fetchone()
        return bytes(row["data"]) if row else None

    # ── позиция курсора для произвольных путей (файлы каталога) ─────
    def get_path_caret(self, path: str) -> int:
        """Сохранённая позиция курсора для пути (файл каталога) или 0."""
        key = f"caret:{path}"
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        try:
            return int(row["value"]) if row else 0
        except (TypeError, ValueError):
            return 0

    def set_path_caret(self, path: str, pos: int) -> None:
        """Запомнить позицию курсора для пути (файл каталога)."""
        if pos <= 0:
            return
        key = f"caret:{path}"
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(int(pos))),
            )

    # ── позиция скролла (заметка / файл каталога) ───────────────────
    def _get_meta_int(self, key: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        try:
            return int(row["value"]) if row else 0
        except (TypeError, ValueError):
            return 0

    def _set_meta_int(self, key: str, pos: int) -> None:
        if pos <= 0:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(int(pos))),
            )

    def get_note_scroll(self, note_id: int) -> int:
        """Сохранённая позиция вертикального скролла заметки (px) или 0."""
        return self._get_meta_int(f"scroll:{note_id}")

    def set_note_scroll(self, note_id: int, pos: int) -> None:
        self._set_meta_int(f"scroll:{note_id}", pos)

    def get_path_scroll(self, path: str) -> int:
        """Сохранённая позиция скролла файла каталога (px) или 0."""
        return self._get_meta_int(f"scroll_path:{path}")

    def set_path_scroll(self, path: str, pos: int) -> None:
        self._set_meta_int(f"scroll_path:{path}", pos)

    def close(self):
        with self._lock:
            self._conn.close()
