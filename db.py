import json
import os
import time

DB_PATH = os.environ.get("DB_PATH", "data/db.json")

_db = {
    "courts": [],
    "witnesses": [],
    "groups": [],
    "sessions": [],
    "msgs": [],
}

def _load():
    global _db
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                _db = json.load(f)
        except Exception:
            pass
    for key in ["courts", "witnesses", "groups", "sessions", "msgs"]:
        if key not in _db:
            _db[key] = []

def _save():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(_db, f, ensure_ascii=False, indent=2)

def now():
    return int(time.time())

_load()

# ── ID generator ──────────────────────────────────────────────────────────────

def _next_id(table):
    items = _db[table]
    return max((i["id"] for i in items), default=0) + 1

# ── Courts ────────────────────────────────────────────────────────────────────

def court_create(data: dict) -> dict:
    court = {"id": _next_id("courts"), **data}
    _db["courts"].append(court)
    _save()
    return court

def court_by_id(court_id: int) -> dict | None:
    return next((c for c in _db["courts"] if c["id"] == court_id), None)

def court_active_in_chat(chat_id: str) -> dict | None:
    return next(
        (c for c in _db["courts"]
         if c.get("court_chat_id") == chat_id
         and c["status"] not in ("concluded", "stopped")),
        None,
    )

def court_awaiting_in_origin(chat_id: str) -> dict | None:
    return next(
        (c for c in _db["courts"]
         if c.get("origin_chat_id") == chat_id
         and c["status"] in ("pending", "awaiting_court")),
        None,
    )

def court_update(court_id: int, patch: dict):
    for c in _db["courts"]:
        if c["id"] == court_id:
            c.update(patch)
            _save()
            return

# ── Witnesses ─────────────────────────────────────────────────────────────────

def witness_add(data: dict):
    _db["witnesses"].append({"id": _next_id("witnesses"), **data})
    _save()

def witnesses_by_court(court_id: int) -> list:
    return [w for w in _db["witnesses"] if w["court_id"] == court_id]

def witness_mark_left(court_id: int, user_id: int):
    for w in _db["witnesses"]:
        if w["court_id"] == court_id and w["user_id"] == user_id:
            w["left_court"] = True
            _save()
            return

# ── Groups ────────────────────────────────────────────────────────────────────

def group_get(chat_id: str) -> dict | None:
    return next((g for g in _db["groups"] if g["chat_id"] == chat_id), None)

def group_upsert(chat_id: str, title: str | None):
    g = group_get(chat_id)
    if g:
        if title:
            g["title"] = title
        _save()
    else:
        _db["groups"].append({"chat_id": chat_id, "title": title, "owner_id": None, "court_chat_id": None})
        _save()

def group_set_owner(owner_id: int, chat_id: str):
    g = group_get(chat_id)
    if g:
        g["owner_id"] = owner_id
    else:
        _db["groups"].append({"chat_id": chat_id, "title": None, "owner_id": owner_id, "court_chat_id": None})
    _save()

def group_set_court_chat(court_chat_id: str, origin_chat_id: str):
    g = group_get(origin_chat_id)
    if g:
        g["court_chat_id"] = court_chat_id
    else:
        _db["groups"].append({"chat_id": origin_chat_id, "title": None, "owner_id": None, "court_chat_id": court_chat_id})
    _save()

def groups_all() -> list:
    return list(_db["groups"])

# ── Sessions ──────────────────────────────────────────────────────────────────

def session_get(user_id: int) -> dict | None:
    return next((s for s in _db["sessions"] if s["user_id"] == user_id), None)

def session_set(user_id: int, state: str, data: str | None):
    existing = session_get(user_id)
    if existing:
        existing["state"] = state
        existing["data"] = data
        existing["updated_at"] = now()
    else:
        _db["sessions"].append({"user_id": user_id, "state": state, "data": data, "updated_at": now()})
    _save()

def session_clear(user_id: int):
    _db["sessions"] = [s for s in _db["sessions"] if s["user_id"] != user_id]
    _save()

# ── Messages (for cleanup) ────────────────────────────────────────────────────

def msg_add(court_id: int, message_id: int, chat_id: str):
    _db["msgs"].append({"court_id": court_id, "message_id": message_id, "chat_id": chat_id})
    _save()

def msgs_by_court(court_id: int) -> list:
    return [m for m in _db["msgs"] if m["court_id"] == court_id]
