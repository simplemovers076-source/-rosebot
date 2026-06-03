"""
db.py — Simple JSON-based persistent storage.
Each chat gets its own file under data/<chat_id>.json
"""

import json
import os
from threading import Lock

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_locks: dict[str, Lock] = {}


def _lock(chat_id: int) -> Lock:
    key = str(chat_id)
    if key not in _locks:
        _locks[key] = Lock()
    return _locks[key]


def _path(chat_id: int) -> str:
    return os.path.join(DATA_DIR, f"{chat_id}.json")


def load(chat_id: int) -> dict:
    p = _path(chat_id)
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save(chat_id: int, data: dict) -> None:
    with _lock(chat_id):
        with open(_path(chat_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get(chat_id: int, key: str, default=None):
    return load(chat_id).get(key, default)


def set(chat_id: int, key: str, value) -> None:
    data = load(chat_id)
    data[key] = value
    save(chat_id, data)


def delete(chat_id: int, key: str) -> None:
    data = load(chat_id)
    data.pop(key, None)
    save(chat_id, data)


# ── Global store (for federations, global bans, etc.) ────────────────────────
GLOBAL_PATH = os.path.join(DATA_DIR, "_global.json")
_global_lock = Lock()


def load_global() -> dict:
    if not os.path.exists(GLOBAL_PATH):
        return {}
    with open(GLOBAL_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_global(data: dict) -> None:
    with _global_lock:
        with open(GLOBAL_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get_global(key: str, default=None):
    return load_global().get(key, default)


def set_global(key: str, value) -> None:
    data = load_global()
    data[key] = value
    save_global(data)
