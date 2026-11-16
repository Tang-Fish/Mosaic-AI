import base64
import ctypes
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import settings

DATA_DIR = Path.home() / ".mosaic"
CONNECTIONS_FILE = DATA_DIR / "connections.json"
AGENTS_FILE = DATA_DIR / "agents.json"
AGENT_OUTPUTS_DIR = DATA_DIR / "agent_outputs"

MODE_SPECS = [
    (
        "chat",
        "Chat",
        "Chat with Mosaic AI simple chatbot",
    ),
    (
        "agent",
        "Agent",
        "Create and run custom Mosaic Agents with unique personalities, missions, and isolated API keys",
    ),
    (
        "cowork",
        "Cowork",
        "Allows Mosaic AI to see your screen and control your cursor",
    ),
]

AGENT_AVATAR_COLORS = [
    ("Ocean Blue", "#3b82f6"),
    ("Emerald", "#10b981"),
    ("Violet", "#8b5cf6"),
    ("Amber", "#f59e0b"),
    ("Crimson", "#ef4444"),
    ("Cyan", "#06b6d4"),
]

AGENT_AVATAR_BADGES = [
    ("orbit", "Orbit"),
    ("code", "Code"),
    ("search", "Scout"),
    ("sparkle", "Spark"),
    ("bolt", "Bolt"),
    ("shield", "Guard"),
]

SERVICE_SPECS = {
    "none": {
        "label": "No External API (Built-in Notes & Reports Only)",
        "short": "Built-in",
        "placeholder": "No API key needed",
        "needs_key": False,
    },
    "github": {
        "label": "GitHub (Profile, Repos, READMEs & Search)",
        "short": "GitHub",
        "placeholder": "GitHub Personal Access Token (ghp_... or github_pat_...)",
        "needs_key": True,
    },
    "youtube": {
        "label": "YouTube Data API v3 (Video & Channel Search)",
        "short": "YouTube",
        "placeholder": "YouTube Data API v3 Key (AIza...)",
        "needs_key": True,
    },
    "google_drive": {
        "label": "Google Drive (Search & Read Docs/Files)",
        "short": "Drive",
        "placeholder": "Google Drive OAuth Access Token (ya29...)",
        "needs_key": True,
    },
    "notion": {
        "label": "Notion (Search Pages & Databases)",
        "short": "Notion",
        "placeholder": "Notion Integration Secret (secret_... or ntn_...)",
        "needs_key": True,
    },
    "weather": {
        "label": "Live Weather (Open-Meteo — No Key Needed)",
        "short": "Weather",
        "placeholder": "No API key required",
        "needs_key": False,
    },
    "custom_api": {
        "label": "Custom REST API (GET JSON Endpoint)",
        "short": "Custom API",
        "placeholder": "Optional Bearer Token / API Key",
        "needs_key": False,
    },
}

DEFAULT_CONNECTIONS = {
    "github": {
        "name": "GitHub",
        "enabled": False,
        "api_key": "",
        "placeholder": "GitHub Personal Access Token (ghp_... or github_pat_...)",
        "description": "View your GitHub profile, list your public/private repos, inspect repo READMEs, and search GitHub.",
    },
    "youtube": {
        "name": "YouTube",
        "enabled": False,
        "api_key": "",
        "placeholder": "YouTube Data API v3 Key (AIza...)",
        "description": "Search YouTube videos, channels, and descriptions.",
    },
    "google_drive": {
        "name": "Google Drive",
        "enabled": False,
        "api_key": "",
        "placeholder": "Google Drive OAuth Access Token (ya29...)",
        "description": "Search files and read text/Google Docs from your Drive.",
    },
    "notion": {
        "name": "Notion",
        "enabled": False,
        "api_key": "",
        "placeholder": "Notion Integration Secret (secret_... or ntn_...)",
        "description": "Search your connected Notion pages and databases.",
    },
    "weather": {
        "name": "Live Weather",
        "enabled": True,
        "api_key": "",
        "placeholder": "No API key required (built-in Open-Meteo)",
        "description": "Check real-time weather and temperatures for any city.",
    },
    "custom_api": {
        "name": "Custom REST API",
        "enabled": False,
        "api_key": "",
        "base_url": "",
        "custom_name": "My API",
        "placeholder": "Optional Bearer Token / API Key",
        "description": "Query any custom HTTP JSON endpoint (GET base_url + path).",
    },
}


def make_mode_icon(mode_key, color_hex, size=22):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color_hex))
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    if mode_key == "chat":
        painter.drawRoundedRect(3, 4, size - 6, size - 9, 4.0, 4.0)
        painter.drawLine(7, size - 5, 5, size - 2)
        painter.drawLine(5, size - 2, 11, size - 5)
        mid_y = int((size - 5) / 2) + 2
        painter.drawLine(7, mid_y - 2, size - 7, mid_y - 2)
        painter.drawLine(7, mid_y + 2, size - 10, mid_y + 2)

    elif mode_key == "agent":
        cx, cy = size / 2.0, size / 2.0
        painter.drawEllipse(int(cx - 3), int(cy - 3), 6, 6)
        nodes = [(5, 5), (size - 5, 5), (5, size - 5), (size - 5, size - 5)]
        for nx, ny in nodes:
            painter.drawLine(int(cx), int(cy), int(nx), int(ny))
            painter.drawEllipse(int(nx - 2), int(ny - 2), 4, 4)

    elif mode_key == "cowork":
        painter.drawRoundedRect(2, 3, size - 4, size - 8, 2.5, 2.5)
        painter.drawLine(int(size / 2) - 4, size - 2, int(size / 2) + 4, size - 2)
        painter.drawLine(int(size / 2), size - 5, int(size / 2), size - 2)
        px, py = int(size * 0.44), int(size * 0.32)
        painter.drawLine(px, py, px, py + 7)
        painter.drawLine(px, py, px + 6, py + 5)
        painter.drawLine(px, py + 7, px + 2, py + 5)
        painter.drawLine(px + 2, py + 5, px + 6, py + 5)

    painter.end()
    return QIcon(pm)


