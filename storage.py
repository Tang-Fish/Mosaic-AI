import json
import time
import uuid
from pathlib import Path

DATA_DIR = Path.home() / ".mosaic"
CHATS_DIR = DATA_DIR / "chats"
FOLDERS_FILE = DATA_DIR / "folders.json"


def _ensure_dirs():
    CHATS_DIR.mkdir(parents=True, exist_ok=True)


def _chat_path(chat_id):
    return CHATS_DIR / f"{chat_id}.json"


def estimate_tokens(messages):
    if not messages:
        return 0
    total = 0
    for m in messages:
        content = m.get("content", "")
        if content:
            total += max(1, round(len(content) / 4))
    return total


def format_tokens(count):
    if count < 1000:
        return f"{count} tokens"
    return f"{round(count / 1000)}K tokens"


def load_folders():
    _ensure_dirs()
    if not FOLDERS_FILE.exists():
        return []
    try:
        data = json.loads(FOLDERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []


def _save_folders(folders):
    _ensure_dirs()
    FOLDERS_FILE.write_text(
        json.dumps(folders, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def create_folder(name):
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        return None
    folders = load_folders()
    folder = {"id": uuid.uuid4().hex[:10], "name": cleaned, "collapsed": False}
    folders.append(folder)
    _save_folders(folders)
    return folder


def rename_folder(folder_id, new_name):
    cleaned = " ".join(new_name.strip().split())
    if not cleaned:
        return
    folders = load_folders()
    for f in folders:
        if f["id"] == folder_id:
            f["name"] = cleaned
            break
    _save_folders(folders)


def toggle_folder_collapsed(folder_id):
    folders = load_folders()
    for f in folders:
        if f["id"] == folder_id:
            f["collapsed"] = not bool(f.get("collapsed", False))
            break
    _save_folders(folders)


def delete_folder(folder_id):
    folders = [f for f in load_folders() if f.get("id") != folder_id]
    _save_folders(folders)
    for path in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("folder_id") == folder_id:
                data["folder_id"] = None
                save_chat(data)
        except (OSError, json.JSONDecodeError):
            continue


def new_chat(folder_id=None):
    return {
        "id": uuid.uuid4().hex[:12],
        "title": "Unnamed Chat",
        "pinned": False,
        "folder_id": folder_id,
        "updated_at": time.time(),
        "messages": [],
    }


def make_title(text, max_len=34):
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "Unnamed Chat"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def save_chat(chat_data):
    _ensure_dirs()
    chat_data["updated_at"] = time.time()
    chat_data.setdefault("pinned", False)
    chat_data.setdefault("folder_id", None)
    path = _chat_path(chat_data["id"])
    path.write_text(json.dumps(chat_data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_chat(chat_id):
    path = _chat_path(chat_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "id" in data and "messages" in data:
            data.setdefault("title", "Unnamed Chat")
            data.setdefault("pinned", False)
            data.setdefault("folder_id", None)
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def set_chat_folder(chat_id, folder_id):
    data = load_chat(chat_id)
    if data is None:
        return
    data["folder_id"] = folder_id
    save_chat(data)


def list_chats(query="", folder_id=None):
    _ensure_dirs()
    q = query.strip().lower()
    chats = []
    for path in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not (isinstance(data, dict) and "id" in data):
                continue
            if folder_id is not None and data.get("folder_id") != folder_id:
                continue
            title = data.get("title", "Unnamed Chat")
            messages = data.get("messages", [])
            if q:
                in_title = q in title.lower()
                in_msgs = any(q in m.get("content", "").lower() for m in messages)
                if not (in_title or in_msgs):
                    continue
            tokens = estimate_tokens(messages)
            chats.append(
                {
                    "id": data["id"],
                    "title": title,
                    "pinned": bool(data.get("pinned", False)),
                    "folder_id": data.get("folder_id"),
                    "updated_at": data.get("updated_at", path.stat().st_mtime),
                    "msg_count": len(messages),
                    "tokens": tokens,
                    "tokens_label": format_tokens(tokens),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue

    chats.sort(key=lambda c: (c["pinned"], c["updated_at"]), reverse=True)
    return chats


def toggle_pin_chat(chat_id):
    data = load_chat(chat_id)
    if data is None:
        return False
    data["pinned"] = not bool(data.get("pinned", False))
    save_chat(data)
    return data["pinned"]


def delete_chat(chat_id):
    path = _chat_path(chat_id)
    if path.exists():
        path.unlink()


def clear_all_chats():
    _ensure_dirs()
    for path in CHATS_DIR.glob("*.json"):
        try:
            path.unlink()
        except OSError:
            continue


def export_all_chats_json():
    _ensure_dirs()
    all_chats = []
    for path in sorted(CHATS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                all_chats.append(data)
        except (OSError, json.JSONDecodeError):
            continue
    return json.dumps(
        {"exported_at": time.time(), "folders": load_folders(), "chats": all_chats},
        indent=2,
        ensure_ascii=False,
    )


def export_chat_markdown(chat_data, bot_name="Mosaic"):
    lines = [f"# {chat_data.get('title', 'Chat')}", ""]
    for msg in chat_data.get("messages", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            lines.append("## You")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append(f"## {bot_name}")
            lines.append(content)
            lines.append("")
    return "\n".join(lines).strip() + "\n"