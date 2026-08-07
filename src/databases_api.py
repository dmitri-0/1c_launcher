"""Vendored клиент DBM API (скопирован из C:\\ROOT\\CodeBase\\Py\\dbm_api\\databases_api.py).

Лежит ВНУТРИ проекта лаунчера, чтобы PyInstaller видел его статическим
импортом и упаковывал вместе с requests — без рантайм-манипуляций sys.path.
"""

import requests
import urllib3

# Отключаем предупреждения о небезопасном запросе (так как verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "http://dbm.comandor.local/api/v1/databases"
ERP_SERVERS_URL = "http://dbm/api/v1/erpservers"
SNAPSHOTS_URL = "http://dbm/api/v1/snapshots"
TASKS_URL = "http://dbm/api/v1/tasks"


def get_databases(access_token: str, timeout: int = 20):
    """
    GET /api/v1/databases, возвращает список dict.
    verify=False используется, чтобы избежать ошибок SSL с локальными самоподписанными сертификатами.
    """
    if not access_token:
        raise ValueError("access_token is empty")

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    # Добавлен параметр verify=False для отключения проверки SSL-сертификата
    response = requests.get(API_URL, headers=headers, timeout=timeout, verify=False)

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    if not isinstance(data, list):
        raise ValueError("API response is not a list")

    return data


def get_snapshots(access_token: str, db_id: int, timeout: int = 20):
    """
    GET /api/v1/databases/{id}, возвращает список снапшотов.
    """
    if not access_token:
        raise ValueError("access_token is empty")
        
    url = f"{API_URL}/{db_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(url, headers=headers, timeout=timeout, verify=False)

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    # Ожидаем список снапшотов
    if not isinstance(data, list):
        raise ValueError("API response is not a list")

    return data


def get_user_snapshots(access_token: str, timeout: int = 20):
    """
    GET /api/v1/snapshots, возвращает список собственных снапшотов пользователя.
    """
    if not access_token:
        raise ValueError("access_token is empty")

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(SNAPSHOTS_URL, headers=headers, timeout=timeout, verify=False)

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    if not isinstance(data, list):
        raise ValueError("API response is not a list")

    return data


def get_erp_servers(access_token: str, timeout: int = 20):
    """
    GET /api/v1/erpservers, возвращает список ERP серверов.
    Фильтрует серверы, исключая те, у которых в поле description содержится "НЕ использовать".
    """
    if not access_token:
        raise ValueError("access_token is empty")

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(ERP_SERVERS_URL, headers=headers, timeout=timeout, verify=False)

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    if not isinstance(data, list):
        raise ValueError("API response is not a list")

    # Фильтруем серверы, исключая те, у которых в description есть "НЕ использовать"
    filtered_servers = [
        server for server in data
        if "НЕ использовать" not in server.get("description", "")
    ]

    return filtered_servers


def create_snapshot(access_token: str, master_snapshot_id: str, erp_server_id: str, description: str, timeout: int = 60):
    """
    POST /api/v1/snapshots
    """
    if not access_token:
        raise ValueError("access_token is empty")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "masterSnapshotId": master_snapshot_id,
        "erpServerId": erp_server_id,
        "description": description
    }

    response = requests.post(SNAPSHOTS_URL, json=payload, headers=headers, timeout=timeout, verify=False)

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    return response.json()


def delete_snapshot(access_token: str, snapshot_id: int, timeout: int = 20):
    """
    DELETE /api/v1/snapshots/{id}
    Удаляет снапшот по его ID.
    """
    if not access_token:
        raise ValueError("access_token is empty")

    url = f"{SNAPSHOTS_URL}/{snapshot_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.delete(url, headers=headers, timeout=timeout, verify=False)

    if response.status_code not in (200, 204):
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    return True


def get_task_status(access_token: str, task_id: str, timeout: int = 20):
    """
    GET /api/v1/tasks/{id}
    """
    if not access_token:
        raise ValueError("access_token is empty")

    url = f"{TASKS_URL}/{task_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(url, headers=headers, timeout=timeout, verify=False)

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

    return response.json()


def format_databases(databases: list):
    """Форматирует список баз по шаблону: <id>. <name> (<description>)"""
    lines = []
    for item in databases:
        if not isinstance(item, dict):
            continue
        db_id = item.get("id", "")
        name = item.get("name", "")
        description = item.get("description", "")
        lines.append(f"{db_id}. {name} ({description})")

    return "\n".join(lines)