def make_agent_avatar_icon(color_hex="#3b82f6", badge="orbit", size=28):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)

    base = QColor(color_hex or "#3b82f6")
    fill = QColor(base)
    fill.setAlpha(42)
    painter.setBrush(QBrush(fill))
    ring_pen = QPen(base)
    ring_pen.setWidthF(1.7)
    painter.setPen(ring_pen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    glyph_pen = QPen(base)
    glyph_pen.setWidthF(1.7)
    glyph_pen.setCapStyle(Qt.RoundCap)
    glyph_pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(glyph_pen)
    painter.setBrush(Qt.NoBrush)

    c = size / 2.0
    if badge == "code":
        painter.drawLine(int(c - 3), int(c - 3), int(c - 6), int(c))
        painter.drawLine(int(c - 6), int(c), int(c - 3), int(c + 3))
        painter.drawLine(int(c + 3), int(c - 3), int(c + 6), int(c))
        painter.drawLine(int(c + 6), int(c), int(c + 3), int(c + 3))
        painter.drawLine(int(c + 1), int(c - 4), int(c - 1), int(c + 4))
    elif badge == "search":
        painter.drawEllipse(int(c - 5), int(c - 5), 8, 8)
        painter.drawLine(int(c + 2), int(c + 2), int(c + 5), int(c + 5))
    elif badge == "sparkle":
        painter.drawLine(int(c), int(c - 6), int(c), int(c + 6))
        painter.drawLine(int(c - 6), int(c), int(c + 6), int(c))
        painter.drawLine(int(c - 3), int(c - 3), int(c + 3), int(c + 3))
        painter.drawLine(int(c + 3), int(c - 3), int(c - 3), int(c + 3))
    elif badge == "bolt":
        painter.drawLine(int(c + 1), int(c - 6), int(c - 3), int(c))
        painter.drawLine(int(c - 3), int(c), int(c + 2), int(c))
        painter.drawLine(int(c + 2), int(c), int(c - 1), int(c + 6))
    elif badge == "shield":
        painter.drawLine(int(c), int(c - 6), int(c + 5), int(c - 4))
        painter.drawLine(int(c + 5), int(c - 4), int(c + 4), int(c + 2))
        painter.drawLine(int(c + 4), int(c + 2), int(c), int(c + 6))
        painter.drawLine(int(c), int(c + 6), int(c - 4), int(c + 2))
        painter.drawLine(int(c - 4), int(c + 2), int(c - 5), int(c - 4))
        painter.drawLine(int(c - 5), int(c - 4), int(c), int(c - 6))
    else:  # "orbit"
        painter.setBrush(QBrush(base))
        painter.drawEllipse(int(c - 2.5), int(c - 2.5), 5, 5)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(int(c - 6.5), int(c - 6.5), 13, 13)

    painter.end()
    return QIcon(pm)


def _clean_token(raw_key):
    cleaned = (raw_key or "").strip().strip('"').strip("'")
    cleaned = re.sub(r"^(?:bearer|token)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def mask_api_key(raw_key):
    tok = _clean_token(raw_key)
    if not tok:
        return "Not set"
    if len(tok) <= 8:
        return "••••" + tok[-2:]
    return f"{tok[:4]}••••{tok[-4:]}"


def _make_handle(name):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "mosaic-agent").strip().lower()).strip("-")
    if not slug:
        slug = "mosaic-agent"
    return f"@{slug[:28]}"


