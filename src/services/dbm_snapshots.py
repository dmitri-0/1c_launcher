"""Интеграция лаунчера с DBM API: снапшоты и их обновление.

- Токен доступа запрашивается у DBM API раз в час (кэш с TTL 1 час);
  сам запрос выполняет хелпер-подпроцесс на venv DBM API (там расшифровка
  учётных данных через cryptography).
- Логика «голубых» снапшотов — как в «Мои снапшоты» DBM API: если у базы
  данных есть снапшот с БОЛЬШИМ сроком истечения, чем у текущего, значит
  появился более новый снапшот — текущий можно обновить.
- Сопоставление с базами лаунчера: база, чья строка подключения ссылается
  на Ref снапшота (snapshot.name == Ref) и в имени которой НЕТ даты
  «<дата>» (то есть она ещё не обновлялась) — кандидат на обновление.
"""

import re
import subprocess
import time
from datetime import datetime, date
from pathlib import Path
from typing import Callable, Dict, List, Optional

import databases_api  # vendored: src/databases_api.py (см. модуль)

from config import DBM_API_DIR, DBM_PYTHON_EXE

# Токен запрашивается каждый час
TOKEN_TTL_SEC = 3600

_SNAPSHOT_STATES = ("READY", "RETIRED")
_DATE_SUFFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")

_token_cache: Dict[str, Optional[str]] = {"token": None, "fetched_at": 0.0}


def _dbm_api_dir() -> Path:
    return Path(DBM_API_DIR)


# ------------------------------------------------------------------ #
#  Токен (раз в час)                                                  #
# ------------------------------------------------------------------ #

def get_valid_token(max_age_sec: int = TOKEN_TTL_SEC) -> Optional[str]:
    """Возвращает access token DBM API; кэширует на час.

    При истечении часа хелпер запрашивает СВЕЖИЙ токен (password grant),
    при неудаче — возвращает сохранённый валидный.
    """
    global _token_cache
    now = time.time()
    cached = _token_cache.get("token")
    if cached and (now - _token_cache.get("fetched_at", 0)) < max_age_sec:
        return cached

    token = _request_token_via_helper()
    _token_cache = {"token": token, "fetched_at": now}
    return token