def _github_headers(api_key=""):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Mosaic-Local-AI",
    }
    tok = _clean_token(api_key)
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def load_connections():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    merged = {k: dict(v) for k, v in DEFAULT_CONNECTIONS.items()}
    if CONNECTIONS_FILE.exists():
        try:
            raw = json.loads(CONNECTIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, val in raw.items():
                    if key in merged and isinstance(val, dict):
                        merged[key].update(val)
        except (OSError, json.JSONDecodeError):
            pass
    return merged


def save_connections(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = load_connections()
    for key, val in data.items():
        if key in current and isinstance(val, dict):
            current[key].update(val)
    CONNECTIONS_FILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return current


def _default_starter_agent():
    # Migrate any previously configured GitHub key into the starter Mosaic Agent if present
    existing_conn = load_connections()
    gh_key = _clean_token(existing_conn.get("github", {}).get("api_key", ""))
    return {
        "id": "mosaic_agent_default",
        "name": "Mosaic Agent",
        "handle": "@mosaic-agent",
        "avatar_color": "#3b82f6",
        "avatar_badge": "orbit",
        "personality": "Sharp, proactive, and concise assistant who focuses on accuracy and clear action.",
        "instructions": (
            "Help me inspect my connected workspace, summarize findings clearly, "
            "save important notes, and generate clean Markdown reports when requested."
        ),
        "standing_mission": "Check my connected service and give me a concise status briefing.",
        "boundary_mode": "auto",
        "service_type": "github" if gh_key else "weather",
        "api_key": gh_key,
        "custom_base_url": "",
        "custom_service_name": "My API",
        "strict_isolation": True,
        "notes": [],
        "created_at": time.time(),
    }


def _normalize_agent(raw):
    base = _default_starter_agent()
    if isinstance(raw, dict):
        base.update(raw)
    base["id"] = str(base.get("id") or f"agent_{uuid.uuid4().hex[:10]}")
    base["name"] = (base.get("name") or "Mosaic Agent").strip()
    h = (base.get("handle") or "").strip()
    if not h:
        h = _make_handle(base["name"])
    elif not h.startswith("@"):
        h = "@" + h
    base["handle"] = h
    base["avatar_color"] = base.get("avatar_color") or "#3b82f6"
    base["avatar_badge"] = base.get("avatar_badge") or "orbit"
    base["personality"] = (base.get("personality") or "").strip()
    base["instructions"] = (base.get("instructions") or "").strip()
    base["standing_mission"] = (base.get("standing_mission") or "").strip()
    base["boundary_mode"] = base.get("boundary_mode") if base.get("boundary_mode") in ("auto", "confirm") else "auto"
    stype = (base.get("service_type") or "none").strip().lower()
    base["service_type"] = stype if stype in SERVICE_SPECS else "none"
    base["api_key"] = _clean_token(base.get("api_key") or "")
    base["custom_base_url"] = (base.get("custom_base_url") or "").strip()
    base["custom_service_name"] = (base.get("custom_service_name") or "My API").strip()
    base["strict_isolation"] = bool(base.get("strict_isolation", True))
    notes = base.get("notes")
    base["notes"] = [str(n).strip() for n in notes if str(n).strip()] if isinstance(notes, list) else []
    return base


def _load_agents_store():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if AGENTS_FILE.exists():
        try:
            raw = json.loads(AGENTS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("agents"), list) and raw["agents"]:
                agents = [_normalize_agent(a) for a in raw["agents"]]
                active_id = raw.get("active_agent_id") or agents[0]["id"]
                if not any(a["id"] == active_id for a in agents):
                    active_id = agents[0]["id"]
                return {"active_agent_id": active_id, "agents": agents}
        except (OSError, json.JSONDecodeError):
            pass

    starter = _default_starter_agent()
    store = {"active_agent_id": starter["id"], "agents": [starter]}
    _save_agents_store(store)
    return store


def _save_agents_store(store):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AGENTS_FILE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def list_agents():
    return _load_agents_store()["agents"]


def get_agent(agent_id):
    store = _load_agents_store()
    for a in store["agents"]:
        if a["id"] == agent_id:
            return a
    return None


def get_active_agent():
    store = _load_agents_store()
    active_id = store["active_agent_id"]
    for a in store["agents"]:
        if a["id"] == active_id:
            return a
    return store["agents"][0]


def set_active_agent(agent_id):
    store = _load_agents_store()
    if any(a["id"] == agent_id for a in store["agents"]):
        store["active_agent_id"] = agent_id
        _save_agents_store(store)
    return get_active_agent()


def create_agent(agent_fields):
    store = _load_agents_store()
    new_data = dict(agent_fields)
    new_data["id"] = f"agent_{uuid.uuid4().hex[:10]}"
    new_data["created_at"] = time.time()
    agent = _normalize_agent(new_data)
    store["agents"].append(agent)
    store["active_agent_id"] = agent["id"]
    _save_agents_store(store)
    return agent


def update_agent(agent_id, updates):
    store = _load_agents_store()
    updated_obj = None
    for idx, existing in enumerate(store["agents"]):
        if existing["id"] == agent_id:
            merged = dict(existing)
            merged.update(updates)
            merged["id"] = agent_id
            updated_obj = _normalize_agent(merged)
            store["agents"][idx] = updated_obj
            break
    if updated_obj is not None:
        _save_agents_store(store)
    return updated_obj


def delete_agent(agent_id):
    store = _load_agents_store()
    remaining = [a for a in store["agents"] if a["id"] != agent_id]
    if not remaining:
        remaining = [_default_starter_agent()]
    store["agents"] = remaining
    if not any(a["id"] == store["active_agent_id"] for a in remaining):
        store["active_agent_id"] = remaining[0]["id"]
    _save_agents_store(store)
    return get_active_agent()


def add_agent_note(agent_id, note_text):
    clean = (note_text or "").strip()
    if not clean:
        return None
    agent = get_agent(agent_id)
    if agent is None:
        return None
    notes = list(agent.get("notes", []))
    if clean not in notes:
        notes.append(clean)
        notes = notes[-25:]
        return update_agent(agent_id, {"notes": notes})
    return agent


def get_agent_service_summary(agent):
    if not agent:
        return "No service"
    stype = agent.get("service_type", "none")
    spec = SERVICE_SPECS.get(stype, SERVICE_SPECS["none"])
    short = agent.get("custom_service_name") or spec["short"] if stype == "custom_api" else spec["short"]
    tok = _clean_token(agent.get("api_key", ""))
    if stype == "none":
        return "Built-in Tools"
    if stype == "weather":
        return "Live Weather"
    if tok:
        return f"{short} • Private Key"
    if not agent.get("strict_isolation", True):
        return f"{short} • Shared"
    return f"{short} • No Key"


def build_agent_system_prompt(base_prompt, agent=None):
    ag = agent if agent is not None else get_active_agent()
    stype = ag.get("service_type", "none")
    tok = _clean_token(ag.get("api_key", ""))
    strict = bool(ag.get("strict_isolation", True))

    personality_block = ag.get("personality") or "Helpful, focused, and reliable specialist agent."
    instructions_block = ag.get("instructions") or "Assist the user with tasks using your assigned tools."
    mission_block = ag.get("standing_mission") or ""
    notes = ag.get("notes", [])

    lines = [
        f"{base_prompt}\n\n"
        f"[MOSAIC AGENT ACTIVE: {ag['name']} ({ag['handle']})]\n"
        f"Your Personality & Voice: {personality_block}\n"
        f"Your Core Role & Instructions (What You Are Supposed To Do):\n{instructions_block}",
    ]
    if mission_block:
        lines.append(f"Your Standing Mission: {mission_block}")
    if notes:
        formatted_notes = "\n".join(f"- {n}" for n in notes[-12:])
        lines.append(f"\n[YOUR PERSISTENT AGENT MEMORY NOTES]:\n{formatted_notes}")

    lines.append(
        "\n[HOW TO USE YOUR TOOLS]\n"
        "You have live tool execution enabled. Do NOT claim you lack access to your assigned tool.\n"
        "When you need to run a tool, output ONLY this single line and nothing else:\n"
        "[[CALL_API: tool_id | query_or_command]]\n\n"
        "Available tools for THIS Mosaic Agent:"
    )

    if stype == "github" and (tok or not strict):
        lines.append(
            "- github (using this agent's dedicated API key): Access GitHub. Commands:\n"
            "  * [[CALL_API: github | me]] -> get authenticated GitHub profile\n"
            "  * [[CALL_API: github | my repos]] -> list your own public & private repositories\n"
            "  * [[CALL_API: github | owner/repo]] -> inspect a specific repository and read its README\n"
            "  * [[CALL_API: github | search keyword]] -> search public GitHub repositories"
        )
    elif stype == "youtube" and (tok or not strict):
        lines.append("- youtube (using this agent's dedicated API key): Search YouTube videos. Example: [[CALL_API: youtube | python tutorial]]")
    elif stype == "google_drive" and (tok or not strict):
        lines.append("- google_drive (using this agent's dedicated API key): Search and read files in Google Drive. Example: [[CALL_API: google_drive | project notes]]")
    elif stype == "notion" and (tok or not strict):
        lines.append("- notion (using this agent's dedicated API key): Search Notion pages. Example: [[CALL_API: notion | roadmap]]")
    elif stype == "weather":
        lines.append("- weather: Check live weather for any city. Example: [[CALL_API: weather | Melbourne]]")
    elif stype == "custom_api" and (ag.get("custom_base_url") or not strict):
        cname = ag.get("custom_service_name") or "Custom REST API"
        burl = ag.get("custom_base_url", "")
        lines.append(
            f"- custom_api ({cname} at {burl}, using this agent's dedicated credentials): "
            "Query GET path or search term. Example: [[CALL_API: custom_api | /status]]"
        )
    elif stype != "none":
        lines.append(
            f"- Note: This agent is configured for '{stype}', but its individual API key has not been entered yet. "
            "Remind the user to click 'Edit' on this Mosaic Agent to paste its private API key."
        )

    lines.append(
        "- save_note: Save an important fact or finding into this Mosaic Agent's persistent memory. "
        "Example: [[CALL_API: save_note | User's main repo is username/mosaic]]"
    )
    lines.append(
        "- write_report: Save a formatted Markdown report or deliverable file for the user. "
        "Example: [[CALL_API: write_report | weekly-summary.md :: # Weekly Summary\\n...]]"
    )
    lines.append(
        "\nStay in character with your Personality and follow your Core Role & Instructions. "
        "Once tool data returns, synthesize a clear, accurate response."
    )
    return "\n".join(lines)


def _strip_filler_words(text, extra_words=()):
    stopwords = {
        "a", "an", "the", "my", "me", "i", "please", "can", "you", "could",
        "show", "list", "get", "check", "look", "see", "view", "open", "read",
        "find", "search", "for", "on", "in", "of", "to", "from", "with", "about",
        "what", "whats", "what's", "are", "is", "all", "recent", "latest", "run",
        "mission", "standing", "briefing", "status", "give",
    }
    stopwords.update(w.lower() for w in extra_words)
    tokens = re.findall(r"[a-zA-Z0-9_.-]+", text.lower())
    kept = [t for t in tokens if t not in stopwords]
    return " ".join(kept).strip()


def infer_fallback_tool_call(user_text, agent=None):
    """Fallback router when smaller local models omit [[CALL_API: ...]]."""
    ag = agent if agent is not None else get_active_agent()
    text = (user_text or "").strip()
    low = text.lower()
    if not text:
        return None

    # Explicit note-taking command
    note_match = re.match(r"^(?:save\s+note|remember\s+note|note\s+that)[:\s]+(.+)$", text, re.I)
    if note_match:
        return ("save_note", note_match.group(1).strip())

    stype = ag.get("service_type", "none")
    tok = _clean_token(ag.get("api_key", ""))
    strict = bool(ag.get("strict_isolation", True))

    if stype == "github" and (tok or not strict):
        repo_slug = re.search(r"\b([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\b", text)
        if any(w in low for w in ("profile", "who am i", "whoami", "username", "account", "bio")):
            return ("github", "me")
        if repo_slug and "github.com" not in repo_slug.group(1).lower():
            return ("github", repo_slug.group(1))
        if re.search(r"\b(search|find|explore|trending)\b", low) and "my " not in low:
            term = _strip_filler_words(text, ("github", "repo", "repos", "repository", "repositories", "public"))
            if term:
                return ("github", f"search {term}")
        return ("github", "my repos")

    if stype == "youtube" and (tok or not strict):
        cleaned_q = _strip_filler_words(text, ("youtube", "video", "videos", "channel", "channels"))
        return ("youtube", cleaned_q or text)

    if stype == "google_drive" and (tok or not strict):
        cleaned_q = _strip_filler_words(text, ("google", "drive", "gdrive", "file", "files", "doc", "docs", "document"))
        return ("google_drive", cleaned_q)

    if stype == "notion" and (tok or not strict):
        cleaned_q = _strip_filler_words(text, ("notion", "page", "pages", "note", "notes", "workspace", "database"))
        return ("notion", cleaned_q)

    if stype == "weather":
        m = re.search(r"(?:weather|forecast|temperature)\s+(?:in|for|at)\s+([a-zA-Z\s,.-]+)", text, re.I)
        city = m.group(1).strip(" ?.!") if m else "Melbourne"
        return ("weather", city)

    if stype == "custom_api" and (ag.get("custom_base_url") or not strict):
        path_match = re.search(r"(/[a-zA-Z0-9_./?=&-]+)", text)
        return ("custom_api", path_match.group(1) if path_match else "")

    return None


def _run_github_tool(arg, api_key, timeout=12):
    headers = _github_headers(api_key)
    tok = _clean_token(api_key)
    q = (arg or "").strip()
    low = q.lower()

    if any(w in low for w in ("me", "profile", "whoami", "username", "my account", "user info")) and "/" not in low:
        if not tok:
            return "This Mosaic Agent has no GitHub API key configured. Click 'Edit' on the agent to add its private token.", []
        r = requests.get("https://api.github.com/user", headers=headers, timeout=timeout)
        if r.status_code == 401:
            return "GitHub returned 401 Unauthorized — this agent's GitHub token is invalid or expired.", []
        r.raise_for_status()
        u = r.json()
        login = u.get("login", "unknown")
        name = u.get("name") or login
        url = u.get("html_url", f"https://github.com/{login}")
        pub = u.get("public_repos", 0)
        priv = u.get("total_private_repos", 0)
        bio = u.get("bio") or "No bio"
        summary = (
            f"Authenticated GitHub User: {name} (@{login})\n"
            f"Profile URL: {url}\n"
            f"Public Repositories: {pub} | Private Repositories: {priv}\n"
            f"Bio: {bio}"
        )
        return summary, [{"title": f"GitHub: @{login}", "url": url}]

    repo_match = re.search(r"\b([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\b", q)
    if repo_match and not low.startswith("search "):
        slug = repo_match.group(1)
        r = requests.get(f"https://api.github.com/repos/{slug}", headers=headers, timeout=timeout)
        if r.status_code == 404:
            return f"Repository '{slug}' was not found (or this agent's token lacks 'repo' scope for private repos).", []
        if r.status_code == 401:
            return "GitHub returned 401 Unauthorized — check this agent's GitHub token.", []
        r.raise_for_status()
        repo = r.json()
        url = repo.get("html_url", f"https://github.com/{slug}")
        vis = "Private" if repo.get("private") else "Public"
        desc = repo.get("description") or "No description"
        lang = repo.get("language") or "Unknown"
        stars = repo.get("stargazers_count", 0)
        lines = [
            f"Repository: {repo.get('full_name', slug)} ({vis})",
            f"URL: {url}",
            f"Language: {lang} | Stars: {stars} | Default Branch: {repo.get('default_branch', 'main')}",
            f"Description: {desc}",
        ]
        rm = requests.get(f"https://api.github.com/repos/{slug}/readme", headers=headers, timeout=timeout)
        if rm.status_code == 200:
            encoded = rm.json().get("content", "")
            if encoded:
                try:
                    decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")[:2500]
                    lines.append(f"\nREADME excerpt:\n{decoded}")
                except Exception:
                    pass
        return "\n".join(lines), [{"title": f"GitHub: {slug}", "url": url}]

    is_explicit_public_search = low.startswith("search ") or not tok
    if is_explicit_public_search:
        search_term = re.sub(r"^search\s+", "", q, flags=re.IGNORECASE).strip()
        if not search_term:
            return "Specify a search keyword to search public GitHub repositories.", []
        r = requests.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params={"q": search_term, "per_page": 6},
            timeout=timeout,
        )
        if r.status_code == 401:
            return "GitHub returned 401 Unauthorized — this agent's token is invalid or expired.", []
        r.raise_for_status()
        repos = r.json().get("items", [])
        if not repos:
            return f"No public GitHub repositories found for '{search_term}'.", []
        lines = [f"Public GitHub search results for '{search_term}':"]
        sources = []
        for idx, repo in enumerate(repos, 1):
            full_name = repo.get("full_name", "")
            stars = repo.get("stargazers_count", 0)
            desc = (repo.get("description") or "")[:200]
            url = repo.get("html_url", "")
            lines.append(f"[{idx}] {full_name} (★ {stars}) — {url}\n    {desc}")
            if url:
                sources.append({"title": full_name, "url": url})
        return "\n".join(lines), sources

    r = requests.get(
        "https://api.github.com/user/repos",
        headers=headers,
        params={"sort": "updated", "per_page": 15, "affiliation": "owner,collaborator"},
        timeout=timeout,
    )
    if r.status_code == 401:
        return "GitHub returned 401 Unauthorized — this agent's GitHub token is invalid or expired.", []
    r.raise_for_status()
    repos = r.json()
    if not repos:
        return "No repositories found on the GitHub account linked to this agent.", []

    generic_tokens = {"my", "repos", "repo", "repositories", "repository", "list", "all", "github", "user", "user_repos", "my_repos"}
    filter_words = [w for w in re.findall(r"[a-zA-Z0-9_.-]+", low) if w not in generic_tokens]
    if filter_words:
        matched = [
            repo for repo in repos
            if any(
                fw in (repo.get("full_name", "") + " " + (repo.get("description") or "")).lower()
                for fw in filter_words
            )
        ]
        if matched:
            repos = matched

    lines = [f"Repositories accessible to this Mosaic Agent ({len(repos)} shown):"]
    sources = []
    for idx, repo in enumerate(repos, 1):
        full_name = repo.get("full_name", "")
        vis = "Private" if repo.get("private") else "Public"
        lang = repo.get("language") or "n/a"
        stars = repo.get("stargazers_count", 0)
        desc = (repo.get("description") or "").strip()[:160]
        url = repo.get("html_url", "")
        lines.append(f"[{idx}] {full_name} [{vis} | {lang} | ★ {stars}] — {url}")
        if desc:
            lines.append(f"    {desc}")
        if url:
            sources.append({"title": full_name, "url": url})
    return "\n".join(lines), sources


def test_agent_service(service_type, api_key="", base_url="", timeout=10):
    """Verify an agent's individual API key immediately inside the Mosaic Agent editor."""
    tid = (service_type or "none").strip().lower()
    tok = _clean_token(api_key)
    try:
        if tid == "none":
            return True, "Built-in Notes & Report Writer ready (no external API key needed)."

        if tid == "github":
            if not tok:
                return False, "Paste a GitHub Personal Access Token (ghp_...) first."
            r = requests.get("https://api.github.com/user", headers=_github_headers(tok), timeout=timeout)
            if r.status_code == 401:
                return False, "401 Unauthorized — invalid or expired GitHub token."
            r.raise_for_status()
            u = r.json()
            scopes = r.headers.get("X-OAuth-Scopes", "none")
            return (
                True,
                f"Verified for this agent: @{u.get('login')} ({u.get('public_repos', 0)} public, "
                f"{u.get('total_private_repos', 0)} private repos | scopes: {scopes or 'none'})",
            )

        if tid == "youtube":
            if not tok:
                return False, "Enter a YouTube Data API v3 key first."
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "q": "python", "type": "video", "maxResults": 1, "key": tok},
                timeout=timeout,
            )
            if r.status_code in (400, 403):
                return False, f"YouTube API rejected key ({r.status_code})."
            r.raise_for_status()
            return True, "Verified YouTube Data API v3 key for this agent."

        if tid == "google_drive":
            if not tok:
                return False, "Enter a Google Drive OAuth token first."
            r = requests.get(
                "https://www.googleapis.com/drive/v3/about",
                headers={"Authorization": f"Bearer {tok}"},
                params={"fields": "user(displayName,emailAddress)"},
                timeout=timeout,
            )
            if r.status_code == 401:
                return False, "401 Unauthorized — OAuth token expired or invalid."
            r.raise_for_status()
            email = r.json().get("user", {}).get("emailAddress", "Google Drive")
            return True, f"Verified Google Drive access ({email}) for this agent."

        if tid == "notion":
            if not tok:
                return False, "Enter a Notion integration secret first."
            r = requests.get(
                "https://api.notion.com/v1/users/me",
                headers={"Authorization": f"Bearer {tok}", "Notion-Version": "2022-06-28"},
                timeout=timeout,
            )
            if r.status_code == 401:
                return False, "401 Unauthorized — invalid Notion secret."
            r.raise_for_status()
            return True, f"Verified Notion integration ({r.json().get('name', 'Integration')}) for this agent."

        if tid == "weather":
            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": -37.8136, "longitude": 144.9631, "current": "temperature_2m"},
                timeout=timeout,
            )
            r.raise_for_status()
            return True, "Connected to Open-Meteo Live Weather."

        if tid == "custom_api":
            burl = (base_url or "").strip()
            if not burl:
                return False, "Enter a Base URL first."
            headers = {"Accept": "application/json"}
            if tok:
                headers["Authorization"] = f"Bearer {tok}"
            r = requests.get(burl, headers=headers, timeout=timeout)
            return True, f"Reached {burl} (HTTP {r.status_code})."

    except Exception as e:
        return False, f"Connection error: {e}"

    return False, "Unknown service."


def execute_agent_tool(tool_id, argument, agent=None, timeout=12):
    """Execute a tool strictly scoped to the selected Mosaic Agent and its individual API key."""
    ag = agent if agent is not None else get_active_agent()
    tid = (tool_id or "").strip().lower()
    arg = (argument or "").strip()

    # Built-in persistent agent note tool
    if tid in ("save_note", "note", "remember"):
        if not arg:
            return "No note text provided.", []
        add_agent_note(ag["id"], arg)
        return f"Saved to {ag['name']}'s persistent memory: '{arg}'", []

    # Built-in Markdown report writer tool
    if tid in ("write_report", "report", "save_report"):
        if "::" in arg:
            raw_fname, body = arg.split("::", 1)
        else:
            raw_fname = f"{ag['id']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
            body = arg
        safe_fname = re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw_fname.strip()).strip("-") or "report.md"
        if not safe_fname.endswith(".md"):
            safe_fname += ".md"
        out_dir = AGENT_OUTPUTS_DIR / re.sub(r"[^a-zA-Z0-9_-]+", "_", ag["id"])
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / safe_fname
        out_path.write_text(body.strip() + "\n", encoding="utf-8")
        return (
            f"Saved Markdown report to {out_path}",
            [{"title": f"Report: {safe_fname}", "url": out_path.as_uri()}],
        )

    assigned_service = ag.get("service_type", "none")
    strict = bool(ag.get("strict_isolation", True))

    if strict and tid != assigned_service:
        allowed_label = SERVICE_SPECS.get(assigned_service, {}).get("short", assigned_service)
        return (
            f"Access blocked by isolation policy: {ag['name']} only has credentials for '{allowed_label}' "
            f"and cannot access '{tid}'.",
            [],
        )

    # Resolve credentials exclusively from this agent (or optional shared fallback if isolation is off)
    if tid == assigned_service:
        api_key = _clean_token(ag.get("api_key", ""))
        custom_base_url = (ag.get("custom_base_url") or "").strip()
        custom_name = (ag.get("custom_service_name") or "Custom API").strip()
    elif not strict:
        shared = load_connections().get(tid, {})
        if not shared.get("enabled"):
            return f"Tool '{tid}' is not enabled on {ag['name']} or shared connections.", []
        api_key = _clean_token(shared.get("api_key", ""))
        custom_base_url = (shared.get("base_url") or "").strip()
        custom_name = (shared.get("custom_name") or "Custom API").strip()
    else:
        return f"Tool '{tid}' is not available to {ag['name']}.", []

    try:
        if tid == "github":
            return _run_github_tool(arg, api_key, timeout=timeout)

        if tid == "youtube":
            if not api_key:
                return f"{ag['name']} has no YouTube API key set. Click 'Edit' on this agent to add its key.", []
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": arg,
                    "type": "video",
                    "maxResults": 5,
                    "key": api_key,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if not items:
                return f"No YouTube videos found for '{arg}'.", []
            lines = [f"YouTube search results for '{arg}':"]
            sources = []
            for idx, v in enumerate(items, 1):
                vid = v.get("id", {}).get("videoId", "")
                snip = v.get("snippet", {})
                title = snip.get("title", "Untitled")
                channel = snip.get("channelTitle", "")
                desc = (snip.get("description") or "")[:200]
                url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
                lines.append(f"[{idx}] {title} (Channel: {channel}) — {url}\n    {desc}")
                if url:
                    sources.append({"title": title, "url": url})
            return "\n".join(lines), sources

        if tid == "google_drive":
            if not api_key:
                return f"{ag['name']} has no Google Drive OAuth token set. Click 'Edit' on this agent to add its token.", []
            headers = {"Authorization": f"Bearer {api_key}"}
            safe_q = arg.replace("'", "\\'")
            drive_q = f"name contains '{safe_q}' and trashed = false" if safe_q else "trashed = false"
            r = requests.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                params={
                    "q": drive_q,
                    "orderBy": "modifiedTime desc",
                    "pageSize": 6,
                    "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
                },
                timeout=timeout,
            )
            r.raise_for_status()
            files = r.json().get("files", [])
            if not files:
                return f"No Google Drive files found{f' matching {arg!r}' if arg else ''}.", []
            lines = [f"Google Drive files{f' matching {arg!r}' if arg else ''}:"]
            sources = []
            for idx, f in enumerate(files, 1):
                fid = f.get("id", "")
                fname = f.get("name", "Untitled")
                mtype = f.get("mimeType", "")
                link = f.get("webViewLink") or f"https://drive.google.com/file/d/{fid}/view"
                preview = ""
                if mtype == "application/vnd.google-apps.document" and fid:
                    exp = requests.get(
                        f"https://www.googleapis.com/drive/v3/files/{fid}/export",
                        headers=headers,
                        params={"mimeType": "text/plain"},
                        timeout=timeout,
                    )
                    if exp.status_code == 200:
                        preview = exp.text[:500].strip()
                elif mtype.startswith("text/") and fid:
                    dl = requests.get(
                        f"https://www.googleapis.com/drive/v3/files/{fid}",
                        headers=headers,
                        params={"alt": "media"},
                        timeout=timeout,
                    )
                    if dl.status_code == 200:
                        preview = dl.text[:500].strip()
                lines.append(f"[{idx}] {fname} ({mtype}) — {link}")
                if preview:
                    lines.append(f"    Excerpt: {preview}")
                sources.append({"title": fname, "url": link})
            return "\n".join(lines), sources

        if tid == "notion":
            if not api_key:
                return f"{ag['name']} has no Notion secret set. Click 'Edit' on this agent to add its secret.", []
            payload = {"page_size": 6}
            if arg:
                payload["query"] = arg
            r = requests.post(
                "https://api.notion.com/v1/search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            if not results:
                return f"No Notion pages found{f' for {arg!r}' if arg else ''}.", []
            lines = [f"Notion pages{f' matching {arg!r}' if arg else ''}:"]
            sources = []
            for idx, page in enumerate(results, 1):
                url = page.get("url", "")
                props = page.get("properties", {})
                title = "Notion Page"
                for pval in props.values():
                    if isinstance(pval, dict) and pval.get("type") == "title":
                        t_arr = pval.get("title", [])
                        if t_arr:
                            title = "".join(t.get("plain_text", "") for t in t_arr)
                            break
                lines.append(f"[{idx}] {title} — {url}")
                if url:
                    sources.append({"title": title, "url": url})
            return "\n".join(lines), sources

        if tid == "weather":
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": arg or "Melbourne", "count": 1, "language": "en", "format": "json"},
                timeout=timeout,
            )
            geo.raise_for_status()
            places = geo.json().get("results", [])
            if not places:
                return f"Could not find location '{arg}'.", []
            place = places[0]
            lat, lon = place["latitude"], place["longitude"]
            label = f"{place.get('name')}, {place.get('country', '')}".strip(", ")
            wx = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m",
                },
                timeout=timeout,
            )
            wx.raise_for_status()
            cur = wx.json().get("current", {})
            summary = (
                f"Current weather in {label}: {cur.get('temperature_2m')}°C "
                f"(feels like {cur.get('apparent_temperature')}°C), "
                f"humidity {cur.get('relative_humidity_2m')}%, wind {cur.get('wind_speed_10m')} km/h."
            )
            return summary, [{"title": f"Open-Meteo: {label}", "url": "https://open-meteo.com/"}]

        if tid == "custom_api":
            base_url = custom_base_url.rstrip("/")
            if not base_url:
                return f"{ag['name']} has no Custom API Base URL configured.", []
            headers = {"Accept": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            if arg.startswith(("http://", "https://")):
                target = arg
            elif arg.startswith("/"):
                target = f"{base_url}{arg}"
            else:
                sep = "&" if "?" in base_url else "?"
                target = f"{base_url}{sep}q={quote(arg)}" if arg else base_url
            r = requests.get(target, headers=headers, timeout=timeout)
            r.raise_for_status()
            body = r.text[:2500]
            return f"Response from {custom_name} ({target}):\n{body}", [{"title": custom_name, "url": target}]

    except Exception as e:
        return f"API error from {tid}: {e}", []

    return f"Unknown tool '{tid}'.", []


class MosaicAgentEditorDialog(QDialog):
    """Create or edit a persistent Mosaic Agent with its own personality, mission, and private API key."""

    def __init__(self, parent=None, agent=None):
        super().__init__(parent)
        self.editing_agent = agent
        self.saved_agent = None
        self.deleted_agent_id = None
        self.palette = settings.get_palette(settings.load_settings())
        self.setStyleSheet(settings.build_stylesheet(self.palette))

        is_edit = agent is not None
        self.setWindowTitle("Edit Mosaic Agent" if is_edit else "Create New Mosaic Agent")
        self.resize(640, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        hdr = QLabel("Configure Mosaic Agent" if is_edit else "Create a Custom Mosaic Agent")
        hdr.setObjectName("sectionHeading")
        outer.addWidget(hdr)

        sub = QLabel(
            "Give this Mosaic Agent a distinct identity, personality, instructions, and its own isolated API key. "
            "Everything is saved locally in ~/.mosaic/agents.json."
        )
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("settingsPage")
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 6, 0)
        c_lay.setSpacing(12)

        # Card 1: Identity & Avatar
        id_card = QFrame()
        id_card.setObjectName("settingsCard")
        id_lay = QVBoxLayout(id_card)
        id_lay.setContentsMargins(14, 12, 14, 12)
        id_lay.setSpacing(8)

        id_title = QLabel("1. Agent Identity & Badge")
        id_title.setObjectName("settingTitle")
        id_lay.addWidget(id_title)

        name_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Agent Name (e.g., Repo Auditor, Research Scout)")
        self.name_edit.setText(agent["name"] if is_edit else "")
        self.name_edit.textChanged.connect(self._auto_fill_handle)

        self.handle_edit = QLineEdit()
        self.handle_edit.setPlaceholderText("@handle")
        self.handle_edit.setFixedWidth(190)
        self.handle_edit.setText(agent["handle"] if is_edit else "")

        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(self.handle_edit)
        id_lay.addLayout(name_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Color:"))
        self.color_box = QComboBox()
        for cname, hex_val in AGENT_AVATAR_COLORS:
            self.color_box.addItem(cname, hex_val)
        if is_edit:
            idx = self.color_box.findData(agent.get("avatar_color"))
            if idx >= 0:
                self.color_box.setCurrentIndex(idx)

        style_row.addWidget(self.color_box)
        style_row.addSpacing(12)
        style_row.addWidget(QLabel("Badge:"))
        self.badge_box = QComboBox()
        for bkey, blabel in AGENT_AVATAR_BADGES:
            self.badge_box.addItem(blabel, bkey)
        if is_edit:
            bidx = self.badge_box.findData(agent.get("avatar_badge"))
            if bidx >= 0:
                self.badge_box.setCurrentIndex(bidx)
        style_row.addWidget(self.badge_box)
        style_row.addStretch()
        id_lay.addLayout(style_row)
        c_lay.addWidget(id_card)

        # Card 2: Personality & Standing Instructions
        role_card = QFrame()
        role_card.setObjectName("settingsCard")
        role_lay = QVBoxLayout(role_card)
        role_lay.setContentsMargins(14, 12, 14, 12)
        role_lay.setSpacing(8)

        role_title = QLabel("2. Personality & What It Should Do")
        role_title.setObjectName("settingTitle")
        role_lay.addWidget(role_title)

        role_lay.addWidget(QLabel("Personality & Communication Style:"))
        self.personality_edit = QLineEdit()
        self.personality_edit.setPlaceholderText(
            "e.g., Sharp senior engineer with dry humor, concise bullet points, zero fluff"
        )
        self.personality_edit.setText(agent.get("personality", "") if is_edit else "")
        role_lay.addWidget(self.personality_edit)

        role_lay.addWidget(QLabel("Standing Instructions (Tell it what it is supposed to do):"))
        self.instructions_edit = QPlainTextEdit()
        self.instructions_edit.setFixedHeight(88)
        self.instructions_edit.setPlaceholderText(
            "Describe this agent's ongoing responsibilities, rules, and output format..."
        )
        self.instructions_edit.setPlainText(agent.get("instructions", "") if is_edit else "")
        role_lay.addWidget(self.instructions_edit)

        role_lay.addWidget(QLabel("One-Click Standing Mission (used when you click 'Run Mission'):"))
        self.mission_edit = QLineEdit()
        self.mission_edit.setPlaceholderText(
            "e.g., List my GitHub repositories and audit which ones need README updates"
        )
        self.mission_edit.setText(agent.get("standing_mission", "") if is_edit else "")
        role_lay.addWidget(self.mission_edit)

        bound_row = QHBoxLayout()
        bound_row.addWidget(QLabel("Execution Boundary:"))
        self.boundary_box = QComboBox()
        self.boundary_box.addItem("Autonomous (Run assigned tools automatically)", "auto")
        self.boundary_box.addItem("Ask Confirmation Before Running Tools", "confirm")
        if is_edit:
            bd_idx = self.boundary_box.findData(agent.get("boundary_mode", "auto"))
            if bd_idx >= 0:
                self.boundary_box.setCurrentIndex(bd_idx)
        bound_row.addWidget(self.boundary_box, 1)
        role_lay.addLayout(bound_row)
        c_lay.addWidget(role_card)

        # Card 3: Individual Isolated API Key
        api_card = QFrame()
        api_card.setObjectName("settingsCard")
        api_lay = QVBoxLayout(api_card)
        api_lay.setContentsMargins(14, 12, 14, 12)
        api_lay.setSpacing(8)

        api_hdr = QHBoxLayout()
        api_title = QLabel("3. Individual API Key (Exclusive to This Agent)")
        api_title.setObjectName("settingTitle")
        api_hdr.addWidget(api_title)
        api_hdr.addStretch()

        self.test_key_btn = QPushButton("Test Key")
        self.test_key_btn.setFixedHeight(28)
        self.test_key_btn.clicked.connect(self._test_key)
        api_hdr.addWidget(self.test_key_btn)
        api_lay.addLayout(api_hdr)

        self.service_box = QComboBox()
        for skey, sspec in SERVICE_SPECS.items():
            self.service_box.addItem(sspec["label"], skey)
        if is_edit:
            sidx = self.service_box.findData(agent.get("service_type", "none"))
            if sidx >= 0:
                self.service_box.setCurrentIndex(sidx)
        self.service_box.currentIndexChanged.connect(self._on_service_changed)
        api_lay.addWidget(self.service_box)

        self.custom_name_edit = QLineEdit()
        self.custom_name_edit.setPlaceholderText("Custom API Display Name (e.g., Internal Tracker)")
        self.custom_name_edit.setText(agent.get("custom_service_name", "My API") if is_edit else "My API")
        api_lay.addWidget(self.custom_name_edit)

        self.custom_url_edit = QLineEdit()
        self.custom_url_edit.setPlaceholderText("Custom API Base URL (e.g., http://localhost:8000/api)")
        self.custom_url_edit.setText(agent.get("custom_base_url", "") if is_edit else "")
        api_lay.addWidget(self.custom_url_edit)

        key_row = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setText(agent.get("api_key", "") if is_edit else "")
        key_row.addWidget(self.api_key_edit, 1)

        self.reveal_btn = QPushButton("Show")
        self.reveal_btn.setCheckable(True)
        self.reveal_btn.setFixedWidth(64)
        self.reveal_btn.toggled.connect(
            lambda shown: (
                self.api_key_edit.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password),
                self.reveal_btn.setText("Hide" if shown else "Show"),
            )
        )
        key_row.addWidget(self.reveal_btn)
        api_lay.addLayout(key_row)

        self.isolation_cb = QCheckBox(
            "Strictly isolate this API key to ONLY this Mosaic Agent (never shared with other agents)"
        )
        self.isolation_cb.setChecked(bool(agent.get("strict_isolation", True)) if is_edit else True)
        api_lay.addWidget(self.isolation_cb)

        self.key_status_lbl = QLabel("")
        self.key_status_lbl.setWordWrap(True)
        self.key_status_lbl.setVisible(False)
        api_lay.addWidget(self.key_status_lbl)

        c_lay.addWidget(api_card)

        # Card 4: Agent Persistent Memory Notes (when editing an existing agent)
        if is_edit:
            notes_card = QFrame()
            notes_card.setObjectName("settingsCard")
            notes_lay = QVBoxLayout(notes_card)
            notes_lay.setContentsMargins(14, 12, 14, 12)
            notes_lay.setSpacing(6)

            nhdr = QHBoxLayout()
            ntitle = QLabel(f"4. Saved Agent Memory Notes ({len(agent.get('notes', []))})")
            ntitle.setObjectName("settingTitle")
            nhdr.addWidget(ntitle)
            nhdr.addStretch()
            clear_notes_btn = QPushButton("Clear Notes")
            clear_notes_btn.setFixedHeight(26)
            clear_notes_btn.clicked.connect(self._clear_notes)
            nhdr.addWidget(clear_notes_btn)
            notes_lay.addLayout(nhdr)

            self.notes_list = QListWidget()
            self.notes_list.setFixedHeight(90)
            for n in agent.get("notes", []):
                self.notes_list.addItem(n)
            notes_lay.addWidget(self.notes_list)
            c_lay.addWidget(notes_card)

        c_lay.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        footer = QHBoxLayout()
        if is_edit and len(list_agents()) > 1:
            del_btn = QPushButton("Delete Agent")
            del_btn.setStyleSheet(f"color: {self.palette['red']};")
            del_btn.clicked.connect(self._delete_this_agent)
            footer.addWidget(del_btn)

        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Mosaic Agent")
        save_btn.setObjectName("send")
        save_btn.clicked.connect(self._save)
        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)
        outer.addLayout(footer)

        self._handle_manually_edited = bool(is_edit)
        self.handle_edit.textEdited.connect(lambda: setattr(self, "_handle_manually_edited", True))
        self._on_service_changed()

    def _auto_fill_handle(self, text):
        if not self._handle_manually_edited:
            self.handle_edit.setText(_make_handle(text))

    def _on_service_changed(self):
        stype = self.service_box.currentData()
        spec = SERVICE_SPECS.get(stype, SERVICE_SPECS["none"])
        is_custom = stype == "custom_api"
        self.custom_name_edit.setVisible(is_custom)
        self.custom_url_edit.setVisible(is_custom)
        self.api_key_edit.setVisible(stype not in ("none", "weather"))
        self.reveal_btn.setVisible(stype not in ("none", "weather"))
        self.api_key_edit.setPlaceholderText(spec["placeholder"])

    def _test_key(self):
        stype = self.service_box.currentData()
        self.key_status_lbl.setVisible(True)
        self.key_status_lbl.setStyleSheet(f"color: {self.palette['text_muted']};")
        self.key_status_lbl.setText("Verifying key for this Mosaic Agent...")
        QApplication.processEvents()
        ok, msg = test_agent_service(
            stype,
            api_key=self.api_key_edit.text(),
            base_url=self.custom_url_edit.text(),
        )
        col = self.palette["green"] if ok else self.palette["red"]
        self.key_status_lbl.setStyleSheet(f"color: {col}; font-weight: bold; font-size: 12px;")
        self.key_status_lbl.setText(msg)

    def _clear_notes(self):
        if hasattr(self, "notes_list"):
            self.notes_list.clear()

    def _delete_this_agent(self):
        if self.editing_agent is None:
            return
        ans = QMessageBox.question(
            self,
            "Delete Mosaic Agent",
            f"Delete '{self.editing_agent['name']}' and its stored API key?",
        )
        if ans == QMessageBox.Yes:
            self.deleted_agent_id = self.editing_agent["id"]
            delete_agent(self.deleted_agent_id)
            self.accept()

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Give your Mosaic Agent a name first.")
            self.name_edit.setFocus()
            return

        payload = {
            "name": name,
            "handle": self.handle_edit.text().strip() or _make_handle(name),
            "avatar_color": self.color_box.currentData(),
            "avatar_badge": self.badge_box.currentData(),
            "personality": self.personality_edit.text().strip(),
            "instructions": self.instructions_edit.toPlainText().strip(),
            "standing_mission": self.mission_edit.text().strip(),
            "boundary_mode": self.boundary_box.currentData(),
            "service_type": self.service_box.currentData(),
            "api_key": _clean_token(self.api_key_edit.text()),
            "custom_service_name": self.custom_name_edit.text().strip() or "My API",
            "custom_base_url": self.custom_url_edit.text().strip(),
            "strict_isolation": bool(self.isolation_cb.isChecked()),
        }

        if self.editing_agent is not None:
            if hasattr(self, "notes_list"):
                payload["notes"] = [
                    self.notes_list.item(i).text() for i in range(self.notes_list.count())
                ]
            self.saved_agent = update_agent(self.editing_agent["id"], payload)
        else:
            self.saved_agent = create_agent(payload)

        self.accept()