def _request_token_via_helper() -> Optional[str]:
    """Запускает get_token_cli.py на venv DBM API и читает токен из stdout."""
    python_exe = Path(DBM_PYTHON_EXE)
    helper = _dbm_api_dir() / "get_token_cli.py"
    if not python_exe.exists() or not helper.exists():
        return None
    try:
        proc = subprocess.run(
            [str(python_exe), str(helper)],
            capture_output=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    return token or None


# ------------------------------------------------------------------ #
#  Снапшоты                                                           #
# ------------------------------------------------------------------ #

def _parse_date(raw) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None


def get_my_snapshots(token: str) -> List[dict]:
    """Снапшоты пользователя (GET /api/v1/snapshots), только READY/RETIRED."""
    if not token:
        return []

    try:
        snapshots = databases_api.get_user_snapshots(token) or []
    except Exception:
        return []
    return [s for s in snapshots if s.get("state") in _SNAPSHOT_STATES]


def get_databases(token: str) -> List[dict]:
    """Список баз данных DBM API (для выбора при создании снапшота)."""
    if not token:
        return []

    try:
        return databases_api.get_databases(token) or []
    except Exception:
        return []


def get_db_snapshots(token: str, db_id) -> List[dict]:
    """Снапшоты конкретной базы данных DBM API."""
    if not token:
        return []

    try:
        return databases_api.get_snapshots(token, db_id) or []
    except Exception:
        return []


def get_erp_servers(token: str) -> List[dict]:
    """Доступные ERP-серверы DBM API (для создания снапшота)."""
    if not token:
        return []

    try:
        return databases_api.get_erp_servers(token) or []
    except Exception:
        return []


def create_snapshot(token: str, master_snapshot_id, erp_server_id, description: str) -> dict:
    """Создаёт снапшот через DBM API (POST /api/v1/snapshots)."""

    return databases_api.create_snapshot(token, master_snapshot_id, erp_server_id, description)


# Состояния задачи создания снапшота (как в DBM API)
TASK_DONE_STATES = {"completed", "succeeded", "success", "finished", "done"}
TASK_FAILED_STATES = {"failed", "error", "canceled", "cancelled", "aborted"}


def get_task_status(token: str, task_id: str):
    """Статус задачи DBM API (GET /api/v1/tasks/{id})."""

    return databases_api.get_task_status(token, task_id)


def task_info_from_status(data) -> dict:
    """Нормализует ответ get_task_status (list/dict) в dict задачи."""
    if isinstance(data, list):
        return data[0] if data else {}
    if isinstance(data, dict):
        return data
    return {}


def find_newer_snapshot_connect(snapshots: List[dict], base_ref: str) -> str:
    """Connection string самого нового снапшота (срок > текущего), очищенный от \\".

    Возвращает "" — если более нового снапшота с connectionString ещё нет.
    """
    cur_exp = next((_parse_date(s.get("expirationDate"))
                    for s in snapshots if s.get("name") == base_ref), None)
    if cur_exp is None:
        return ""
    best = None
    for s in snapshots:
        exp = _parse_date(s.get("expirationDate"))
        if (s.get("name") != base_ref and s.get("connectionString")
                and exp and exp > cur_exp):
            if best is None or exp > _parse_date(best.get("expirationDate")):
                best = s
    if not best:
        return ""
    return (best.get("connectionString") or "").replace('\\"', '"')


def find_updatable_snapshots(
    snapshots: List[dict],
    get_db_snapshots: Callable[[int], List[dict]],
) -> List[dict]:
    """Снапшоты, у которых появился более новый (логика «голубой» строки).

    Args:
        snapshots: снапшоты пользователя (READY/RETIRED).
        get_db_snapshots: функция(db_id) -> все снапшоты базы данных.
    """
    max_exp_by_db: Dict[int, Optional[date]] = {}
    for snap in snapshots:
        db_id = snap.get("databaseId")
        if db_id in max_exp_by_db:
            continue
        try:
            db_snapshots = get_db_snapshots(db_id) or []
        except Exception:
            db_snapshots = []
        exps = [_parse_date(s.get("expirationDate")) for s in db_snapshots]
        exps = [e for e in exps if e is not None]
        max_exp_by_db[db_id] = max(exps) if exps else None

    updatable = []
    for snap in snapshots:
        exp = _parse_date(snap.get("expirationDate"))
        mx = max_exp_by_db.get(snap.get("databaseId"))
        if exp and mx and mx > exp:
            updatable.append(snap)
    return updatable


def build_update_candidates(
    snapshots: List[dict],
    bases,
    get_db_snapshots: Callable[[int], List[dict]],
) -> List[dict]:
    """Строки диалога: ВСЕ базы лаунчера из раздела «Мои снапшоты».

    База попадает в список, если её Ref из Connect совпадает с именем одного
    из снапшотов пользователя. Строка помечается как обновляемая, если:
    - у её БД DBM API есть снапшот с бОльшим сроком истечения («голубой»);
    - в имени базы НЕТ даты «<дата>» (ещё не обновлялась).

    Несколько баз могут ссылаться на один снапшот (например, «ХРАН»-копии
    одного поколения) — каждая получает свою строку.
    """
    updatable_names = {
        s.get("name")
        for s in find_updatable_snapshots(snapshots, get_db_snapshots)
    }

    # имя/строка/истечение самого нового снапшота по каждой БД
    newest_by_db: Dict[int, dict] = {}
    for snap in snapshots:
        db_id = snap.get("databaseId")
        exp = _parse_date(snap.get("expirationDate"))
        current = newest_by_db.get(db_id)
        if exp and (not current or exp > _parse_date(current.get("expirationDate"))):
            newest_by_db[db_id] = snap

    snapshot_by_name = {s.get("name"): s for s in snapshots}

    rows = []
    for base in bases:
        ref = _ref_from_connect(getattr(base, "connect", ""))
        snap = snapshot_by_name.get(ref)
        if not snap:
            continue
        base_name = getattr(base, "name", "") or ""
        newest = newest_by_db.get(snap.get("databaseId"))
        blue = ref in updatable_names  # голубой: как в DBM API — есть более новый снапшот
        updatable = blue and bool(newest and newest.get("connectionString"))
        rows.append({
            "base": base,
            "snapshot_name": ref,
            "snapshot_exp": _parse_date(snap.get("expirationDate")),
            "blue": blue,
            "updatable": updatable,
            "dated": bool(_DATE_SUFFIX_RE.search(base_name)),
            "new_name": newest.get("name") if newest else None,
            "new_connect": newest.get("connectionString") if newest else None,
            "new_expiration": _parse_date(newest.get("expirationDate")) if newest else None,
        })
    return rows


def _ref_from_connect(connect: str) -> str:
    m = re.search(r'(?i)Ref\s*=\s*["\']?([^;"\']+)', connect or "")
    return m.group(1).strip() if m else ""