def capture_screen_base64(max_width=1280):
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return "", 1920, 1080, QPixmap()
    full_pm = screen.grabWindow(0)
    orig_w = max(1, full_pm.width())
    orig_h = max(1, full_pm.height())

    scaled_pm = full_pm
    if orig_w > max_width:
        scaled_pm = full_pm.scaledToWidth(max_width, Qt.SmoothTransformation)

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    scaled_pm.save(buf, "JPEG", 82)
    b64 = bytes(ba.toBase64()).decode("ascii")
    return b64, orig_w, orig_h, full_pm


def get_cursor_xy():
    pos = QCursor.pos()
    return int(pos.x()), int(pos.y())


def build_cowork_system_prompt(base_prompt, screen_w, screen_h, allow_cursor=True):
    cx, cy = get_cursor_xy()
    if allow_cursor:
        cursor_block = (
            "You CAN control the user's mouse cursor and keyboard when needed by emitting ONE action per step on its own line:\n"
            "[[ACTION: move | x, y]]\n"
            "[[ACTION: click | x, y]]\n"
            "[[ACTION: double_click | x, y]]\n"
            "[[ACTION: right_click | x, y]]\n"
            "[[ACTION: type | text to type]]\n"
            "[[ACTION: press | enter]]  (supports: enter, tab, esc, backspace, space, up, down, left, right)\n"
            "[[ACTION: scroll | -300]]  (negative = scroll down, positive = scroll up)\n"
            "[[ACTION: wait | 1.0]]\n\n"
            f"Use absolute screen pixel coordinates within width={screen_w}, height={screen_h}. "
            "After an action executes, you will receive an updated screenshot to verify the result. "
            "When the task is complete (or if the user just asked a question about the screen), explain clearly without emitting an action."
        )
    else:
        cursor_block = (
            "Cursor control is currently turned OFF by the user (Screen Vision only). "
            "Analyze what is visible on the user's screen and guide them clearly without emitting [[ACTION: ...]] tags."
        )

    return (
        f"{base_prompt}\n\n"
        f"[COWORK MODE ACTIVE — Screen Resolution: {screen_w}x{screen_h} | Current Cursor: ({cx}, {cy})]\n"
        "You have been provided with a live screenshot of the user's screen.\n"
        f"{cursor_block}"
    )


def _check_failsafe():
    x, y = get_cursor_xy()
    if x <= 1 and y <= 1:
        raise RuntimeError("Cowork fail-safe triggered (cursor moved to top-left corner).")


def _win32_move_and_click(x, y, button=None, double=False):
    user32 = ctypes.windll.user32
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.06)
    if button == "left":
        clicks = 2 if double else 1
        for _ in range(clicks):
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.03)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            if double:
                time.sleep(0.06)
    elif button == "right":
        user32.mouse_event(0x0008, 0, 0, 0, 0)
        time.sleep(0.03)
        user32.mouse_event(0x0010, 0, 0, 0, 0)


def _win32_scroll(delta):
    ctypes.windll.user32.mouse_event(0x0800, 0, 0, int(delta), 0)


def _win32_type_text(text):
    user32 = ctypes.windll.user32
    for ch in text:
        vk_scan = user32.VkKeyScanW(ord(ch))
        if vk_scan == -1:
            continue
        vk = vk_scan & 0xFF
        shift = bool((vk_scan >> 8) & 1)
        if shift:
            user32.keybd_event(0x10, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.015)
        user32.keybd_event(vk, 0, 2, 0)
        if shift:
            user32.keybd_event(0x10, 0, 2, 0)
        time.sleep(0.015)


def _win32_press_key(key_name):
    vk_map = {
        "enter": 0x0D,
        "return": 0x0D,
        "tab": 0x09,
        "esc": 0x1B,
        "escape": 0x1B,
        "backspace": 0x08,
        "space": 0x20,
        "left": 0x25,
        "up": 0x26,
        "right": 0x27,
        "down": 0x28,
        "delete": 0x2E,
    }
    vk = vk_map.get(key_name.strip().lower())
    if vk is None:
        return False
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, 2, 0)
    return True


def _parse_xy(arg_str, screen_w, screen_h):
    nums = re.findall(r"-?\d+(?:\.\d+)?", arg_str or "")
    if len(nums) < 2:
        raise ValueError(f"Invalid coordinates: '{arg_str}'")
    x = max(2, min(screen_w - 3, int(round(float(nums[0])))))
    y = max(2, min(screen_h - 3, int(round(float(nums[1])))))
    return x, y


def execute_cowork_action(action_type, arg_str, screen_w, screen_h):
    _check_failsafe()
    act = (action_type or "").strip().lower()
    arg = (arg_str or "").strip()

    if act == "wait":
        secs = max(0.1, min(5.0, float(arg or 1.0)))
        time.sleep(secs)
        return f"Waited {secs:.1f}s"

    if act in ("move", "click", "double_click", "right_click"):
        x, y = _parse_xy(arg, screen_w, screen_h)
        if sys.platform == "win32":
            btn = None
            if act in ("click", "double_click"):
                btn = "left"
            elif act == "right_click":
                btn = "right"
            _win32_move_and_click(x, y, button=btn, double=(act == "double_click"))
        else:
            try:
                import pyautogui  # type: ignore

                pyautogui.moveTo(x, y, duration=0.12)
                if act == "click":
                    pyautogui.click(x, y)
                elif act == "double_click":
                    pyautogui.doubleClick(x, y)
                elif act == "right_click":
                    pyautogui.rightClick(x, y)
            except ImportError:
                if shutil.which("xdotool"):
                    subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=False)
                    if act == "click":
                        subprocess.run(["xdotool", "click", "1"], check=False)
                    elif act == "double_click":
                        subprocess.run(["xdotool", "click", "--repeat", "2", "1"], check=False)
                    elif act == "right_click":
                        subprocess.run(["xdotool", "click", "3"], check=False)
                else:
                    raise RuntimeError("Install 'pyautogui' or 'xdotool' for cursor control on this OS.")

        labels = {
            "move": f"Moved cursor to ({x}, {y})",
            "click": f"Left-clicked at ({x}, {y})",
            "double_click": f"Double-clicked at ({x}, {y})",
            "right_click": f"Right-clicked at ({x}, {y})",
        }
        return labels[act]

    if act == "scroll":
        delta = int(round(float(arg or -300)))
        if sys.platform == "win32":
            _win32_scroll(delta)
        else:
            try:
                import pyautogui  # type: ignore

                pyautogui.scroll(delta)
            except ImportError:
                if shutil.which("xdotool"):
                    btn = "5" if delta < 0 else "4"
                    subprocess.run(["xdotool", "click", "--repeat", "3", btn], check=False)
        return f"Scrolled ({delta})"

    if act == "type":
        if sys.platform == "win32":
            _win32_type_text(arg)
        else:
            try:
                import pyautogui  # type: ignore

                pyautogui.write(arg, interval=0.02)
            except ImportError:
                if shutil.which("xdotool"):
                    subprocess.run(["xdotool", "type", "--delay", "20", arg], check=False)
        return f'Typed "{arg[:40]}"'

    if act == "press":
        if sys.platform == "win32":
            if not _win32_press_key(arg):
                return f"Unsupported key '{arg}'"
        else:
            try:
                import pyautogui  # type: ignore

                pyautogui.press(arg.lower())
            except ImportError:
                if shutil.which("xdotool"):
                    subprocess.run(["xdotool", "key", arg], check=False)
        return f"Pressed key [{arg}]"

    return f"Ignored unknown action '{act}'"