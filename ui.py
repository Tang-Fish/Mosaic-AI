from datetime import datetime
import base64
import html
import json
import math
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import api
from icons import make_icon, make_pixmap
import memory
import modes
import settings
import storage


EXTRA_API_SERVICES = api.EXTRA_API_SERVICES
KEYLESS_SERVICES = api.KEYLESS_SERVICES
EXTRA_TOOL_PREFIXES = api.EXTRA_TOOL_PREFIXES
_register_extra_api_services = api.register_extra_api_services
_extract_agent_base_url = api.extract_agent_base_url
_augment_custom_api_system_prompt = api.augment_custom_api_system_prompt
_infer_custom_api_fallback = api.infer_custom_api_fallback
_execute_custom_api_request = api.execute_custom_api_request


AGENT_ICON_SHAPES = [
    ("hexagon", "Hexagon"),
    ("triangle", "Triangle"),
    ("square", "Square"),
    ("diamond", "Diamond"),
    ("circle", "Circle"),
    ("pentagon", "Pentagon"),
    ("octagon", "Octagon"),
    ("star", "Star"),
]

AGENT_ICON_COLORS = [
    ("#4f8cff", "Cobalt Blue"),
    ("#10b981", "Emerald"),
    ("#a855f7", "Violet"),
    ("#f59e0b", "Amber Gold"),
    ("#ef4444", "Crimson"),
    ("#06b6d4", "Cyan"),
    ("#ec4899", "Rose Pink"),
    ("#f97316", "Sunset Orange"),
    ("#84cc16", "Lime"),
    ("#94a3b8", "Titanium Silver"),
]

_VALID_SHAPE_KEYS = {k for k, _ in AGENT_ICON_SHAPES}


def _resolve_agent_shape(agent):
    """Return a normalized geometric shape key for an agent profile."""
    if not isinstance(agent, dict):
        return "hexagon"
    raw_badge = (agent.get("avatar_badge") or "").strip().lower()
    if raw_badge in _VALID_SHAPE_KEYS:
        return raw_badge

    stype = (agent.get("service_type") or "none").strip().lower()
    service_defaults = {
        "free_news": "circle",
        "gmail": "diamond",
        "google_calendar": "square",
        "slack": "hexagon",
        "discord": "octagon",
        "trello": "square",
        "linear": "triangle",
        "spotify": "circle",
        "reddit": "pentagon",
        "wikipedia": "hexagon",
        "arxiv": "star",
        "crypto": "diamond",
        "currency": "octagon",
        "github": "square",
        "youtube": "triangle",
        "google_drive": "pentagon",
        "notion": "pentagon",
        "weather": "diamond",
        "custom": "octagon",
    }
    if stype in service_defaults:
        return service_defaults[stype]

    seed_str = f"{agent.get('id', '')}:{agent.get('name', '')}"
    ordered = [k for k, _ in AGENT_ICON_SHAPES]
    return ordered[sum(ord(ch) for ch in seed_str) % len(ordered)]


def _rounded_polygon_path(points, radius):
    """Build a QPainterPath for a closed polygon with smooth rounded corners."""
    path = QPainterPath()
    n = len(points)
    if n < 3:
        return path

    anchors = []
    for i in range(n):
        prev_pt = points[(i - 1) % n]
        curr_pt = points[i]
        next_pt = points[(i + 1) % n]

        v1x, v1y = prev_pt.x() - curr_pt.x(), prev_pt.y() - curr_pt.y()
        v2x, v2y = next_pt.x() - curr_pt.x(), next_pt.y() - curr_pt.y()
        d1 = math.hypot(v1x, v1y) or 1.0
        d2 = math.hypot(v2x, v2y) or 1.0
        r = min(radius, d1 * 0.34, d2 * 0.34)

        entry_pt = QPointF(curr_pt.x() + v1x * (r / d1), curr_pt.y() + v1y * (r / d1))
        exit_pt = QPointF(curr_pt.x() + v2x * (r / d2), curr_pt.y() + v2y * (r / d2))
        anchors.append((entry_pt, curr_pt, exit_pt))

    path.moveTo(anchors[0][2])
    for i in range(1, n + 1):
        entry_pt, corner_pt, exit_pt = anchors[i % n]
        path.lineTo(entry_pt)
        path.quadTo(corner_pt, exit_pt)
    path.closeSubpath()
    return path


def _build_shape_path(shape_key, cx, cy, r):
    """Create a centered geometric QPainterPath of radius r for the given shape."""
    corner_r = max(1.4, r * 0.16)

    if shape_key == "circle":
        p = QPainterPath()
        p.addEllipse(QPointF(cx, cy), r * 0.92, r * 0.92)
        return p

    if shape_key == "square":
        side = r * 1.62
        p = QPainterPath()
        p.addRoundedRect(QRectF(cx - side * 0.5, cy - side * 0.5, side, side), r * 0.28, r * 0.28)
        return p

    if shape_key == "triangle":
        pts = [
            QPointF(cx, cy - r * 0.96),
            QPointF(cx + r * 0.90, cy + r * 0.72),
            QPointF(cx - r * 0.90, cy + r * 0.72),
        ]
        return _rounded_polygon_path(pts, corner_r * 1.15)

    if shape_key == "diamond":
        pts = [
            QPointF(cx, cy - r * 0.98),
            QPointF(cx + r * 0.84, cy),
            QPointF(cx, cy + r * 0.98),
            QPointF(cx - r * 0.84, cy),
        ]
        return _rounded_polygon_path(pts, corner_r)

    if shape_key == "pentagon":
        pts = []
        for i in range(5):
            ang = math.radians(-90 + i * 72)
            pts.append(QPointF(cx + r * 0.95 * math.cos(ang), cy + r * 0.95 * math.sin(ang)))
        return _rounded_polygon_path(pts, corner_r)

    if shape_key == "octagon":
        pts = []
        for i in range(8):
            ang = math.radians(-90 + 22.5 + i * 45)
            pts.append(QPointF(cx + r * 0.95 * math.cos(ang), cy + r * 0.95 * math.sin(ang)))
        return _rounded_polygon_path(pts, corner_r * 0.85)

    if shape_key == "star":
        pts = []
        outer_r = r * 0.98
        inner_r = r * 0.42
        for i in range(8):
            ang = math.radians(-90 + i * 45)
            rad = outer_r if i % 2 == 0 else inner_r
            pts.append(QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        return _rounded_polygon_path(pts, corner_r * 0.55)

    # Default: "hexagon" (pointy-top precision hexagon)
    pts = []
    for i in range(6):
        ang = math.radians(-90 + i * 60)
        pts.append(QPointF(cx + r * 0.96 * math.cos(ang), cy + r * 0.96 * math.sin(ang)))
    return _rounded_polygon_path(pts, corner_r)


def _make_custom_agent_icon(agent, size=30, is_active=False):
    """Render a crisp, high-DPI geometric shape icon with custom color and glass bevels."""
    dpr = 3.0
    px_size = int(size * dpr)
    pm = QPixmap(px_size, px_size)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    s = float(size)
    if isinstance(agent, dict):
        base_hex = (agent.get("avatar_color") or "#4f8cff").strip()
        shape_key = _resolve_agent_shape(agent)
    else:
        base_hex = "#4f8cff"
        shape_key = str(agent or "hexagon").strip().lower()
        if shape_key not in _VALID_SHAPE_KEYS:
            shape_key = "hexagon"

    base_col = QColor(base_hex)
    if not base_col.isValid():
        base_col = QColor("#4f8cff")

    # 1. Dark frosted-obsidian tile backdrop so any chosen shape color pops cleanly
    pad = 1.2
    tile_rect = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
    tile_radius = s * 0.27

    tile_grad = QLinearGradient(0, 0, s, s)
    tile_grad.setColorAt(0.0, QColor("#182032"))
    tile_grad.setColorAt(1.0, QColor("#0d111b"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(tile_grad))
    painter.drawRoundedRect(tile_rect, tile_radius, tile_radius)

    # Subtle ambient color wash inside the tile
    glow_grad = QRadialGradient(s * 0.5, s * 0.5, s * 0.62)
    glow_c1 = QColor(base_col)
    glow_c1.setAlpha(72 if is_active else 46)
    glow_c2 = QColor(base_col)
    glow_c2.setAlpha(0)
    glow_grad.setColorAt(0.0, glow_c1)
    glow_grad.setColorAt(1.0, glow_c2)
    painter.setBrush(QBrush(glow_grad))
    painter.drawRoundedRect(tile_rect, tile_radius, tile_radius)

    # Tile border rim (highlighted in base_col when active)
    rim_col = QColor(base_col)
    rim_col.setAlpha(235 if is_active else 115)
    painter.setPen(QPen(rim_col, 1.35 if is_active else 0.95))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(tile_rect.adjusted(0.4, 0.4, -0.4, -0.4), tile_radius, tile_radius)

    # 2. Primary sculpted geometric shape
    cx = s * 0.50
    cy = s * 0.50 + (s * 0.025 if shape_key == "triangle" else 0.0)
    shape_r = s * 0.31

    outer_path = _build_shape_path(shape_key, cx, cy, shape_r)
    shape_grad = QLinearGradient(cx - shape_r, cy - shape_r, cx + shape_r, cy + shape_r)
    shape_grad.setColorAt(0.0, base_col.lighter(135))
    shape_grad.setColorAt(0.55, base_col)
    shape_grad.setColorAt(1.0, base_col.darker(140))

    painter.setPen(QPen(QColor(255, 255, 255, 165), max(0.85, s * 0.03)))
    painter.setBrush(QBrush(shape_grad))
    painter.drawPath(outer_path)

    # 3. Inner faceted geometric ring + luminous center core
    inner_path = _build_shape_path(shape_key, cx, cy, shape_r * 0.52)
    painter.setPen(QPen(QColor(255, 255, 255, 110), max(0.75, s * 0.024)))
    painter.setBrush(QColor(255, 255, 255, 26))
    painter.drawPath(inner_path)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 215))
    core_r = max(1.0, s * 0.042)
    painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

    painter.end()
    return QIcon(pm)


def _make_color_swatch_icon(hex_color, size=14):
    """Render a circular color swatch icon for menus and pickers."""
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    col = QColor(hex_color)
    if not col.isValid():
        col = QColor("#4f8cff")
    painter.setPen(QPen(QColor(255, 255, 255, 160), 1.0))
    painter.setBrush(QBrush(col))
    painter.drawEllipse(QRectF(1.5, 1.5, size - 3.0, size - 3.0))
    painter.end()
    return QIcon(pm)


def _save_agent_appearance(agent_id, shape=None, color=None):
    """Persist updated avatar_badge (shape) and/or avatar_color on an agent."""
    target = modes.get_agent(agent_id)
    if not isinstance(target, dict):
        return None
    updated = dict(target)
    if shape:
        updated["avatar_badge"] = shape
    if color:
        updated["avatar_color"] = color

    updater = getattr(modes, "update_agent", None) or getattr(modes, "save_agent", None)
    if callable(updater):
        try:
            updater(updated)
            return updated
        except TypeError:
            try:
                updater(agent_id, updated)
                return updated
            except Exception:
                pass
        except Exception:
            pass

    # Fallback: update via modes list/save helpers or ~/.mosaic/agents.json
    all_agents = [dict(a) for a in modes.list_agents()]
    replaced = False
    for idx, ag in enumerate(all_agents):
        if ag.get("id") == agent_id:
            all_agents[idx] = updated
            replaced = True
            break
    if not replaced:
        all_agents.append(updated)

    bulk_saver = getattr(modes, "save_agents", None)
    if callable(bulk_saver):
        try:
            bulk_saver(all_agents)
            return updated
        except Exception:
            pass

    agents_file = getattr(modes, "AGENTS_FILE", Path.home() / ".mosaic" / "agents.json")
    try:
        Path(agents_file).parent.mkdir(parents=True, exist_ok=True)
        Path(agents_file).write_text(
            json.dumps(all_agents, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
    return updated


_register_extra_api_services()

MODE_STARTER_PROMPTS = {
    "chat": [
        ("bulb", "accent", "Explain a concept", "Explain how neural networks learn in simple terms with a real-world analogy."),
        ("code", "green", "Write Python code", "Write a clean Python script that organizes files in a folder by file extension."),
        ("bug", "red", "Debug my code", "Help me find bugs and optimize performance in a piece of code I'll paste next."),
        ("sparkle", "purple", "Brainstorm ideas", "Give me 5 creative project ideas I can build over a weekend with Python."),
    ],
    "cowork": [
        ("search", "accent", "Describe my screen", "Look at my current screen and summarize what windows or apps are open."),
        ("bulb", "green", "Help with current app", "Examine what is currently visible on my screen and help me with the next step."),
        ("code", "purple", "Review visible code/error", "Read the code or error message visible on my screen and tell me how to fix it."),
        ("sparkle", "yellow", "Click an item on screen", "Look at my screen, find the search bar, and click on it."),
    ],
}

_KW_RE = re.compile(
    r"\b(def|class|return|if|elif|else|for|while|try|except|finally|with|as|import|from|"
    r"pass|break|continue|lambda|yield|async|await|True|False|None|const|let|var|function|"
    r"public|private|static|void|int|float|str|bool|struct|enum|match|case)\b"
)
_STR_RE = re.compile(r"(&quot;.*?&quot;|&#x27;.*?&#x27;)")
_NUM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")
_TOOL_CALL_RE = re.compile(r"\[\[CALL_API:\s*([a-zA-Z0-9_-]+)\s*\|\s*(.*?)\s*\]\]", re.DOTALL)
_COWORK_ACT_RE = re.compile(r"\[\[ACTION:\s*([a-zA-Z0-9_-]+)\s*\|\s*(.+?)\s*\]\]")
_THINK_BLOCK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _dedupe_sources(sources):
    cleaned = []
    seen = set()
    for src in sources or []:
        if not isinstance(src, dict):
            continue
        url = (src.get("url") or "").strip()
        if not url.startswith(("http://", "https://", "file://")):
            continue
        norm_url = url.rstrip("/")
        if norm_url in seen:
            continue
        seen.add(norm_url)
        title = (src.get("title") or url).strip()
        cleaned.append({"title": title, "url": url})
    return cleaned


def _extract_agent_base_url(agent_profile):
    if not isinstance(agent_profile, dict):
        return ""
    for key in ("base_url", "custom_base_url", "api_base_url", "endpoint_url", "url"):
        val = (agent_profile.get(key) or "").strip()
        if val:
            return val.rstrip("/")
    return ""


def _augment_custom_api_system_prompt(system_prompt, agent_profile):
    if not isinstance(agent_profile, dict):
        return system_prompt
    service_type = (agent_profile.get("service_type") or "").strip().lower()

    if service_type in EXTRA_API_SERVICES:
        meta = EXTRA_API_SERVICES[service_type]
        tool_lines = "\n".join(
            f"• [[CALL_API: {tid} | <argument>]] — {desc}"
            for tid, desc in meta["tools"]
        )
        guidance = (
            f"\n\n[{meta['name'].upper()} API INSTRUCTIONS]\n"
            f"{meta['description']}\n"
            "When the user's request requires data or actions from this service, output ONLY a single tool call tag:\n"
            f"{tool_lines}"
        )
        return system_prompt + guidance

    base_url = _extract_agent_base_url(agent_profile)
    if service_type != "custom" and not base_url:
        return system_prompt

    if "newsapi.org" in base_url.lower():
        guidance = (
            "\n\n[CUSTOM REST API — NEWSAPI INSTRUCTIONS]\n"
            f"Base URL: {base_url}\n"
            "Authentication is injected automatically via request headers — NEVER put apiKey or YOUR_API_KEY in the URL.\n"
            "To fetch news, output ONLY a tool call tag using one of these endpoints:\n"
            "• [[CALL_API: custom_get | /top-headlines?country=us&pageSize=8]] (optional: &category=technology|business|science|health|sports|entertainment or &q=keyword)\n"
            "• [[CALL_API: custom_get | /everything?q=your+search+terms&sortBy=publishedAt&language=en&pageSize=8]]\n"
            "Note: /top-headlines requires at least one of country, category, sources, or q; /everything requires q."
        )
    else:
        guidance = (
            "\n\n[CUSTOM REST API INSTRUCTIONS]\n"
            f"Base URL: {base_url or '(configured in settings)'}\n"
            "Authentication headers are attached automatically — do not embed placeholder API keys in URLs.\n"
            "Invoke endpoints with [[CALL_API: custom_get | /relative/endpoint?param=value]]."
        )
    return system_prompt + guidance


def _infer_custom_api_fallback(user_query, agent_profile):
    if not isinstance(agent_profile, dict):
        return None
    service_type = (agent_profile.get("service_type") or "").strip().lower()
    base_url = _extract_agent_base_url(agent_profile)
    if service_type not in ("custom", *EXTRA_API_SERVICES.keys()) and not base_url:
        return None

    q = (user_query or "").strip()
    if not q:
        return None
    ql = q.lower()

    if service_type == "free_news":
        topic = re.sub(
            r"^(?:can you\s+|please\s+)?(?:get|find|show|give|fetch|search|tell)\s+(?:me\s+)?(?:the\s+)?(?:latest\s+|top\s+|recent\s+)?(?:news|headlines|articles)(?:\s+(?:about|on|for|regarding))?\s*",
            "",
            q,
            flags=re.IGNORECASE,
        ).strip(" ?!.")
        if topic and topic.lower() not in ("today", "now", "news", "headlines", "top"):
            return ("free_news", topic[:120])
        return ("free_news", "top")

    if service_type == "gmail":
        if "label" in ql or "folder" in ql:
            return ("gmail_labels", "")
        if "unread" in ql:
            return ("gmail_search", "is:unread")
        m = re.search(r"(?:search|find|from|about|for)\s+(.+)$", q, flags=re.IGNORECASE)
        return ("gmail_search", m.group(1).strip(" ?!.")) if m else ("gmail_search", "in:inbox")

    if service_type == "google_calendar":
        if any(w in ql for w in ("schedule", "add", "create", "book", "remind")):
            return ("gcal_quick_add", q)
        return ("gcal_upcoming", "")

    if service_type == "slack":
        return ("slack_channels", "")

    if service_type == "discord":
        return ("discord_guilds", "")

    if service_type == "trello":
        return ("trello_boards", "")

    if service_type == "linear":
        if "team" in ql:
            return ("linear_teams", "")
        return ("linear_issues", "")

    if service_type == "spotify":
        if any(w in ql for w in ("playing", "current", "listening")):
            return ("spotify_now_playing", "")
        if "top" in ql:
            return ("spotify_top", "")
        topic = re.sub(r"^(?:search|find|play|look up)\s+(?:spotify\s+for\s+)?", "", q, flags=re.IGNORECASE).strip(" ?!.")
        return ("spotify_search", topic or "top hits")

    if service_type == "reddit":
        sub_m = re.search(r"\br/([a-zA-Z0-9_]+)", q)
        if sub_m:
            return ("reddit_hot", sub_m.group(1))
        topic = re.sub(r"^(?:search|find|show|get)\s+(?:reddit\s+(?:for|about)\s+)?", "", q, flags=re.IGNORECASE).strip(" ?!.")
        return ("reddit_search", topic or "technology")

    if service_type == "wikipedia":
        topic = re.sub(
            r"^(?:search\s+wikipedia\s+for|wikipedia|wiki|who\s+is|what\s+is|tell\s+me\s+about)\s+",
            "",
            q,
            flags=re.IGNORECASE,
        ).strip(" ?!.")
        return ("wiki_search", topic or q[:100])

    if service_type == "arxiv":
        topic = re.sub(
            r"^(?:search\s+arxiv\s+for|find\s+papers\s+on|arxiv|papers\s+about)\s+",
            "",
            q,
            flags=re.IGNORECASE,
        ).strip(" ?!.")
        return ("arxiv_search", topic or q[:100])

    if service_type == "crypto":
        if "trending" in ql:
            return ("crypto_trending", "")
        coins = []
        for sym, cid in (
            ("btc", "bitcoin"), ("bitcoin", "bitcoin"),
            ("eth", "ethereum"), ("ethereum", "ethereum"),
            ("sol", "solana"), ("solana", "solana"),
            ("doge", "dogecoin"), ("dogecoin", "dogecoin"),
            ("xrp", "ripple"), ("ada", "cardano"),
        ):
            if re.search(rf"\b{sym}\b", ql) and cid not in coins:
                coins.append(cid)
        return ("crypto_price", ",".join(coins) if coins else "bitcoin,ethereum,solana")

    if service_type == "currency":
        return ("fx_convert", q[:100])

    if "newsapi.org" in base_url.lower():
        topic = re.sub(
            r"^(?:can you\s+|please\s+)?(?:get|find|show|give|fetch|search|tell)\s+(?:me\s+)?(?:the\s+)?(?:latest\s+|top\s+|recent\s+)?(?:news|headlines|articles)(?:\s+(?:about|on|for|regarding))?\s*",
            "",
            q,
            flags=re.IGNORECASE,
        ).strip(" ?!.")
        if topic and topic.lower() not in ("today", "now", "news", "headlines"):
            encoded = urllib.parse.quote_plus(topic[:120])
            return ("custom_get", f"/everything?q={encoded}&sortBy=publishedAt&language=en&pageSize=8")
        return ("custom_get", "/top-headlines?country=us&pageSize=8")

    return None


def _execute_free_news_request(raw_arg, user_query=""):
    topic = (raw_arg or "").strip()
    if not topic or topic.lower() in ("top", "headlines", "latest", "news"):
        topic = ""
    if not topic and user_query:
        cleaned_q = re.sub(
            r"^(?:can you\s+|please\s+)?(?:get|find|show|give|fetch|search|tell)\s+(?:me\s+)?(?:the\s+)?(?:latest\s+|top\s+|recent\s+)?(?:news|headlines|articles)(?:\s+(?:about|on|for|regarding))?\s*",
            "",
            user_query.strip(),
            flags=re.IGNORECASE,
        ).strip(" ?!.")
        if cleaned_q and cleaned_q.lower() not in ("today", "now", "news", "headlines", "top"):
            topic = cleaned_q[:120]

    headers = {"User-Agent": "Mosaic-Local-AI-Studio/1.0"}
    if topic:
        encoded = urllib.parse.quote_plus(topic)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        heading = f"Live News for '{topic}':"
    else:
        rss_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        heading = "Top Live News Headlines:"

    try:
        req = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)
        items = root.findall(".//item")
        if items:
            lines = [heading]
            sources = []
            for idx, item in enumerate(items[:8], start=1):
                title = (item.findtext("title") or "Untitled").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()[:16]
                src = (item.findtext("source") or "News").strip()
                lines.append(f"{idx}. {title} ({src}{', ' + pub if pub else ''})")
                if link:
                    lines.append(f"   URL: {link}")
                    sources.append({"title": title, "url": link})
            return ("\n".join(lines), sources)
    except Exception:
        pass

    # Fallback to keyless Hacker News Algolia API
    hn_query = urllib.parse.quote_plus(topic or "technology")
    hn_url = f"https://hn.algolia.com/api/v1/search?query={hn_query}&tags=story&hitsPerPage=8"
    try:
        req = urllib.request.Request(hn_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        hits = data.get("hits") or []
        if not hits:
            return ("No recent news stories matched that topic.", [])
        lines = [heading]
        sources = []
        for idx, hit in enumerate(hits[:8], start=1):
            title = (hit.get("title") or "Untitled").strip()
            url = (hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}").strip()
            date_str = (hit.get("created_at") or "")[:10]
            lines.append(f"{idx}. {title} ({date_str})")
            lines.append(f"   URL: {url}")
            sources.append({"title": title, "url": url})
        return ("\n".join(lines), sources)
    except Exception as e:
        return (f"Free News lookup error: {e}", [])


def _http_json_request(url, headers=None, data_bytes=None, method="GET", timeout=25):
    req_headers = {"User-Agent": "Mosaic-Local-AI-Studio/1.0", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def _extract_gmail_body(payload):
    if not isinstance(payload, dict):
        return ""
    body_data = ((payload.get("body") or {}).get("data") or "").strip()
    if body_data:
        try:
            padded = body_data + "=" * (-len(body_data) % 4)
            return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
        except Exception:
            pass
    for part in payload.get("parts") or []:
        if (part.get("mimeType") or "") == "text/plain":
            txt = _extract_gmail_body(part)
            if txt:
                return txt
    for part in payload.get("parts") or []:
        txt = _extract_gmail_body(part)
        if txt:
            return txt
    return ""


def _execute_extra_service_request(service_type, tool_id, raw_arg, agent_profile, user_query=""):
    tid = (tool_id or "").strip().lower()
    arg = (raw_arg or "").strip()
    api_key = (agent_profile.get("api_key") or "").strip()
    if api_key in ("built-in-keyless", "FREE_NEWS_NO_KEY", "KEYLESS_SERVICE_NO_KEY"):
        api_key = ""

    try:
        # 1. GMAIL
        if service_type == "gmail" or tid.startswith("gmail_"):
            if not api_key:
                return ("Gmail requires a Google OAuth Access Token in Settings or Edit Agent.", [])
            auth = {"Authorization": f"Bearer {api_key}"}

            if tid == "gmail_labels":
                data = _http_json_request("https://gmail.googleapis.com/gmail/v1/users/me/labels", headers=auth)
                labels = [lb.get("name", "") for lb in (data.get("labels") or []) if lb.get("name")]
                return ("Gmail Labels:\n" + "\n".join(f"• {name}" for name in labels[:30]), [])

            if tid == "gmail_read":
                msg_id = arg.split()[0] if arg else ""
                if not msg_id:
                    return ("Provide a Gmail message ID to read.", [])
                msg = _http_json_request(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{urllib.parse.quote(msg_id)}?format=full",
                    headers=auth,
                )
                hdrs = {
                    h.get("name", "").lower(): h.get("value", "")
                    for h in ((msg.get("payload") or {}).get("headers") or [])
                }
                body_txt = _extract_gmail_body(msg.get("payload")) or msg.get("snippet", "")
                return (
                    f"From: {hdrs.get('from', 'Unknown')}\n"
                    f"To: {hdrs.get('to', '')}\n"
                    f"Date: {hdrs.get('date', '')}\n"
                    f"Subject: {hdrs.get('subject', '(No Subject)')}\n\n"
                    f"{body_txt[:3500]}",
                    [{"title": hdrs.get("subject") or f"Gmail {msg_id}", "url": f"https://mail.google.com/mail/u/0/#all/{msg_id}"}],
                )

            if tid == "gmail_send":
                parts = [p.strip() for p in arg.split("|", 2)]
                if len(parts) < 3 or "@" not in parts[0]:
                    return ("Format gmail_send as: recipient@example.com | Subject | Body text", [])
                to_addr, subj, body_txt = parts
                mime_msg = f"To: {to_addr}\r\nSubject: {subj}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body_txt}"
                raw_b64 = base64.urlsafe_b64encode(mime_msg.encode("utf-8")).decode("ascii")
                sent = _http_json_request(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={**auth, "Content-Type": "application/json"},
                    data_bytes=json.dumps({"raw": raw_b64}).encode("utf-8"),
                    method="POST",
                )
                return (f"Email sent successfully to {to_addr} (Message ID: {sent.get('id', 'sent')}).", [])

            q_param = urllib.parse.quote_plus(arg or "in:inbox")
            listing = _http_json_request(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={q_param}&maxResults=6",
                headers=auth,
            )
            msgs = listing.get("messages") or []
            if not msgs:
                return (f"No Gmail messages matched '{arg or 'in:inbox'}'.", [])
            lines = [f"Found {len(msgs)} Gmail messages:"]
            sources = []
            for idx, item in enumerate(msgs[:6], start=1):
                mid = item.get("id", "")
                meta = _http_json_request(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date",
                    headers=auth,
                )
                hdrs = {
                    h.get("name", "").lower(): h.get("value", "")
                    for h in ((meta.get("payload") or {}).get("headers") or [])
                }
                subj = hdrs.get("subject") or "(No Subject)"
                sender = hdrs.get("from") or "Unknown"
                snippet = (meta.get("snippet") or "").strip()
                lines.append(f"{idx}. [ID: {mid}] {subj} — From: {sender}")
                if snippet:
                    lines.append(f"   Snippet: {snippet[:180]}")
                sources.append({"title": subj, "url": f"https://mail.google.com/mail/u/0/#all/{mid}"})
            return ("\n".join(lines), sources)

        # 2. GOOGLE CALENDAR
        if service_type == "google_calendar" or tid.startswith("gcal_"):
            if not api_key:
                return ("Google Calendar requires a Google OAuth Access Token.", [])
            auth = {"Authorization": f"Bearer {api_key}"}

            if tid == "gcal_quick_add":
                if not arg:
                    return ("Provide event text to add (e.g. 'Dentist Friday at 2pm').", [])
                ev = _http_json_request(
                    f"https://www.googleapis.com/calendar/v3/calendars/primary/events/quickAdd?text={urllib.parse.quote_plus(arg)}",
                    headers=auth,
                    data_bytes=b"",
                    method="POST",
                )
                start_info = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date") or ""
                link = ev.get("htmlLink") or ""
                return (
                    f"Created Calendar Event: {ev.get('summary', arg)} ({start_info})",
                    [{"title": ev.get("summary", "Calendar Event"), "url": link}] if link else [],
                )

            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={urllib.parse.quote(now_iso)}&maxResults=8&singleEvents=true&orderBy=startTime"
            if tid == "gcal_search" and arg:
                url += f"&q={urllib.parse.quote_plus(arg)}"
            data = _http_json_request(url, headers=auth)
            items = data.get("items") or []
            if not items:
                return ("No upcoming Google Calendar events found.", [])
            lines = ["Upcoming Google Calendar Events:"]
            sources = []
            for idx, ev in enumerate(items[:8], start=1):
                title = ev.get("summary") or "(Busy / Untitled)"
                start_dt = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date") or ""
                loc = ev.get("location") or ""
                lines.append(f"{idx}. {title} — {start_dt}{(' @ ' + loc) if loc else ''}")
                if ev.get("htmlLink"):
                    sources.append({"title": title, "url": ev["htmlLink"]})
            return ("\n".join(lines), sources)

        # 3. SLACK
        if service_type == "slack" or tid.startswith("slack_"):
            if not api_key:
                return ("Slack requires a Slack Bot/User Token (xoxb-... or xoxp-...).", [])
            auth = {"Authorization": f"Bearer {api_key}"}

            if tid == "slack_post":
                parts = [p.strip() for p in arg.split("|", 1)]
                if len(parts) < 2:
                    return ("Format slack_post as: CHANNEL_ID | Message text", [])
                res = _http_json_request(
                    "https://slack.com/api/chat.postMessage",
                    headers={**auth, "Content-Type": "application/json; charset=utf-8"},
                    data_bytes=json.dumps({"channel": parts[0], "text": parts[1]}).encode("utf-8"),
                    method="POST",
                )
                if not res.get("ok"):
                    return (f"Slack API error: {res.get('error', 'unknown_error')}", [])
                return (f"Posted message to Slack channel {parts[0]}.", [])

            if tid == "slack_history":
                chan = arg.split()[0] if arg else ""
                if not chan:
                    return ("Provide a Slack channel ID to read history.", [])
                res = _http_json_request(
                    f"https://slack.com/api/conversations.history?channel={urllib.parse.quote(chan)}&limit=10",
                    headers=auth,
                )
                if not res.get("ok"):
                    return (f"Slack API error: {res.get('error', 'unknown_error')}", [])
                msgs = res.get("messages") or []
                lines = [f"Recent messages in {chan}:"]
                for m in msgs[:10]:
                    lines.append(f"• [{m.get('user', 'bot')}]: {m.get('text', '')}")
                return ("\n".join(lines), [])

            res = _http_json_request(
                "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=25",
                headers=auth,
            )
            if not res.get("ok"):
                return (f"Slack API error: {res.get('error', 'unknown_error')}", [])
            chans = res.get("channels") or []
            lines = ["Slack Channels:"]
            for ch in chans[:20]:
                lines.append(f"• #{ch.get('name')} (ID: {ch.get('id')})")
            return ("\n".join(lines), [])

        # 4. DISCORD
        if service_type == "discord" or tid.startswith("discord_"):
            if not api_key:
                return ("Discord requires a Bot Token or a Discord Webhook URL.", [])
            if api_key.startswith(("http://", "https://")) and "/webhooks/" in api_key:
                msg_text = arg.split("|", 1)[-1].strip() if "|" in arg else (arg or user_query)
                _http_json_request(
                    api_key,
                    headers={"Content-Type": "application/json"},
                    data_bytes=json.dumps({"content": msg_text[:1900]}).encode("utf-8"),
                    method="POST",
                )
                return ("Sent message to Discord webhook.", [])

            bot_auth = {"Authorization": api_key if api_key.startswith("Bot ") else f"Bot {api_key}"}
            if tid == "discord_send":
                parts = [p.strip() for p in arg.split("|", 1)]
                if len(parts) < 2:
                    return ("Format discord_send as: CHANNEL_ID | Message text", [])
                _http_json_request(
                    f"https://discord.com/api/v10/channels/{urllib.parse.quote(parts[0])}/messages",
                    headers={**bot_auth, "Content-Type": "application/json"},
                    data_bytes=json.dumps({"content": parts[1][:1900]}).encode("utf-8"),
                    method="POST",
                )
                return (f"Sent message to Discord channel {parts[0]}.", [])

            if tid == "discord_messages":
                chan = arg.split()[0] if arg else ""
                if not chan:
                    return ("Provide a Discord channel ID.", [])
                msgs = _http_json_request(
                    f"https://discord.com/api/v10/channels/{urllib.parse.quote(chan)}/messages?limit=10",
                    headers=bot_auth,
                )
                lines = [f"Recent messages in Discord channel {chan}:"]
                for m in (msgs if isinstance(msgs, list) else [])[:10]:
                    author = (m.get("author") or {}).get("username", "User")
                    lines.append(f"• {author}: {m.get('content', '')}")
                return ("\n".join(lines), [])

            guilds = _http_json_request("https://discord.com/api/v10/users/@me/guilds", headers=bot_auth)
            lines = ["Discord Servers (Guilds):"]
            for g in (guilds if isinstance(guilds, list) else [])[:20]:
                lines.append(f"• {g.get('name')} (ID: {g.get('id')})")
            return ("\n".join(lines), [])

        # 5. TRELLO
        if service_type == "trello" or tid.startswith("trello_"):
            if ":" not in api_key:
                return ("Trello requires 'api_key:token' separated by a colon.", [])
            t_key, t_tok = api_key.split(":", 1)
            auth_q = f"key={urllib.parse.quote(t_key.strip())}&token={urllib.parse.quote(t_tok.strip())}"

            if tid == "trello_create_card":
                parts = [p.strip() for p in arg.split("|", 2)]
                if len(parts) < 2:
                    return ("Format trello_create_card as: LIST_ID | Card Title | Optional description", [])
                id_list = urllib.parse.quote(parts[0])
                name = urllib.parse.quote_plus(parts[1])
                desc = urllib.parse.quote_plus(parts[2] if len(parts) > 2 else "")
                card = _http_json_request(
                    f"https://api.trello.com/1/cards?{auth_q}&idList={id_list}&name={name}&desc={desc}",
                    data_bytes=b"",
                    method="POST",
                )
                url = card.get("url") or ""
                return (
                    f"Created Trello card '{card.get('name', parts[1])}'.",
                    [{"title": card.get("name", "Trello Card"), "url": url}] if url else [],
                )

            if tid == "trello_cards" and arg:
                board_id = urllib.parse.quote(arg.split()[0])
                cards = _http_json_request(
                    f"https://api.trello.com/1/boards/{board_id}/cards?fields=name,desc,url,due&{auth_q}"
                )
                lines = [f"Cards on Trello board {board_id}:"]
                sources = []
                for c in (cards if isinstance(cards, list) else [])[:15]:
                    lines.append(f"• {c.get('name')} (ID: {c.get('id')})")
                    if c.get("url"):
                        sources.append({"title": c.get("name", "Card"), "url": c["url"]})
                return ("\n".join(lines), sources)

            boards = _http_json_request(
                f"https://api.trello.com/1/members/me/boards?fields=name,url,closed&{auth_q}"
            )
            lines = ["Your Trello Boards:"]
            sources = []
            for b in (boards if isinstance(boards, list) else [])[:15]:
                if not b.get("closed"):
                    lines.append(f"• {b.get('name')} (ID: {b.get('id')})")
                    if b.get("url"):
                        sources.append({"title": b.get("name", "Board"), "url": b["url"]})
            return ("\n".join(lines), sources)

        # 6. LINEAR
        if service_type == "linear" or tid.startswith("linear_"):
            if not api_key:
                return ("Linear requires a Personal API Key (lin_api_...).", [])
            headers = {"Authorization": api_key, "Content-Type": "application/json"}

            if tid == "linear_teams":
                gql = {"query": "{ teams { nodes { id name key } } }"}
                res = _http_json_request(
                    "https://api.linear.app/graphql",
                    headers=headers,
                    data_bytes=json.dumps(gql).encode("utf-8"),
                    method="POST",
                )
                teams = (((res.get("data") or {}).get("teams") or {}).get("nodes") or [])
                return ("Linear Teams:\n" + "\n".join(f"• {t['name']} ({t['key']}) — ID: {t['id']}" for t in teams), [])

            if tid == "linear_create_issue":
                parts = [p.strip() for p in arg.split("|", 2)]
                if len(parts) < 2:
                    return ("Format linear_create_issue as: TEAM_ID | Issue Title | Optional description", [])
                gql = {
                    "query": "mutation($teamId: String!, $title: String!, $desc: String) { issueCreate(input: { teamId: $teamId, title: $title, description: $desc }) { success issue { identifier title url } } }",
                    "variables": {
                        "teamId": parts[0],
                        "title": parts[1],
                        "desc": parts[2] if len(parts) > 2 else "",
                    },
                }
                res = _http_json_request(
                    "https://api.linear.app/graphql",
                    headers=headers,
                    data_bytes=json.dumps(gql).encode("utf-8"),
                    method="POST",
                )
                issue = ((((res.get("data") or {}).get("issueCreate") or {}).get("issue")) or {})
                url = issue.get("url") or ""
                return (
                    f"Created Linear issue {issue.get('identifier', '')}: {issue.get('title', parts[1])}",
                    [{"title": f"{issue.get('identifier', '')} {issue.get('title', '')}".strip(), "url": url}] if url else [],
                )

            gql = {
                "query": "{ issues(first: 10, orderBy: updatedAt) { nodes { identifier title url state { name } assignee { name } } } }"
            }
            res = _http_json_request(
                "https://api.linear.app/graphql",
                headers=headers,
                data_bytes=json.dumps(gql).encode("utf-8"),
                method="POST",
            )
            nodes = (((res.get("data") or {}).get("issues") or {}).get("nodes") or [])
            lines = ["Recent Linear Issues:"]
            sources = []
            for n in nodes:
                st = (n.get("state") or {}).get("name", "")
                lines.append(f"• [{n.get('identifier')}] {n.get('title')} ({st})")
                if n.get("url"):
                    sources.append({"title": f"{n.get('identifier')} {n.get('title')}", "url": n["url"]})
            return ("\n".join(lines), sources)

        # 7. SPOTIFY
        if service_type == "spotify" or tid.startswith("spotify_"):
            if not api_key:
                return ("Spotify requires a Spotify OAuth Bearer Token.", [])
            auth = {"Authorization": f"Bearer {api_key}"}

            if tid == "spotify_now_playing":
                data = _http_json_request("https://api.spotify.com/v1/me/player/currently-playing", headers=auth)
                item = data.get("item") or {}
                if not item:
                    return ("Nothing is currently playing on Spotify.", [])
                artists = ", ".join(a.get("name", "") for a in (item.get("artists") or []))
                ext_url = (item.get("external_urls") or {}).get("spotify", "")
                return (
                    f"Currently Playing: {item.get('name')} — {artists}",
                    [{"title": f"{item.get('name')} — {artists}", "url": ext_url}] if ext_url else [],
                )

            if tid == "spotify_top":
                data = _http_json_request("https://api.spotify.com/v1/me/top/tracks?limit=8", headers=auth)
                items = data.get("items") or []
                lines = ["Your Top Spotify Tracks:"]
                sources = []
                for idx, tr in enumerate(items, start=1):
                    artists = ", ".join(a.get("name", "") for a in (tr.get("artists") or []))
                    lines.append(f"{idx}. {tr.get('name')} — {artists}")
                    ext_url = (tr.get("external_urls") or {}).get("spotify", "")
                    if ext_url:
                        sources.append({"title": f"{tr.get('name')} — {artists}", "url": ext_url})
                return ("\n".join(lines), sources)

            q_param = urllib.parse.quote_plus(arg or user_query or "top hits")
            data = _http_json_request(
                f"https://api.spotify.com/v1/search?q={q_param}&type=track&limit=8",
                headers=auth,
            )
            tracks = ((data.get("tracks") or {}).get("items") or [])
            lines = [f"Spotify Search Results for '{arg or user_query}':"]
            sources = []
            for idx, tr in enumerate(tracks, start=1):
                artists = ", ".join(a.get("name", "") for a in (tr.get("artists") or []))
                lines.append(f"{idx}. {tr.get('name')} — {artists}")
                ext_url = (tr.get("external_urls") or {}).get("spotify", "")
                if ext_url:
                    sources.append({"title": f"{tr.get('name')} — {artists}", "url": ext_url})
            return ("\n".join(lines), sources)

        # 8. REDDIT (KEYLESS OR WITH OPTIONAL TOKEN)
        if service_type == "reddit" or tid.startswith("reddit_"):
            headers = {"User-Agent": "desktop:MosaicLocalAI:v1.0 (by /u/mosaic_studio)"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            if tid == "reddit_hot":
                sub = re.sub(r"^r/", "", (arg or "technology").strip()).split()[0]
                url = f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/hot.json?limit=8"
                heading = f"Hot posts in r/{sub}:"
            else:
                q_param = urllib.parse.quote_plus(arg or user_query or "technology")
                url = f"https://www.reddit.com/search.json?q={q_param}&sort=relevance&limit=8"
                heading = f"Reddit search results for '{arg or user_query}':"
            data = _http_json_request(url, headers=headers)
            children = ((data.get("data") or {}).get("children") or [])
            if not children:
                return ("No Reddit posts matched that query.", [])
            lines = [heading]
            sources = []
            for idx, ch in enumerate(children[:8], start=1):
                post = ch.get("data") or {}
                title = post.get("title") or "Untitled"
                sub_name = post.get("subreddit_name_prefixed") or ""
                score = post.get("score", 0)
                permalink = f"https://www.reddit.com{post.get('permalink', '')}"
                lines.append(f"{idx}. {title} ({sub_name}, {score} pts)")
                sources.append({"title": f"{title} ({sub_name})", "url": permalink})
            return ("\n".join(lines), sources)

        # 9. WIKIPEDIA (KEYLESS)
        if service_type == "wikipedia" or tid.startswith("wiki_"):
            query_txt = (arg or user_query or "").strip()
            if tid == "wiki_summary" and query_txt:
                slug = urllib.parse.quote(query_txt.replace(" ", "_"))
                data = _http_json_request(f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}")
                title = data.get("title") or query_txt
                extract = data.get("extract") or "No summary found."
                page_url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page", "")
                return (
                    f"{title}:\n{extract}",
                    [{"title": f"{title} — Wikipedia", "url": page_url}] if page_url else [],
                )

            q_param = urllib.parse.quote_plus(query_txt or "Artificial intelligence")
            data = _http_json_request(
                f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_param}&format=json&srlimit=5"
            )
            hits = ((data.get("query") or {}).get("search") or [])
            if not hits:
                return (f"No Wikipedia articles found for '{query_txt}'.", [])
            top_title = hits[0].get("title") or query_txt
            top_slug = urllib.parse.quote(top_title.replace(" ", "_"))
            summary_data = _http_json_request(f"https://en.wikipedia.org/api/rest_v1/page/summary/{top_slug}")
            lines = [f"Top Wikipedia Article — {top_title}:", summary_data.get("extract") or "", "\nRelated Articles:"]
            sources = []
            for h in hits[:5]:
                t = h.get("title", "")
                u = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(t.replace(' ', '_'))}"
                lines.append(f"• {t}")
                sources.append({"title": f"{t} — Wikipedia", "url": u})
            return ("\n".join(lines), sources)

        # 10. ARXIV RESEARCH (KEYLESS)
        if service_type == "arxiv" or tid.startswith("arxiv_"):
            q_param = urllib.parse.quote_plus(arg or user_query or "large language models")
            xml_url = f"http://export.arxiv.org/api/query?search_query=all:{q_param}&start=0&max_results=6"
            req = urllib.request.Request(xml_url, headers={"User-Agent": "Mosaic-Local-AI-Studio/1.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                xml_bytes = resp.read()
            root = ET.fromstring(xml_bytes)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            if not entries:
                return ("No arXiv papers matched that search.", [])
            lines = [f"arXiv Papers for '{arg or user_query}':"]
            sources = []
            for idx, ent in enumerate(entries[:6], start=1):
                title = re.sub(r"\s+", " ", (ent.findtext("atom:title", "", ns) or "")).strip()
                summary = re.sub(r"\s+", " ", (ent.findtext("atom:summary", "", ns) or "")).strip()[:240]
                link = (ent.findtext("atom:id", "", ns) or "").strip()
                pub = (ent.findtext("atom:published", "", ns) or "")[:10]
                authors = [a.findtext("atom:name", "", ns) for a in ent.findall("atom:author", ns)[:3]]
                lines.append(f"{idx}. {title} ({', '.join(authors)}, {pub})")
                if summary:
                    lines.append(f"   Abstract: {summary}...")
                if link:
                    sources.append({"title": title, "url": link})
            return ("\n".join(lines), sources)

        # 11. CRYPTO & MARKETS (KEYLESS)
        if service_type == "crypto" or tid.startswith("crypto_"):
            if tid == "crypto_trending":
                data = _http_json_request("https://api.coingecko.com/api/v3/search/trending")
                coins = data.get("coins") or []
                lines = ["Trending Cryptocurrencies on CoinGecko:"]
                sources = []
                for idx, entry in enumerate(coins[:8], start=1):
                    item = entry.get("item") or {}
                    name = item.get("name", "")
                    sym = item.get("symbol", "")
                    rank = item.get("market_cap_rank", "?")
                    slug = item.get("id", "")
                    lines.append(f"{idx}. {name} ({sym}) — Market Cap Rank #{rank}")
                    if slug:
                        sources.append({"title": f"{name} ({sym})", "url": f"https://www.coingecko.com/en/coins/{slug}"})
                return ("\n".join(lines), sources)

            coins_arg = re.sub(r"[^a-zA-Z0-9,-]", "", (arg or "bitcoin,ethereum,solana").lower()) or "bitcoin,ethereum,solana"
            data = _http_json_request(
                f"https://api.coingecko.com/api/v3/simple/price?ids={urllib.parse.quote(coins_arg)}&vs_currencies=usd,aud&include_24hr_change=true"
            )
            if not isinstance(data, dict) or not data:
                return (f"No CoinGecko price data found for '{coins_arg}'. Use coin IDs like 'bitcoin,ethereum,solana'.", [])
            lines = ["Live Cryptocurrency Prices:"]
            sources = []
            for cid, info in data.items():
                usd = info.get("usd", "N/A")
                aud = info.get("aud", "N/A")
                chg = info.get("usd_24h_change")
                chg_str = f" ({chg:+.2f}% 24h)" if isinstance(chg, (int, float)) else ""
                lines.append(f"• {cid.capitalize()}: ${usd:,} USD / ${aud:,} AUD{chg_str}" if isinstance(usd, (int, float)) and isinstance(aud, (int, float)) else f"• {cid.capitalize()}: {usd} USD / {aud} AUD{chg_str}")
                sources.append({"title": f"{cid.capitalize()} Live Price", "url": f"https://www.coingecko.com/en/coins/{cid}"})
            return ("\n".join(lines), sources)

        # 12. CURRENCY & FX RATES (KEYLESS)
        if service_type == "currency" or tid.startswith("fx_"):
            txt = (arg or user_query or "USD").upper()
            m = re.search(r"(\d+(?:\.\d+)?)\s*([A-Z]{3})\s*(?:TO|IN|->)\s*([A-Z]{3})", txt)
            if m:
                amount = float(m.group(1))
                src_cur, dst_cur = m.group(2), m.group(3)
                data = _http_json_request(f"https://open.er-api.com/v6/latest/{src_cur}")
                rates = data.get("rates") or {}
                if dst_cur not in rates:
                    return (f"Unsupported target currency '{dst_cur}'.", [])
                converted = amount * float(rates[dst_cur])
                return (
                    f"{amount:,.2f} {src_cur} = {converted:,.4f} {dst_cur} (Rate: 1 {src_cur} = {rates[dst_cur]} {dst_cur})",
                    [{"title": f"{src_cur} to {dst_cur} Exchange Rate", "url": "https://www.exchangerate-api.com"}],
                )
            codes = re.findall(r"\b[A-Z]{3}\b", txt)
            base_cur = codes[0] if codes else "USD"
            data = _http_json_request(f"https://open.er-api.com/v6/latest/{base_cur}")
            rates = data.get("rates") or {}
            if not rates:
                return (f"Could not fetch FX rates for '{base_cur}'.", [])
            major = ["USD", "EUR", "GBP", "AUD", "JPY", "CAD", "NZD", "CHF", "SGD"]
            lines = [f"Live Exchange Rates (Base: 1 {base_cur}):"]
            for c in major:
                if c in rates and c != base_cur:
                    lines.append(f"• {c}: {rates[c]}")
            return ("\n".join(lines), [{"title": f"{base_cur} FX Rates", "url": "https://www.exchangerate-api.com"}])

    except urllib.error.HTTPError as e:
        err_detail = ""
        try:
            err_detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return (f"HTTP {e.code} Error from {service_type}: {err_detail or e.reason}", [])
    except Exception as e:
        return (f"{service_type} API Error: {e}", [])

    return (f"Unsupported service tool '{tool_id}'.", [])


def _execute_custom_api_request(tool_id, raw_arg, agent_profile, user_query=""):
    service_type = (agent_profile.get("service_type") or "").strip().lower()
    if service_type == "free_news" or tool_id.lower().startswith("free_news"):
        return _execute_free_news_request(raw_arg, user_query=user_query)
    if service_type in EXTRA_API_SERVICES or tool_id.lower().startswith(EXTRA_TOOL_PREFIXES):
        return _execute_extra_service_request(
            service_type, tool_id, raw_arg, agent_profile, user_query=user_query
        )

    base_url = _extract_agent_base_url(agent_profile)
    api_key = (agent_profile.get("api_key") or "").strip()

    if not base_url:
        return (
            "Configuration Error: No API Base URL is configured for this Custom REST API. "
            "Open Settings (or Edit Agent) and set the Base URL (for NewsAPI, use https://newsapi.org/v2).",
            [],
        )

    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    arg = (raw_arg or "").strip()
    method = "POST" if tool_id.lower().endswith("_post") else "GET"
    body_bytes = None

    if arg.upper().startswith("GET "):
        method = "GET"
        arg = arg[4:].strip()
    elif arg.upper().startswith("POST "):
        method = "POST"
        arg = arg[5:].strip()

    if method == "POST" and "\n" in arg:
        first_line, rest = arg.split("\n", 1)
        arg = first_line.strip()
        if rest.strip():
            body_bytes = rest.strip().encode("utf-8")

    is_newsapi = "newsapi.org" in base_url.lower()

    if is_newsapi:
        if not arg or arg == "/":
            inferred = _infer_custom_api_fallback(user_query, agent_profile)
            arg = inferred[1] if inferred else "/top-headlines?country=us&pageSize=8"
        elif not arg.startswith(("http://", "https://", "/")) and "?" not in arg:
            encoded = urllib.parse.quote_plus(arg[:120])
            arg = f"/everything?q={encoded}&sortBy=publishedAt&language=en&pageSize=8"

    if arg.startswith(("http://", "https://")):
        full_url = arg
    else:
        path = arg if arg.startswith("/") else f"/{arg}"
        full_url = f"{base_url}{path}"

    parsed = urllib.parse.urlsplit(full_url)
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

    if is_newsapi:
        cleaned_pairs = []
        for k, v in query_pairs:
            if k.lower() == "apikey":
                if v and not any(tok in v.upper() for tok in ("YOUR_", "API_KEY", "INSERT", "PLACEHOLDER", "<", ">")):
                    cleaned_pairs.append((k, v))
            else:
                cleaned_pairs.append((k, v))

        param_keys = {k.lower() for k, _ in cleaned_pairs}
        lower_path = parsed.path.lower()
        if lower_path.endswith("/top-headlines") and not (
            param_keys & {"country", "category", "sources", "q"}
        ):
            cleaned_pairs.append(("country", "us"))
        elif lower_path.endswith("/everything") and not (
            param_keys & {"q", "qintitle", "sources", "domains"}
        ):
            fallback_q = (user_query or "news").strip()[:100] or "news"
            cleaned_pairs.append(("q", fallback_q))

        if "pagesize" not in param_keys:
            cleaned_pairs.append(("pageSize", "8"))

        new_query = urllib.parse.urlencode(cleaned_pairs)
        full_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
        )

    headers = {
        "User-Agent": "Mosaic-Local-AI-Studio/1.0",
        "Accept": "application/json",
    }
    if api_key:
        if is_newsapi:
            headers["X-Api-Key"] = api_key
        else:
            auth_val = api_key if api_key.lower().startswith(("bearer ", "token ", "basic ")) else f"Bearer {api_key}"
            headers["Authorization"] = auth_val
            headers["X-Api-Key"] = api_key
    if body_bytes is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(full_url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        detail = err_body[:400]
        try:
            err_json = json.loads(err_body)
            if isinstance(err_json, dict) and err_json.get("message"):
                code = err_json.get("code", "")
                detail = f"{code}: {err_json['message']}" if code else err_json["message"]
        except Exception:
            pass
        return (f"HTTP {e.code} Error from {parsed.netloc}: {detail or e.reason}", [])
    except urllib.error.URLError as e:
        return (f"Network Error reaching {parsed.netloc}: {e.reason}", [])
    except Exception as e:
        return (f"API Request Error: {e}", [])

    try:
        data = json.loads(raw_body)
    except Exception:
        return (raw_body[:4000], [])

    if isinstance(data, dict) and isinstance(data.get("articles"), list):
        articles = data["articles"]
        if not articles:
            return (
                "NewsAPI returned 0 articles for that query. Try /everything?q=<keywords>&language=en or /top-headlines?country=us.",
                [],
            )
        lines = [f"NewsAPI returned {data.get('totalResults', len(articles))} results (showing top {min(len(articles), 8)}):"]
        sources = []
        for idx, art in enumerate(articles[:8], start=1):
            title = (art.get("title") or "Untitled").strip()
            src_name = ((art.get("source") or {}).get("name") or "News").strip()
            published = (art.get("publishedAt") or "")[:10]
            desc = (art.get("description") or "").strip()
            url = (art.get("url") or "").strip()
            lines.append(f"{idx}. {title} ({src_name}, {published})")
            if desc:
                lines.append(f"   Summary: {desc}")
            if url:
                lines.append(f"   URL: {url}")
                sources.append({"title": f"{title} — {src_name}", "url": url})
        return ("\n".join(lines), sources)

    formatted = json.dumps(data, indent=2, ensure_ascii=False)
    if len(formatted) > 4500:
        formatted = formatted[:4500] + "\n... [truncated]"
    return (formatted, [])


def _make_globe_icon(color_hex, size=17):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color_hex), 1.5)
    painter.setPen(pen)
    margin = 2
    d = size - 2 * margin
    painter.drawEllipse(margin, margin, d, d)
    painter.drawEllipse(int(size * 0.32), margin, max(4, int(size * 0.36)), d)
    mid_y = size // 2
    painter.drawLine(margin, mid_y, size - margin, mid_y)
    painter.end()
    return QIcon(pm)


def _make_api_icon(color_hex, size=17):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color_hex), 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    mid_y = size // 2
    painter.drawLine(6, 4, 2, mid_y)
    painter.drawLine(2, mid_y, 6, size - 4)
    painter.drawLine(size - 6, 4, size - 2, mid_y)
    painter.drawLine(size - 2, mid_y, size - 6, size - 4)
    painter.drawLine(size // 2 + 2, 3, size // 2 - 2, size - 3)
    painter.end()
    return QIcon(pm)


def _highlight_code(escaped_code, p):
    tokens = []

    def _stash(html_fragment):
        key = f"\x00TOK{len(tokens)}\x00"
        tokens.append(html_fragment)
        return key

    escaped_code = _STR_RE.sub(
        lambda m: _stash(f'<span style="color:{p["green"]};">{m.group(0)}</span>'),
        escaped_code,
    )
    escaped_code = _KW_RE.sub(
        lambda m: _stash(
            f'<span style="color:{p["accent"]};font-weight:bold;">{m.group(0)}</span>'
        ),
        escaped_code,
    )
    escaped_code = _NUM_RE.sub(
        lambda m: _stash(f'<span style="color:{p["orange"]};">{m.group(0)}</span>'),
        escaped_code,
    )
    for idx, frag in enumerate(tokens):
        escaped_code = escaped_code.replace(f"\x00TOK{idx}\x00", frag)
    return escaped_code


def _format_inline(text, p):
    tokens = []

    def _stash(html_fragment):
        key = f"\x00INL{len(tokens)}\x00"
        tokens.append(html_fragment)
        return key

    def _code_repl(m):
        code_txt = html.escape(m.group(1))
        return _stash(
            f'<code style="background-color:{p["bg_code"]};color:{p["cyan"]};'
            f'padding:1px 5px;border-radius:4px;font-family:monospace;">{code_txt}</code>'
        )

    def _md_link_repl(m):
        label = html.escape(m.group(1))
        url = html.escape(m.group(2).strip(), quote=True)
        return _stash(
            f'<a href="{url}" style="color:{p["accent"]};text-decoration:underline;">{label}</a>'
        )

    def _raw_url_repl(m):
        raw_url = m.group(0)
        escaped_url = html.escape(raw_url, quote=True)
        return _stash(
            f'<a href="{escaped_url}" style="color:{p["accent"]};text-decoration:underline;">{html.escape(raw_url)}</a>'
        )

    text = re.sub(r"`([^`\n]+)`", _code_repl, text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", _md_link_repl, text)
    text = re.sub(r"https?://[^\s<>\"]+", _raw_url_repl, text)

    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"~~(.+?)~~", r"<s>\1</s>", escaped)

    for idx, frag in enumerate(tokens):
        escaped = escaped.replace(f"\x00INL{idx}\x00", frag)
    return escaped


def render_markdown_html(text, p):
    if not text:
        return ""

    cleaned = _THINK_BLOCK_RE.sub("", text).strip()
    if not cleaned:
        return ""

    lines = cleaned.splitlines()
    html_out = []
    in_code = False
    code_lang = ""
    code_lines = []
    in_ul = False
    in_ol = False
    table_rows = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_out.append("</ul>")
            in_ul = False
        if in_ol:
            html_out.append("</ol>")
            in_ol = False

    def close_table():
        nonlocal table_rows
        if not table_rows:
            return
        html_out.append(
            f'<table cellspacing="0" cellpadding="6" '
            f'style="border-collapse:collapse;margin:8px 0;border:1px solid {p["border"]};">'
        )
        for r_idx, row in enumerate(table_rows):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if r_idx == 1 and all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                continue
            tag = "th" if r_idx == 0 else "td"
            bg = p["bg_code_header"] if r_idx == 0 else p["bg_card"]
            html_out.append("<tr>")
            for cell in cells:
                html_out.append(
                    f'<{tag} style="border:1px solid {p["border"]};background-color:{bg};text-align:left;">'
                    f"{_format_inline(cell, p)}</{tag}>"
                )
            html_out.append("</tr>")
        html_out.append("</table>")
        table_rows = []

    def flush_code():
        nonlocal in_code, code_lang, code_lines
        lang_label = html.escape(code_lang or "code")
        raw_code = "\n".join(code_lines)
        highlighted = _highlight_code(html.escape(raw_code), p)
        html_out.append(
            f'<div style="margin:8px 0;border:1px solid {p["border"]};border-radius:8px;overflow:hidden;">'
            f'<div style="background-color:{p["bg_code_header"]};color:{p["text_muted"]};'
            f'padding:4px 10px;font-size:11px;font-family:monospace;">{lang_label}</div>'
            f'<pre style="margin:0;padding:10px;background-color:{p["bg_code"]};'
            f'color:{p["text_primary"]};font-family:monospace;white-space:pre-wrap;">{highlighted}</pre>'
            f"</div>"
        )
        in_code = False
        code_lang = ""
        code_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            close_lists()
            close_table()
            if not in_code:
                in_code = True
                code_lang = stripped[3:].strip()
                code_lines = []
            else:
                flush_code()
            continue

        if in_code:
            code_lines.append(line)
            continue

        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 2:
            close_lists()
            table_rows.append(stripped)
            continue
        else:
            close_table()

        h_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if h_match:
            close_lists()
            level = len(h_match.group(1))
            sizes = {1: "18px", 2: "16px", 3: "14px", 4: "13px"}
            html_out.append(
                f'<div style="font-size:{sizes[level]};font-weight:bold;margin:8px 0 4px 0;">'
                f"{_format_inline(h_match.group(2), p)}</div>"
            )
            continue

        if re.match(r"^([-*_])\1{2,}$", stripped):
            close_lists()
            html_out.append(
                f'<hr style="border:none;border-top:1px solid {p["border"]};margin:8px 0;">'
            )
            continue

        if stripped.startswith("> "):
            close_lists()
            html_out.append(
                f'<div style="border-left:3px solid {p["accent"]};padding-left:10px;'
                f'margin:4px 0;color:{p["text_secondary"]};">{_format_inline(stripped[2:], p)}</div>'
            )
            continue

        ul_match = re.match(r"^[-*+]\s+(.*)$", stripped)
        if ul_match:
            if in_ol:
                html_out.append("</ol>")
                in_ol = False
            if not in_ul:
                html_out.append('<ul style="margin:4px 0 4px 18px;padding:0;">')
                in_ul = True
            html_out.append(
                f'<li style="margin:2px 0;line-height:1.45;">{_format_inline(ul_match.group(1), p)}</li>'
            )
            continue

        ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ol_match:
            if in_ul:
                html_out.append("</ul>")
                in_ul = False
            if not in_ol:
                html_out.append('<ol style="margin:4px 0 4px 18px;padding:0;">')
                in_ol = True
            html_out.append(
                f'<li style="margin:2px 0;line-height:1.45;">{_format_inline(ol_match.group(1), p)}</li>'
            )
            continue

        close_lists()
        if stripped == "":
            html_out.append('<div style="height:6px;"></div>')
        else:
            html_out.append(f'<div style="line-height:1.45;">{_format_inline(line, p)}</div>')

    if in_code:
        flush_code()
    close_lists()
    close_table()

    return "".join(html_out)


class OllamaStarterWorker(QThread):

    finished_check = Signal(bool, str)

    def __init__(self, ensure_ollama, base_url):
        super().__init__()
        self._ensure_ollama = ensure_ollama
        self._base_url = base_url

    def run(self):
        ok, msg = self._ensure_ollama(self._base_url)
        self.finished_check.emit(ok, msg)


class ChatWorker(QThread):

    chunk = Signal(str)
    replace_reply = Signal(str)
    failed = Signal(str)
    status_changed = Signal(str)
    search_completed = Signal(list)
    agent_updated = Signal()
    request_screenshot = Signal()
    request_action_confirm = Signal(str)

    def __init__(
        self,
        stream_chat,
        base_url,
        model,
        messages,
        options=None,
        stream=True,
        keep_alive=None,
        timeout=300,
        use_web_search=False,
        search_web_fn=None,
        format_search_fn=None,
        search_query="",
        max_search_results=5,
        ollama_api_key="",
        mode="chat",
        agent_id=None,
        chat_api_enabled=False,
        chat_agent=None,
        cowork_allow_cursor=False,
        cowork_confirm_actions=True,
        cowork_screen_size=(1920, 1080),
        initial_screen_b64="",
    ):
        super().__init__()
        self._stream_chat = stream_chat
        self._base_url = base_url
        self._model = model
        self._messages = [dict(m) for m in messages]
        self._options = options
        self._stream = stream
        self._keep_alive = keep_alive
        self._timeout = timeout
        self._use_web_search = bool(use_web_search)
        self._search_web_fn = search_web_fn
        self._format_search_fn = format_search_fn
        self._search_query = (search_query or "").strip()
        self._max_search_results = max_search_results
        self._ollama_api_key = ollama_api_key
        self._mode = mode or "chat"
        self._agent_id = agent_id
        self._chat_api_enabled = bool(chat_api_enabled)
        self._chat_agent = dict(chat_agent) if isinstance(chat_agent, dict) else None
        self._cowork_allow_cursor = bool(cowork_allow_cursor)
        self._cowork_confirm_actions = bool(cowork_confirm_actions)
        self._cowork_screen_size = cowork_screen_size
        self._initial_screen_b64 = initial_screen_b64
        self._stop_requested = False

        self._sync_event = threading.Event()
        self._latest_screen_b64 = ""
        self._confirm_result = False

    def stop(self):
        self._stop_requested = True
        self._sync_event.set()

    def provide_screenshot(self, b64):
        self._latest_screen_b64 = b64 or ""
        self._sync_event.set()

    def provide_confirm_result(self, allowed):
        self._confirm_result = bool(allowed)
        self._sync_event.set()

    def _stream_single_turn(self, payload_messages, emit_chunks=True):
        gen = None
        acc = ""
        try:
            gen = self._stream_chat(
                self._base_url,
                self._model,
                payload_messages,
                options=self._options,
                stream=self._stream,
                keep_alive=self._keep_alive,
                timeout=self._timeout,
            )
            for piece in gen:
                if self._stop_requested:
                    break
                acc += piece
                if emit_chunks:
                    self.chunk.emit(piece)
        finally:
            if gen is not None:
                gen.close()
        return acc

    def _run_api_tool_loop(self, payload_messages, agent_profile, collected_sources, is_agent_mode=True):
        used_fallback = False
        actor_name = agent_profile.get("name", "Mosaic")

        for step in range(4):
            if self._stop_requested:
                return
            self.replace_reply.emit("")
            turn_text = self._stream_single_turn(payload_messages, emit_chunks=True)
            if self._stop_requested:
                return

            match = _TOOL_CALL_RE.search(turn_text)
            tool_id, arg = (match.group(1), match.group(2)) if match else (None, None)

            if not tool_id and step == 0 and not used_fallback:
                inferred = modes.infer_fallback_tool_call(self._search_query, agent_profile)
                if inferred is None:
                    inferred = _infer_custom_api_fallback(self._search_query, agent_profile)
                if inferred is not None:
                    tool_id, arg = inferred
                    used_fallback = True

            if not tool_id:
                break

            if agent_profile.get("boundary_mode") == "confirm":
                self._sync_event.clear()
                self.request_action_confirm.emit(
                    f"{actor_name} wants to run: {tool_id} ({arg[:80]})"
                )
                self._sync_event.wait(timeout=60.0)
                if self._stop_requested or not self._confirm_result:
                    self.replace_reply.emit(
                        f"Action `{tool_id}` was cancelled by your confirmation rule."
                    )
                    break

            self.replace_reply.emit("")
            self.status_changed.emit(f"{actor_name} running {tool_id}...")
            stype_lower = (agent_profile.get("service_type") or "").strip().lower()
            is_custom_call = (
                stype_lower in ("custom", *EXTRA_API_SERVICES.keys())
                or tool_id.lower().startswith(("custom", "http_", "api_", *EXTRA_TOOL_PREFIXES))
                or bool(_extract_agent_base_url(agent_profile))
            )
            if is_custom_call:
                tool_out, tool_sources = _execute_custom_api_request(
                    tool_id, arg, agent_profile, user_query=self._search_query
                )
            else:
                tool_out, tool_sources = modes.execute_agent_tool(tool_id, arg, agent=agent_profile)
            if is_agent_mode and tool_id in ("save_note", "note", "remember"):
                self.agent_updated.emit()
            if tool_sources:
                collected_sources = _dedupe_sources(collected_sources + tool_sources)
                self.search_completed.emit(collected_sources)

            payload_messages.append({"role": "assistant", "content": f"[[CALL_API: {tool_id} | {arg}]]"})
            if is_agent_mode:
                followup_content = (
                    f"[TOOL OUTPUT FOR {actor_name.upper()}]:\n{tool_out}\n\n"
                    "Using the tool output above and staying in your assigned personality and role, "
                    "give a clear, helpful response."
                )
                self.status_changed.emit(f"{actor_name} synthesizing...")
            else:
                followup_content = (
                    f"[API TOOL OUTPUT ({tool_id})]:\n{tool_out}\n\n"
                    "Using the API tool output above, give a clear, helpful response."
                )
                self.status_changed.emit("Synthesizing response...")

            payload_messages.append({"role": "user", "content": followup_content})

    def run(self):
        try:
            payload_messages = [dict(m) for m in self._messages]
            collected_sources = []

            if (
                self._mode != "agent"
                and self._use_web_search
                and self._search_query
                and self._search_web_fn is not None
                and self._format_search_fn is not None
            ):
                self.status_changed.emit("Searching the web...")
                results = self._search_web_fn(
                    self._search_query,
                    max_results=self._max_search_results,
                    api_key=self._ollama_api_key,
                )
                if self._stop_requested:
                    return
                collected_sources = _dedupe_sources(collected_sources + results)
                self.search_completed.emit(collected_sources)
                if payload_messages and payload_messages[-1].get("role") == "user":
                    augmented = (
                        payload_messages[-1]["content"]
                        + self._format_search_fn(self._search_query, results)
                    )
                    payload_messages[-1]["content"] = augmented
                self.status_changed.emit("Thinking...")

            if self._mode == "agent":
                active_agent = modes.get_agent(self._agent_id) if self._agent_id else modes.get_active_agent()
                if active_agent is None:
                    active_agent = modes.get_active_agent()
                self._run_api_tool_loop(
                    payload_messages, active_agent, collected_sources, is_agent_mode=True
                )
                return

            if self._mode == "cowork":
                screen_w, screen_h = self._cowork_screen_size
                cur_b64 = self._initial_screen_b64
                if cur_b64 and payload_messages and payload_messages[-1].get("role") == "user":
                    payload_messages[-1]["images"] = [cur_b64]

                action_log = []
                for _step in range(6):
                    if self._stop_requested:
                        return
                    self.replace_reply.emit("")
                    try:
                        turn_text = self._stream_single_turn(payload_messages, emit_chunks=True)
                    except Exception as err:
                        err_lower = str(err).lower()
                        if "images" in payload_messages[-1] and any(
                            k in err_lower for k in ("vision", "image", "mmproj", "400", "500")
                        ):
                            payload_messages[-1].pop("images", None)
                            self.replace_reply.emit("")
                            self.status_changed.emit(
                                "Selected model lacks vision support — running in text mode..."
                            )
                            turn_text = self._stream_single_turn(payload_messages, emit_chunks=True)
                        else:
                            raise

                    if self._stop_requested:
                        return

                    act_match = _COWORK_ACT_RE.search(turn_text)
                    if not act_match or not self._cowork_allow_cursor:
                        if action_log:
                            clean_final = _COWORK_ACT_RE.sub("", turn_text).strip()
                            summary_block = "\n".join(f"- {entry}" for entry in action_log)
                            final_out = f"**Cowork Actions Executed:**\n{summary_block}\n\n{clean_final}".strip()
                            self.replace_reply.emit(final_out)
                        break

                    act_type, act_arg = act_match.group(1), act_match.group(2)
                    desc = f"{act_type} ({act_arg})"

                    if self._cowork_confirm_actions:
                        self._sync_event.clear()
                        self.request_action_confirm.emit(desc)
                        self._sync_event.wait(timeout=60.0)
                        if self._stop_requested or not self._confirm_result:
                            action_log.append(f"Skipped by user: {desc}")
                            clean_final = _COWORK_ACT_RE.sub("", turn_text).strip()
                            summary_block = "\n".join(f"- {entry}" for entry in action_log)
                            self.replace_reply.emit(
                                f"**Cowork Actions:**\n{summary_block}\n\n{clean_final or 'Action cancelled.'}"
                            )
                            break

                    self.replace_reply.emit("")
                    self.status_changed.emit(f"Cowork executing: {desc}...")
                    result_msg = modes.execute_cowork_action(act_type, act_arg, screen_w, screen_h)
                    action_log.append(result_msg)
                    time.sleep(0.35)

                    self._sync_event.clear()
                    self.request_screenshot.emit()
                    self._sync_event.wait(timeout=5.0)
                    next_b64 = self._latest_screen_b64

                    payload_messages.append({"role": "assistant", "content": turn_text})
                    followup = {
                        "role": "user",
                        "content": f"[COWORK ACTION EXECUTED]: {result_msg}. Here is the updated screen.",
                    }
                    if next_b64:
                        followup["images"] = [next_b64]
                    payload_messages.append(followup)
                    self.status_changed.emit("Inspecting updated screen...")
                return

            if self._mode == "chat" and self._chat_api_enabled and self._chat_agent is not None:
                self._run_api_tool_loop(
                    payload_messages, self._chat_agent, collected_sources, is_agent_mode=False
                )
                return

            self._stream_single_turn(payload_messages, emit_chunks=True)

        except Exception as e:
            self.failed.emit(str(e))


class TitleGeneratorWorker(QThread):

    title_ready = Signal(str, str, str)

    def __init__(
        self,
        stream_chat,
        base_url,
        model,
        chat_id,
        expected_old_title,
        user_msg,
        assistant_msg,
        keep_alive="5m",
        force=False,
    ):
        super().__init__()
        self._stream_chat = stream_chat
        self._base_url = base_url
        self._model = model
        self._chat_id = chat_id
        self._expected_old_title = expected_old_title
        self._user_msg = user_msg or ""
        self._assistant_msg = assistant_msg or ""
        self._keep_alive = keep_alive
        self._force = bool(force)

    @staticmethod
    def _condense_for_prompt(text, limit=500):
        cleaned = _CODE_FENCE_RE.sub(" [code block] ", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned[:limit]

    @staticmethod
    def _clean_generated_title(raw):
        text = _THINK_BLOCK_RE.sub("", raw or "").strip()
        if not text:
            return ""
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        first_line = re.sub(r"^(?:title\s*:\s*|#+\s*)", "", first_line, flags=re.IGNORECASE)
        first_line = first_line.strip(" \"'`“”‘’*_-")
        first_line = first_line.rstrip(".!?:;")
        first_line = re.sub(r"\s+", " ", first_line).strip()
        if len(first_line) > 56:
            first_line = first_line[:53].rstrip() + "..."
        return first_line

    def run(self):
        user_snippet = self._condense_for_prompt(self._user_msg, limit=500)
        assistant_snippet = self._condense_for_prompt(self._assistant_msg, limit=500)
        if not user_snippet and not assistant_snippet:
            return

        payload = [
            {
                "role": "system",
                "content": (
                    "Create a short, natural 3 to 6 word title summarizing the topic of this conversation. "
                    "Reply with ONLY the title itself—no quotes, no markdown, no prefixes, and no trailing punctuation."
                ),
            },
            {
                "role": "user",
                "content": f"User: {user_snippet}\n\nAssistant: {assistant_snippet}",
            },
        ]

        gen = None
        acc = ""
        try:
            gen = self._stream_chat(
                self._base_url,
                self._model,
                payload,
                options={"temperature": 0.3, "num_predict": 24},
                stream=False,
                keep_alive=self._keep_alive,
                timeout=45,
            )
            for piece in gen:
                acc += piece
        except Exception:
            return
        finally:
            if gen is not None:
                gen.close()

        cleaned_title = self._clean_generated_title(acc)
        if cleaned_title and len(cleaned_title) >= 2:
            expected = "" if self._force else self._expected_old_title
            self.title_ready.emit(self._chat_id, expected, cleaned_title)


class MemoryExtractorWorker(QThread):

    learned = Signal(list)

    def __init__(self, base_url, model, user_msg, assistant_msg):
        super().__init__()
        self._base_url = base_url
        self._model = model
        self._user_msg = user_msg
        self._assistant_msg = assistant_msg

    def run(self):
        saved = memory.extract_memories_with_llm(
            self._base_url, self._model, self._user_msg, self._assistant_msg
        )
        if saved:
            self.learned.emit(saved)


class InputBox(QPlainTextEdit):

    submitted = Signal()

    def __init__(self):
        super().__init__()
        self._min_h = 54
        self._max_h = 160
        self.send_on_enter = True
        self.setFixedHeight(self._min_h)
        self.textChanged.connect(self._adjust_height)

    def _adjust_height(self):
        doc_height = int(self.document().size().height()) + 18
        clamped = max(self._min_h, min(self._max_h, doc_height))
        if self.height() != clamped:
            self.setFixedHeight(clamped)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.send_on_enter:
                if not (event.modifiers() & Qt.ShiftModifier):
                    self.submitted.emit()
                    return
            else:
                if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
                    self.submitted.emit()
                    return
        super().keyPressEvent(event)


class MemoryDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mosaic Memories")
        self.resize(520, 480)
        self.current_settings = settings.load_settings()
        self.setStyleSheet(settings.build_stylesheet(settings.get_palette(self.current_settings)))

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Everything listed here is automatically injected into Mosaic's context so it "
            "remembers your name, preferences, and projects in every chat.\n"
            'Tip: Say "remember that ..." or state facts like "My name is ..." while chatting.'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.auto_cb = QCheckBox("Auto-learn durable facts from conversations (runs quietly after replies)")
        self.auto_cb.setChecked(bool(self.current_settings.get("auto_memory", False)))
        self.auto_cb.toggled.connect(self._toggle_auto_learn)
        layout.addWidget(self.auto_cb)

        self.list = QListWidget()
        self.list.setObjectName("memList")
        self.list.setWordWrap(True)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self._edit_item)
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Add a fact (e.g., User prefers Python 3.12)...")
        self.entry.returnPressed.connect(self._add)
        row.addWidget(self.entry, 1)
        add_btn = QPushButton("Add")
        add_btn.setObjectName("send")
        add_btn.clicked.connect(self._add)
        row.addWidget(add_btn)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn = QPushButton("Delete selected")
        delete_btn.clicked.connect(self._delete)
        clear_btn = QPushButton("Clear all")
        clear_btn.clicked.connect(self._clear)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(edit_btn)
        buttons.addWidget(delete_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._refresh()

    def _toggle_auto_learn(self, checked):
        self.current_settings = settings.save_settings({"auto_memory": bool(checked)})

    def _refresh(self):
        self.list.clear()
        for m in memory.load_memories():
            item = QListWidgetItem(m["text"])
            item.setData(Qt.UserRole, m["id"])
            item.setToolTip("Double-click to edit")
            self.list.addItem(item)

    def _add(self):
        text = self.entry.text().strip()
        if text:
            memory.add_memory(text, category="manual")
            self.entry.clear()
            self._refresh()

    def _edit_item(self, item):
        mem_id = item.data(Qt.UserRole)
        new_text, ok = QInputDialog.getText(
            self, "Edit Memory", "Memory text:", text=item.text()
        )
        if ok and new_text.strip():
            memory.update_memory(mem_id, new_text)
            self._refresh()

    def _edit_selected(self):
        items = self.list.selectedItems()
        if items:
            self._edit_item(items[0])

    def _delete(self):
        for item in self.list.selectedItems():
            memory.delete_memory(item.data(Qt.UserRole))
        self._refresh()

    def _clear(self):
        if not memory.load_memories():
            return
        answer = QMessageBox.question(
            self, "Clear all memories", "Delete everything Mosaic remembers about you?"
        )
        if answer == QMessageBox.Yes:
            memory.clear_memories()
            self._refresh()


class MosaicWindow(QMainWindow):
    def __init__(
        self,
        base_url,
        model,
        build_system_prompt,
        stream_chat,
        list_models,
        ensure_ollama=None,
        search_web=None,
        format_search_context=None,
        bot_name="Mosaic",
    ):
        super().__init__()
        self.app_settings = settings.load_settings()
        self.palette = settings.get_palette(self.app_settings)
        self.base_url = base_url
        self.build_system_prompt = build_system_prompt
        self.stream_chat = stream_chat
        self.list_models = list_models
        self.ensure_ollama = ensure_ollama
        self.search_web = search_web
        self.format_search_context = format_search_context
        self.bot_name = bot_name
        self._preferred_model = model

        if self.search_web is None or self.format_search_context is None:
            try:
                import main as _main_mod

                if self.search_web is None:
                    self.search_web = getattr(_main_mod, "search_web", None)
                if self.format_search_context is None:
                    self.format_search_context = getattr(_main_mod, "format_search_context", None)
            except Exception:
                pass

        self.current_mode = self.app_settings.get("active_mode", "chat")
        if self.current_mode not in ("chat", "agent", "cowork"):
            self.current_mode = "chat"

        self.chat_data = storage.new_chat()
        self.messages = self.chat_data["messages"]
        self.attachments = []
        self.worker = None
        self.mem_worker = None
        self.starter_worker = None
        self._title_workers = []
        self.current_reply = ""
        self._displayed_reply = ""
        self._worker_done = False
        self._finishing_animation = False
        self._stream_status_text = "Thinking..."
        self._last_search_results = []
        self._startup_note = None
        self._pending_memory_notes = []
        self._stream_dirty = False
        self._active_stream_label = None
        self._auto_scroll = True
        self._starter_buttons = []
        self._mode_buttons = {}
        self._connection_state = "pending"

        self.render_timer = QTimer(self)
        self.render_timer.setInterval(18)
        self.render_timer.timeout.connect(self._flush_stream_render)

        self.setWindowTitle(f"{bot_name} — Local AI Studio")
        self.resize(1180, 750)

        self._build_ui()
        self._apply_theme()
        self._switch_mode(self.current_mode, persist=False)
        self._bind_shortcuts()
        self._init_ollama_connection(model)
        self._refresh_sidebar()
        self._render_chat()

    def _is_busy(self):
        return (self.worker is not None and self.worker.isRunning()) or self._finishing_animation

    def _make_chat_font(self):
        font = QFont()
        family = self.app_settings.get("font_family", "System Default")
        if family and family != "System Default":
            font.setFamily(family)
        font.setPointSize(int(self.app_settings.get("font_size", 11)))
        return font

    def _apply_theme(self):
        self.palette = settings.get_palette(self.app_settings)
        p = self.palette
        self.setStyleSheet(settings.build_stylesheet(p))

        for mode_key, btn in self._mode_buttons.items():
            col = p["accent"] if btn.isChecked() else p["text_secondary"]
            btn.setIcon(modes.make_mode_icon(mode_key, color_hex=col, size=22))

        self._sidebar_icon = make_icon("sidebar", color=p["text_secondary"], hover_color=p["accent"])
        self._search_icon = make_icon("search", color=p["text_muted"], hover_color=p["text_secondary"])
        self._pin_icon = make_icon("pin", color=p["yellow"], hover_color=p["yellow"])
        self._folder_icon = make_icon("folder", color=p["accent"], hover_color=p["accent"])
        self._folder_plus_icon = make_icon("folder_plus", color=p["text_secondary"], hover_color=p["accent"])
        self._memory_icon = make_icon("memory", color=p["purple"], hover_color=p["accent"])
        self._settings_icon = make_icon("settings", color=p["text_secondary"], hover_color=p["accent"])
        self._attach_icon = make_icon("attach", color=p["text_secondary"], hover_color=p["accent"])
        self._file_icon = make_icon("file", color=p["accent"], hover_color="#ffffff")
        self._refresh_icon = make_icon("refresh", color=p["text_secondary"], hover_color=p["accent"])
        self._regen_icon = make_icon("refresh", color=p["text_muted"], hover_color=p["text_primary"])
        self._copy_icon = make_icon("copy", color=p["text_muted"], hover_color=p["text_primary"])
        self._check_icon = make_icon("check", color=p["green"], hover_color=p["green"])
        self._edit_icon = make_icon("edit", color=p["text_muted"], hover_color=p["text_primary"])
        self._trash_icon = make_icon("trash", color=p["text_muted"], hover_color=p["red"])
        self._memory_pill_pixmap = make_pixmap("memory", color=p["yellow"], size=15)
        self._globe_on_icon = _make_globe_icon(p["accent"], size=17)
        self._globe_off_icon = _make_globe_icon(p["text_secondary"], size=17)
        self._api_on_icon = _make_api_icon(p["accent"], size=17)
        self._api_off_icon = _make_api_icon(p["text_secondary"], size=17)

        if p["mode"] == "dark":
            self._theme_icon = make_icon("sun", color=p["yellow"], hover_color=p["text_primary"])
            self.theme_btn.setToolTip("Switch to Light Mode")
        else:
            self._theme_icon = make_icon("moon", color=p["text_secondary"], hover_color=p["accent"])
            self.theme_btn.setToolTip("Switch to Dark Mode")

        self.theme_btn.setIcon(self._theme_icon)
        self.toggle_sidebar_btn.setIcon(self._sidebar_icon)
        self.new_folder_btn.setIcon(self._folder_plus_icon)
        self.memory_btn.setIcon(self._memory_icon)
        if hasattr(self, "api_hub_btn"):
            self.api_hub_btn.setIcon(
                self._api_on_icon if self.chat_api_btn.isChecked() else self._api_off_icon
            )
        self.settings_btn.setIcon(self._settings_icon)
        self.attach_btn.setIcon(self._attach_icon)
        self.refresh_models_btn.setIcon(self._refresh_icon)
        self._on_web_toggled(self.web_btn.isChecked())
        self._sync_chat_api_button_ui()

        if hasattr(self, "_search_action"):
            self._search_action.setIcon(self._search_icon)

        for btn, icon_name, col_key in self._starter_buttons:
            btn.setIcon(make_icon(icon_name, color=p[col_key], hover_color=p["accent"]))

        self._update_status_dot()

        compact = bool(self.app_settings.get("compact_mode", False))
        self.chat_layout.setSpacing(8 if compact else 14)

        self.input.send_on_enter = bool(self.app_settings.get("send_on_enter", True))
        self.input.setFont(self._make_chat_font())
        self._update_input_placeholder()

        self._refresh_agent_bar()
        self._refresh_chips()
        self._refresh_sidebar()

    def _update_input_placeholder(self):
        if self.current_mode == "agent":
            ag = modes.get_active_agent()
            self.input.setPlaceholderText(
                f"Message {ag['name']} ({ag['handle']}) — give it a task or ask it to use its private API..."
            )
        elif self.current_mode == "cowork":
            self.input.setPlaceholderText("Tell Mosaic Cowork what to inspect or do on your screen...")
        elif self.input.send_on_enter:
            self.input.setPlaceholderText("Message Mosaic... (Enter to send, Shift+Enter for new line)")
        else:
            self.input.setPlaceholderText("Message Mosaic... (Ctrl+Enter to send, Enter for new line)")

    def _on_web_toggled(self, checked):
        if hasattr(self, "_globe_on_icon"):
            self.web_btn.setIcon(self._globe_on_icon if checked else self._globe_off_icon)
        if checked:
            self.web_btn.setToolTip(
                "Web Search: ON — Ollama can search the internet for this message (Ctrl+Shift+W)"
            )
        else:
            self.web_btn.setToolTip(
                "Web Search: OFF — Click to allow Ollama to search the internet (Ctrl+Shift+W)"
            )

    def _toggle_web_shortcut(self):
        if self.web_btn.isEnabled():
            self.web_btn.toggle()

    def _toggle_chat_api_shortcut(self):
        if self.current_mode == "chat" and self.chat_api_btn.isEnabled():
            self.chat_api_btn.toggle()

    def _sync_chat_api_button_ui(self):
        if not hasattr(self, "chat_api_btn"):
            return
        checked = self.chat_api_btn.isChecked()
        if hasattr(self, "_api_on_icon"):
            self.chat_api_btn.setIcon(self._api_on_icon if checked else self._api_off_icon)
        svc_key = self.app_settings.get("chat_api_service", "none")
        svc_label = (
            EXTRA_API_SERVICES[svc_key]["short"]
            if svc_key in EXTRA_API_SERVICES
            else modes.SERVICE_SPECS.get(svc_key, {}).get("short", svc_key)
        )
        key_preview = (
            "No Key Required"
            if svc_key in KEYLESS_SERVICES
            else modes.mask_api_key(self.app_settings.get("chat_api_key", ""))
        )
        base_url = (self.app_settings.get("chat_api_base_url") or "").strip()
        url_part = f" • {base_url}" if base_url and svc_key not in KEYLESS_SERVICES else ""
        if hasattr(self, "api_hub_btn"):
            if checked and svc_key not in ("", "none"):
                self.api_hub_btn.setText(f"  APIs ({svc_label})")
                if hasattr(self, "_api_on_icon"):
                    self.api_hub_btn.setIcon(self._api_on_icon)
            else:
                self.api_hub_btn.setText("  APIs & Tools")
                if hasattr(self, "_api_off_icon"):
                    self.api_hub_btn.setIcon(self._api_off_icon)
        if checked and svc_key not in ("", "none"):
            self.chat_api_btn.setToolTip(
                f"Chat API Access: ON ({svc_label}{url_part} • {key_preview}) — Click to toggle, Right-click to open API Studio (Ctrl+Shift+A)"
            )
        else:
            self.chat_api_btn.setToolTip(
                "Chat API Access: OFF — Click to enable or open API & Integrations Studio (Ctrl+Shift+A)"
            )

    def _on_chat_api_toggled(self, checked):
        svc = self.app_settings.get("chat_api_service", "none")
        base_url = (self.app_settings.get("chat_api_base_url") or "").strip()
        if checked and (svc in ("", "none") or (svc == "custom" and not base_url)):
            self.chat_api_btn.blockSignals(True)
            self.chat_api_btn.setChecked(False)
            self.chat_api_btn.blockSignals(False)
            self._sync_chat_api_button_ui()
            self._open_api_hub()
            return
        self.app_settings = settings.save_settings({"chat_api_enabled": bool(checked)})
        self._sync_chat_api_button_ui()
        if not self.messages and not self._is_busy():
            self._render_chat()

    def _chat_api_btn_menu(self, pos):
        menu = QMenu(self)
        cfg_act = menu.addAction("Open API & Integrations Studio...")
        chosen = menu.exec(self.chat_api_btn.mapToGlobal(pos))
        if chosen == cfg_act:
            self._open_api_hub()

    def _build_chat_mode_agent(self, cfg=None):
        data = cfg if cfg is not None else self.app_settings
        service_type = data.get("chat_api_service", "none") or "none"
        api_key = (data.get("chat_api_key") or "").strip()
        base_url = (data.get("chat_api_base_url") or "").strip().rstrip("/")
        confirm = bool(data.get("chat_api_confirm", False))
        return {
            "id": "chat_mode_api",
            "name": self.bot_name,
            "handle": "@mosaic",
            "avatar_color": self.palette.get("accent", "#4f8cff"),
            "avatar_badge": "orbit",
            "service_type": service_type,
            "api_key": api_key,
            "base_url": base_url,
            "custom_base_url": base_url,
            "api_base_url": base_url,
            "boundary_mode": "confirm" if confirm else "auto",
            "personality": "Helpful, direct, conversational AI assistant.",
            "instructions": (
                "Assist the user directly in Chat Mode. Whenever their request needs live data or actions "
                "from your connected API service, invoke the appropriate [[CALL_API: tool_id | arg]] tool "
                "and then summarize the result clearly."
            ),
            "standing_mission": "",
            "notes": [],
        }

    def _update_status_dot(self):
        p = self.palette
        color_map = {
            "online": p["green"],
            "offline": p["red"],
            "pending": p["yellow"],
        }
        col = color_map.get(self._connection_state, p["yellow"])
        self.status_dot.setStyleSheet(f"background: {col}; border-radius: 4px;")

    def _quick_toggle_theme(self):
        next_mode = "dark" if self.palette["mode"] == "light" else "light"
        self.app_settings = settings.save_settings({"theme": next_mode})
        self._apply_theme()
        self._render_chat()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 1. Narrow leftmost Mode Rail sidebar
        self.mode_rail = QWidget()
        self.mode_rail.setObjectName("modeRail")
        self.mode_rail.setFixedWidth(68)
        rail_lay = QVBoxLayout(self.mode_rail)
        rail_lay.setContentsMargins(6, 14, 6, 14)
        rail_lay.setSpacing(8)

        for idx, (mode_key, label, tooltip) in enumerate(modes.MODE_SPECS, start=1):
            btn = QToolButton()
            btn.setObjectName("modeRailBtn")
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setText(label)
            btn.setIconSize(QSize(22, 22))
            btn.setFixedSize(56, 58)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"{label} Mode (Ctrl+{idx})\n{tooltip}")
            btn.clicked.connect(lambda checked=False, mk=mode_key: self._switch_mode(mk))
            self._mode_buttons[mode_key] = btn
            rail_lay.addWidget(btn, 0, Qt.AlignHCenter)

        rail_lay.addStretch(1)
        outer.addWidget(self.mode_rail)

        # 2. Chat History Sidebar
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(265)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 16, 14, 14)
        side.setSpacing(10)

        brand_row = QHBoxLayout()
        brand = QLabel(self.bot_name)
        brand.setObjectName("brand")
        self.mode_badge = QLabel("CHAT")
        self.mode_badge.setObjectName("brandBadge")
        brand_row.addWidget(brand)
        brand_row.addWidget(self.mode_badge)
        brand_row.addStretch()
        side.addLayout(brand_row)

        self.new_btn = QPushButton("+  New Chat")
        self.new_btn.setObjectName("newChat")
        self.new_btn.setToolTip("Start a new conversation (Ctrl+N)")
        self.new_btn.clicked.connect(self._new_chat)
        side.addWidget(self.new_btn)

        # Mosaic Agents Section (placed right under + New Chat and above Chats)
        self.agent_bar = QFrame()
        self.agent_bar.setObjectName("modeContextBar")
        agent_outer = QVBoxLayout(self.agent_bar)
        agent_outer.setContentsMargins(8, 8, 8, 8)
        agent_outer.setSpacing(6)

        agent_hdr_row = QHBoxLayout()
        agent_hdr_row.setContentsMargins(2, 0, 0, 0)
        agent_hdr_row.setSpacing(4)
        agents_lbl = QLabel("Agents")
        agents_lbl.setObjectName("settingTitle")
        agent_hdr_row.addWidget(agents_lbl)
        agent_hdr_row.addStretch()

        self.run_mission_btn = QPushButton("Mission")
        self.run_mission_btn.setFixedHeight(24)
        self.run_mission_btn.setStyleSheet("padding: 2px 7px; font-size: 11px;")
        self.run_mission_btn.setToolTip("Execute this Mosaic Agent's standing mission immediately")
        self.run_mission_btn.clicked.connect(self._run_active_agent_mission)
        agent_hdr_row.addWidget(self.run_mission_btn)

        self.edit_agent_btn = QPushButton("Edit")
        self.edit_agent_btn.setFixedHeight(24)
        self.edit_agent_btn.setStyleSheet("padding: 2px 7px; font-size: 11px;")
        self.edit_agent_btn.setToolTip("Edit personality, instructions, and API settings for this agent")
        self.edit_agent_btn.clicked.connect(self._edit_active_agent)
        agent_hdr_row.addWidget(self.edit_agent_btn)

        self.new_agent_btn = QPushButton("+ New")
        self.new_agent_btn.setObjectName("send")
        self.new_agent_btn.setFixedHeight(24)
        self.new_agent_btn.setStyleSheet("padding: 2px 8px; font-size: 11px; border-radius: 6px;")
        self.new_agent_btn.setToolTip("Create a new Mosaic Agent with its own custom bot icon and API")
        self.new_agent_btn.clicked.connect(self._create_new_agent)
        agent_hdr_row.addWidget(self.new_agent_btn)
        agent_outer.addLayout(agent_hdr_row)

        self.agent_cards_scroll = QScrollArea()
        self.agent_cards_scroll.setWidgetResizable(True)
        self.agent_cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.agent_cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.agent_cards_scroll.setFrameShape(QFrame.NoFrame)
        self.agent_cards_scroll.setStyleSheet("background: transparent;")

        self.agent_cards_host = QWidget()
        self.agent_cards_host.setStyleSheet("background: transparent;")
        self.agent_cards_layout = QVBoxLayout(self.agent_cards_host)
        self.agent_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.agent_cards_layout.setSpacing(5)
        self.agent_cards_scroll.setWidget(self.agent_cards_host)
        agent_outer.addWidget(self.agent_cards_scroll)

        self.agent_status_lbl = QLabel("")
        self.agent_status_lbl.setObjectName("muted")
        self.agent_status_lbl.setWordWrap(True)
        self.agent_status_lbl.setStyleSheet("font-size: 11px; padding-left: 2px;")
        agent_outer.addWidget(self.agent_status_lbl)

        self.agent_bar.setVisible(False)
        side.addWidget(self.agent_bar)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search chats... (Ctrl+F)")
        self._search_action = self.search_box.addAction(
            make_icon("search"), QLineEdit.LeadingPosition
        )
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._refresh_sidebar)
        side.addWidget(self.search_box)

        chats_hdr_row = QHBoxLayout()
        chats_hdr_row.setContentsMargins(0, 0, 0, 0)
        self.chats_header = QLabel("Chats")
        self.chats_header.setObjectName("muted")
        self.new_folder_btn = QPushButton()
        self.new_folder_btn.setObjectName("miniBtn")
        self.new_folder_btn.setIconSize(QSize(15, 15))
        self.new_folder_btn.setFixedSize(24, 24)
        self.new_folder_btn.setToolTip("Create new folder")
        self.new_folder_btn.clicked.connect(self._create_folder)
        chats_hdr_row.addWidget(self.chats_header)
        chats_hdr_row.addStretch()
        chats_hdr_row.addWidget(self.new_folder_btn)
        side.addLayout(chats_hdr_row)

        self.chat_list = QListWidget()
        self.chat_list.setObjectName("chatList")
        self.chat_list.setIconSize(QSize(15, 15))
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._chat_menu)
        self.chat_list.itemClicked.connect(self._on_chat_clicked)
        side.addWidget(self.chat_list, 1)

        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFrameShape(QFrame.HLine)
        side.addWidget(divider)

        self.memory_btn = QPushButton("  Memories (0)")
        self.memory_btn.setObjectName("sidebarFooterBtn")
        self.memory_btn.setIconSize(QSize(17, 17))
        self.memory_btn.setCursor(Qt.PointingHandCursor)
        self.memory_btn.setToolTip("Manage saved memories")
        self.memory_btn.clicked.connect(self._open_memories)
        side.addWidget(self.memory_btn)

        self.api_hub_btn = QPushButton("  APIs & Tools")
        self.api_hub_btn.setObjectName("sidebarFooterBtn")
        self.api_hub_btn.setIconSize(QSize(17, 17))
        self.api_hub_btn.setCursor(Qt.PointingHandCursor)
        self.api_hub_btn.setToolTip("Open API & Integrations Studio (Ctrl+Shift+I)")
        self.api_hub_btn.clicked.connect(self._open_api_hub)
        side.addWidget(self.api_hub_btn)

        self.settings_btn = QPushButton("  Settings")
        self.settings_btn.setObjectName("sidebarFooterBtn")
        self.settings_btn.setIconSize(QSize(17, 17))
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip("Open Mosaic Settings (Ctrl+,)")
        self.settings_btn.clicked.connect(self._open_settings)
        side.addWidget(self.settings_btn)

        outer.addWidget(self.sidebar)

        # 3. Main Workspace
        main = QWidget()
        column = QVBoxLayout(main)
        column.setContentsMargins(18, 14, 18, 16)
        column.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.toggle_sidebar_btn = QPushButton()
        self.toggle_sidebar_btn.setObjectName("iconBtn")
        self.toggle_sidebar_btn.setIconSize(QSize(18, 18))
        self.toggle_sidebar_btn.setFixedSize(34, 34)
        self.toggle_sidebar_btn.setToolTip("Toggle chat history sidebar (Ctrl+B)")
        self.toggle_sidebar_btn.clicked.connect(self._toggle_sidebar)
        top.addWidget(self.toggle_sidebar_btn)

        self.title_label = QLabel("New chat")
        self.title_label.setObjectName("chatTitle")
        top.addWidget(self.title_label)
        top.addStretch()

        self.status_dot = QFrame()
        self.status_dot.setFixedSize(9, 9)
        top.addWidget(self.status_dot)

        self.model_box = QComboBox()
        self.model_box.currentTextChanged.connect(self._on_model_changed)
        top.addWidget(self.model_box)

        self.refresh_models_btn = QPushButton()
        self.refresh_models_btn.setObjectName("iconBtn")
        self.refresh_models_btn.setIconSize(QSize(17, 17))
        self.refresh_models_btn.setFixedSize(34, 34)
        self.refresh_models_btn.setToolTip("Start/Refresh Ollama models")
        self.refresh_models_btn.clicked.connect(
            lambda: self._init_ollama_connection(self.model_box.currentText())
        )
        top.addWidget(self.refresh_models_btn)

        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("iconBtn")
        self.theme_btn.setIconSize(QSize(17, 17))
        self.theme_btn.setFixedSize(34, 34)
        self.theme_btn.clicked.connect(self._quick_toggle_theme)
        top.addWidget(self.theme_btn)

        column.addLayout(top)

        # Cowork Mode Context Bar
        self.cowork_bar = QFrame()
        self.cowork_bar.setObjectName("modeContextBar")
        cowork_lay = QHBoxLayout(self.cowork_bar)
        cowork_lay.setContentsMargins(12, 8, 12, 8)
        cowork_lay.setSpacing(12)

        self.screen_thumb_lbl = QLabel()
        self.screen_thumb_lbl.setFixedSize(96, 54)
        self.screen_thumb_lbl.setAlignment(Qt.AlignCenter)
        self.screen_thumb_lbl.setStyleSheet("border: 1px solid #64748b; border-radius: 4px;")
        cowork_lay.addWidget(self.screen_thumb_lbl)

        cw_info_col = QVBoxLayout()
        cw_info_col.setSpacing(4)
        self.cowork_title_lbl = QLabel("Cowork Mode — Screen Vision & Cursor Control")
        self.cowork_title_lbl.setObjectName("settingTitle")
        cw_info_col.addWidget(self.cowork_title_lbl)

        cw_toggles = QHBoxLayout()
        cw_toggles.setSpacing(14)
        self.cw_vision_cb = QCheckBox("See Screen")
        self.cw_vision_cb.setChecked(bool(self.app_settings.get("cowork_allow_vision", True)))
        self.cw_vision_cb.toggled.connect(
            lambda v: settings.save_settings({"cowork_allow_vision": bool(v)})
        )

        self.cw_cursor_cb = QCheckBox("Control Cursor & Keys")
        self.cw_cursor_cb.setChecked(bool(self.app_settings.get("cowork_allow_cursor", True)))
        self.cw_cursor_cb.toggled.connect(
            lambda v: settings.save_settings({"cowork_allow_cursor": bool(v)})
        )

        self.cw_confirm_cb = QCheckBox("Confirm Before Clicks")
        self.cw_confirm_cb.setChecked(bool(self.app_settings.get("cowork_confirm_actions", True)))
        self.cw_confirm_cb.toggled.connect(
            lambda v: settings.save_settings({"cowork_confirm_actions": bool(v)})
        )

        cw_toggles.addWidget(self.cw_vision_cb)
        cw_toggles.addWidget(self.cw_cursor_cb)
        cw_toggles.addWidget(self.cw_confirm_cb)
        cw_toggles.addStretch()
        cw_info_col.addLayout(cw_toggles)
        cowork_lay.addLayout(cw_info_col, 1)

        self.cw_capture_btn = QPushButton("Capture Preview")
        self.cw_capture_btn.clicked.connect(self._refresh_cowork_preview)
        cowork_lay.addWidget(self.cw_capture_btn)

        self.cowork_bar.setVisible(False)
        column.addWidget(self.cowork_bar)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.chat_container = QWidget()
        self.chat_container.setObjectName("chatContainer")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(16, 16, 16, 16)
        self.chat_layout.setSpacing(14)
        self.chat_layout.addStretch(1)

        self.chat_scroll.setWidget(self.chat_container)
        vbar = self.chat_scroll.verticalScrollBar()
        vbar.rangeChanged.connect(self._on_scroll_range_changed)
        vbar.valueChanged.connect(self._on_scroll_value_changed)

        column.addWidget(self.chat_scroll, 1)

        self.starter_panel = QWidget()
        starter_layout = QVBoxLayout(self.starter_panel)
        starter_layout.setContentsMargins(0, 0, 0, 4)
        starter_layout.setSpacing(6)
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        for idx in range(4):
            btn = QPushButton()
            btn.setObjectName("promptCard")
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self._use_starter_idx(i))
            self._starter_buttons.append([btn, "bulb", "accent"])
            (row1 if idx < 2 else row2).addWidget(btn, 1)
        starter_layout.addLayout(row1)
        starter_layout.addLayout(row2)
        self._apply_starter_prompts_for_mode()
        column.addWidget(self.starter_panel)

        self.chip_bar = QWidget()
        self.chip_layout = QHBoxLayout(self.chip_bar)
        self.chip_layout.setContentsMargins(0, 0, 0, 0)
        self.chip_layout.setSpacing(6)
        self.chip_bar.setVisible(False)
        column.addWidget(self.chip_bar)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self.attach_btn = QPushButton()
        self.attach_btn.setObjectName("iconBtn")
        self.attach_btn.setIconSize(QSize(19, 19))
        self.attach_btn.setFixedSize(46, 54)
        self.attach_btn.setToolTip("Attach a code or text file")
        self.attach_btn.clicked.connect(self._attach_file)
        bottom.addWidget(self.attach_btn, 0, Qt.AlignBottom)

        self.input = InputBox()
        self.input.submitted.connect(self._on_send_clicked)
        bottom.addWidget(self.input, 1, Qt.AlignBottom)

        self.chat_api_btn = QPushButton("API")
        self.chat_api_btn.setObjectName("webSearchBtn")
        self.chat_api_btn.setCheckable(True)
        self.chat_api_btn.setIconSize(QSize(17, 17))
        self.chat_api_btn.setFixedHeight(54)
        self.chat_api_btn.setMinimumWidth(72)
        self.chat_api_btn.setCursor(Qt.PointingHandCursor)
        self.chat_api_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_api_btn.customContextMenuRequested.connect(self._chat_api_btn_menu)
        self.chat_api_btn.setChecked(
            bool(
                self.app_settings.get("chat_api_enabled", False)
                and self.app_settings.get("chat_api_service", "none") not in ("", "none")
            )
        )
        self.chat_api_btn.toggled.connect(self._on_chat_api_toggled)
        bottom.addWidget(self.chat_api_btn, 0, Qt.AlignBottom)

        self.web_btn = QPushButton("Web")
        self.web_btn.setObjectName("webSearchBtn")
        self.web_btn.setCheckable(True)
        self.web_btn.setIconSize(QSize(17, 17))
        self.web_btn.setFixedHeight(54)
        self.web_btn.setMinimumWidth(78)
        self.web_btn.setCursor(Qt.PointingHandCursor)
        self.web_btn.setChecked(bool(self.app_settings.get("web_search_always_on", False)))
        self.web_btn.toggled.connect(self._on_web_toggled)
        bottom.addWidget(self.web_btn, 0, Qt.AlignBottom)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("send")
        self.send_btn.setFixedHeight(54)
        self.send_btn.setMinimumWidth(92)
        self.send_btn.clicked.connect(self._on_send_clicked)
        bottom.addWidget(self.send_btn, 0, Qt.AlignBottom)

        column.addLayout(bottom)

        outer.addWidget(main, 1)
        self.input.setFocus()
        self._update_memory_button()

    def _switch_mode(self, mode_key, persist=True):
        if self._is_busy():
            return
        if mode_key not in ("chat", "agent", "cowork"):
            mode_key = "chat"
        self.current_mode = mode_key
        if persist:
            self.app_settings = settings.save_settings({"active_mode": mode_key})

        p = self.palette
        for mk, btn in self._mode_buttons.items():
            active = mk == mode_key
            btn.setChecked(active)
            btn.setIcon(
                modes.make_mode_icon(
                    mk, color_hex=p["accent"] if active else p["text_secondary"], size=22
                )
            )

        self.mode_badge.setText("MOSAIC AGENT" if mode_key == "agent" else mode_key.upper())
        self.agent_bar.setVisible(mode_key == "agent")
        self.cowork_bar.setVisible(mode_key == "cowork")
        if hasattr(self, "chat_api_btn"):
            self.chat_api_btn.setVisible(mode_key == "chat")

        if mode_key == "agent":
            self._refresh_agent_bar()
        elif mode_key == "cowork":
            self._refresh_cowork_preview()

        self._apply_starter_prompts_for_mode()
        self._update_input_placeholder()
        if not self.messages:
            self._render_chat()

    def _get_agent_starter_prompts(self):
        ag = modes.get_active_agent()
        stype = ag.get("service_type", "none")
        mission = ag.get("standing_mission") or "Run your standing mission and summarize what you find."
        prompts = [
            ("sparkle", "accent", "Run Standing Mission", mission),
        ]
        if stype == "github":
            prompts.extend([
                ("code", "green", "Audit my repositories", "List my GitHub repositories and summarize what each one is for."),
                ("user", "purple", "Check GitHub profile", "Check my GitHub profile, username, and repository counts."),
                ("bulb", "yellow", "Save key finding", "Inspect my latest repository and save a summary note to your agent memory."),
            ])
        elif stype == "youtube":
            prompts.extend([
                ("search", "green", "Search YouTube", "Search YouTube for the latest tutorials in my topic area and summarize them."),
                ("bulb", "purple", "Generate Markdown brief", "Find top videos on Python automation and write a Markdown report."),
                ("sparkle", "yellow", "Save research note", "Save the best channel recommendations to your persistent agent memory."),
            ])
        elif stype == "google_drive":
            prompts.extend([
                ("search", "green", "Scan recent Drive files", "List my most recently modified Google Drive files and summarize them."),
                ("bulb", "purple", "Find project notes", "Search my Google Drive for project notes and extract key action items."),
                ("code", "yellow", "Write summary report", "Summarize my recent Drive documents into a clean Markdown report."),
            ])
        elif stype == "notion":
            prompts.extend([
                ("search", "green", "Search Notion pages", "Search my Notion workspace for recent pages and summarize key items."),
                ("bulb", "purple", "Extract action items", "Check my Notion roadmap pages and list the top priorities."),
                ("code", "yellow", "Save agent note", "Save the key milestones from Notion into your agent memory."),
            ])
        elif stype == "weather":
            prompts.extend([
                ("bulb", "green", "Check Melbourne weather", "What is the current weather and temperature in Melbourne right now?"),
                ("search", "purple", "Compare city weather", "Check the current weather in Sydney and compare it with Melbourne."),
                ("sparkle", "yellow", "Save weather note", "Check Melbourne's temperature and save a note in your agent memory."),
            ])
        elif stype == "free_news":
            prompts.extend([
                ("bulb", "green", "Top world headlines", "Get the top live news headlines right now and summarize the biggest stories."),
                ("search", "purple", "Latest tech & AI news", "Fetch the latest news about technology and artificial intelligence and summarize key highlights."),
                ("sparkle", "yellow", "Save news brief to notes", "Find today's top science or tech headlines and save a concise summary note to your agent memory."),
            ])
        elif stype == "gmail":
            prompts.extend([
                ("search", "green", "Check unread emails", "Search my Gmail for unread messages (is:unread) and summarize who they are from."),
                ("bulb", "purple", "Find important threads", "Search my Gmail inbox for recent important messages and list any action items."),
                ("sparkle", "yellow", "List Gmail labels", "List all my Gmail labels and folders."),
            ])
        elif stype == "google_calendar":
            prompts.extend([
                ("search", "green", "Upcoming schedule", "Check my upcoming Google Calendar events and summarize my schedule."),
                ("bulb", "purple", "Quick-add event", "Quick-add a calendar event: Project review tomorrow at 2pm."),
                ("sparkle", "yellow", "Search calendar", "Search my Google Calendar for meetings this week."),
            ])
        elif stype == "slack":
            prompts.extend([
                ("search", "green", "List Slack channels", "List all Slack channels in my workspace with their channel IDs."),
                ("bulb", "purple", "Summarize channel updates", "Check my Slack channels and help summarize recent activity."),
                ("sparkle", "yellow", "Save workspace note", "Save the main Slack channel IDs to your agent memory."),
            ])
        elif stype == "discord":
            prompts.extend([
                ("search", "green", "List Discord servers", "List the Discord servers (guilds) connected to my bot."),
                ("bulb", "purple", "Send Discord update", "Send a status update message to my Discord webhook or channel."),
                ("sparkle", "yellow", "Save channel note", "Save my primary Discord channel ID to your agent memory."),
            ])
        elif stype == "trello":
            prompts.extend([
                ("search", "green", "List Trello boards", "List all of my active Trello boards and their board IDs."),
                ("bulb", "purple", "Review board cards", "Inspect my Trello boards and help organize upcoming tasks."),
                ("sparkle", "yellow", "Save board IDs", "Save my main Trello board IDs to your agent memory."),
            ])
        elif stype == "linear":
            prompts.extend([
                ("search", "green", "Recent Linear issues", "Fetch my recent Linear issues and summarize their current status."),
                ("bulb", "purple", "List Linear teams", "List all Linear teams and their team IDs."),
                ("sparkle", "yellow", "Sprint triage summary", "Review recent Linear issues and highlight top blockers."),
            ])
        elif stype == "spotify":
            prompts.extend([
                ("bulb", "green", "What's playing now?", "Check what track is currently playing on my Spotify account."),
                ("search", "purple", "My top tracks", "Fetch my top played Spotify tracks and analyze my music taste."),
                ("sparkle", "yellow", "Search music", "Search Spotify for focus instrumental tracks."),
            ])
        elif stype == "reddit":
            prompts.extend([
                ("bulb", "green", "Hot in r/technology", "Fetch the top hot posts from r/technology and summarize key discussions."),
                ("search", "purple", "Search Reddit topics", "Search Reddit for local LLM news and summarize what people are saying."),
                ("sparkle", "yellow", "Hot in r/python", "Check hot posts in r/python and highlight useful tools."),
            ])
        elif stype == "wikipedia":
            prompts.extend([
                ("search", "green", "Look up a concept", "Search Wikipedia for Quantum computing and give me a clear summary."),
                ("bulb", "purple", "Historical overview", "Fetch the Wikipedia summary for the Apollo 11 mission."),
                ("sparkle", "yellow", "Save research summary", "Summarize the Wikipedia article on Neural networks and save key points to memory."),
            ])
        elif stype == "arxiv":
            prompts.extend([
                ("search", "green", "Latest AI papers", "Search arXiv for recent papers on reasoning language models and summarize them."),
                ("bulb", "purple", "Find physics preprints", "Search arXiv for quantum error correction papers."),
                ("sparkle", "yellow", "Save paper digest", "Find top arXiv papers on multimodal agents and save a digest to memory."),
            ])
        elif stype == "crypto":
            prompts.extend([
                ("bulb", "green", "BTC, ETH & SOL prices", "Get the live USD and AUD prices and 24h changes for Bitcoin, Ethereum, and Solana."),
                ("search", "purple", "Trending coins", "Check which cryptocurrencies are trending right now on CoinGecko."),
                ("sparkle", "yellow", "Market snapshot note", "Check live Bitcoin and Ethereum prices and save a snapshot note."),
            ])
        elif stype == "currency":
            prompts.extend([
                ("bulb", "green", "Convert 100 USD to AUD", "Convert 100 USD to AUD using live foreign exchange rates."),
                ("search", "purple", "Major AUD exchange rates", "Show live exchange rates for 1 AUD against USD, EUR, GBP, and JPY."),
                ("sparkle", "yellow", "Convert 250 EUR to USD", "Convert 250 EUR to USD at the current live rate."),
            ])
        else:
            prompts.extend([
                ("bulb", "green", "Execute role task", "Carry out your core instructions and produce a structured summary."),
                ("code", "purple", "Write Markdown report", "Generate a clean Markdown report based on our current topic."),
                ("sparkle", "yellow", "Save memory note", "Save the key takeaway from this conversation to your agent memory."),
            ])
        return prompts[:4]

    def _apply_starter_prompts_for_mode(self):
        p = self.palette
        if self.current_mode == "agent":
            prompts = self._get_agent_starter_prompts()
        else:
            prompts = MODE_STARTER_PROMPTS.get(self.current_mode, MODE_STARTER_PROMPTS["chat"])

        for idx, (icon_name, col_key, label, full_prompt) in enumerate(prompts):
            if idx < len(self._starter_buttons):
                btn = self._starter_buttons[idx][0]
                self._starter_buttons[idx][1] = icon_name
                self._starter_buttons[idx][2] = col_key
                btn.setText(f"  {label}")
                btn.setToolTip(full_prompt)
                btn.setIcon(make_icon(icon_name, color=p[col_key], hover_color=p["accent"]))

    def _use_starter_idx(self, idx):
        if self.current_mode == "agent":
            prompts = self._get_agent_starter_prompts()
        else:
            prompts = MODE_STARTER_PROMPTS.get(self.current_mode, MODE_STARTER_PROMPTS["chat"])
        if 0 <= idx < len(prompts):
            self.input.setPlainText(prompts[idx][3])
            self._send()

    def _refresh_agent_bar(self):
        if not hasattr(self, "agent_cards_layout"):
            return
        while self.agent_cards_layout.count():
            item = self.agent_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        p = self.palette
        agents_list = modes.list_agents()
        active_ag = modes.get_active_agent()

        for ag in agents_list:
            is_active = ag["id"] == active_ag["id"]
            stype = (ag.get("service_type") or "none").strip().lower()
            svc_tag = (
                EXTRA_API_SERVICES[stype]["short"]
                if stype in EXTRA_API_SERVICES
                else modes.get_agent_service_summary(ag)
            )
            accent_col = ag.get("avatar_color", p["accent"])

            card_btn = QPushButton()
            card_btn.setFixedHeight(42)
            card_btn.setCursor(Qt.PointingHandCursor)
            card_btn.setContextMenuPolicy(Qt.CustomContextMenu)
            card_btn.customContextMenuRequested.connect(
                lambda pos, btn=card_btn, aid=ag["id"]: self._agent_card_menu(btn, pos, aid)
            )
            card_btn.setToolTip(
                f"{ag['name']} ({ag['handle']})\n"
                f"Personality: {ag.get('personality') or 'Default'}\n"
                f"Service: {svc_tag}\n"
                "Right-click to change icon shape or color"
            )
            if is_active:
                card_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {p['bg_elevated']}; color: {p['text_primary']}; "
                    f"border: 1.5px solid {accent_col}; border-radius: 9px; padding: 0px; text-align: left; }}"
                )
            else:
                card_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {p['bg_card']}; color: {p['text_secondary']}; "
                    f"border: 1px solid {p['border']}; border-radius: 9px; padding: 0px; text-align: left; }}"
                    f"QPushButton:hover {{ border-color: {accent_col}; background-color: {p['bg_elevated']}; }}"
                )

            card_lay = QHBoxLayout(card_btn)
            card_lay.setContentsMargins(7, 4, 8, 4)
            card_lay.setSpacing(8)

            icon_lbl = QLabel()
            icon_lbl.setFixedSize(28, 28)
            icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            icon_lbl.setPixmap(_make_custom_agent_icon(ag, size=28, is_active=is_active).pixmap(28, 28))
            card_lay.addWidget(icon_lbl)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(1)

            name_lbl = QLabel(ag["name"])
            name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            name_lbl.setStyleSheet(
                f"color: {p['text_primary'] if is_active else p['text_secondary']}; "
                f"font-weight: {'bold' if is_active else '600'}; font-size: 12px; background: transparent;"
            )
            sub_lbl = QLabel(svc_tag)
            sub_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            sub_lbl.setStyleSheet(
                f"color: {p['text_muted']}; font-size: 10px; background: transparent;"
            )
            text_col.addWidget(name_lbl)
            text_col.addWidget(sub_lbl)
            card_lay.addLayout(text_col, 1)

            if is_active:
                dot = QFrame()
                dot.setFixedSize(7, 7)
                dot.setAttribute(Qt.WA_TransparentForMouseEvents)
                dot.setStyleSheet(f"background-color: {accent_col}; border-radius: 3px;")
                card_lay.addWidget(dot)

            card_btn.clicked.connect(lambda checked=False, aid=ag["id"]: self._select_mosaic_agent(aid))
            self.agent_cards_layout.addWidget(card_btn)

        # Dynamically size scroll container so up to 3 agents show cleanly without wasting sidebar space
        visible_rows = max(1, min(len(agents_list), 3))
        self.agent_cards_scroll.setFixedHeight(visible_rows * 47 - 3)

        stype = active_ag.get("service_type", "none")
        notes_count = len(active_ag.get("notes", []))
        if stype in KEYLESS_SERVICES:
            key_info = "No Account / Key"
        else:
            key_info = f"Key: {modes.mask_api_key(active_ag.get('api_key', ''))}"
        self.agent_status_lbl.setText(
            f"{active_ag['handle']} • {key_info} • {notes_count} notes"
        )
        self.run_mission_btn.setEnabled(bool(active_ag.get("standing_mission")))

    def _agent_card_menu(self, card_btn, pos, agent_id):
        ag = modes.get_agent(agent_id)
        if not isinstance(ag, dict):
            return
        cur_color = (ag.get("avatar_color") or "#4f8cff").strip()
        cur_shape = _resolve_agent_shape(ag)

        menu = QMenu(self)
        shape_menu = menu.addMenu("Icon Shape")
        shape_actions = {}
        for shape_key, shape_label in AGENT_ICON_SHAPES:
            preview_icon = _make_custom_agent_icon(
                {"avatar_color": cur_color, "avatar_badge": shape_key},
                size=18,
                is_active=(shape_key == cur_shape),
            )
            act = shape_menu.addAction(preview_icon, shape_label)
            act.setCheckable(True)
            act.setChecked(shape_key == cur_shape)
            shape_actions[act] = shape_key

        color_menu = menu.addMenu("Icon Color")
        color_actions = {}
        for hex_col, col_name in AGENT_ICON_COLORS:
            act = color_menu.addAction(_make_color_swatch_icon(hex_col, size=14), col_name)
            act.setCheckable(True)
            act.setChecked(hex_col.lower() == cur_color.lower())
            color_actions[act] = hex_col
        color_menu.addSeparator()
        custom_color_act = color_menu.addAction("Custom Color...")

        menu.addSeparator()
        edit_act = menu.addAction("Edit Agent...")

        chosen = menu.exec(card_btn.mapToGlobal(pos))
        if chosen is None:
            return

        if chosen in shape_actions:
            _save_agent_appearance(agent_id, shape=shape_actions[chosen])
            self._refresh_agent_bar()
            if not self.messages:
                self._render_chat()
        elif chosen in color_actions:
            _save_agent_appearance(agent_id, color=color_actions[chosen])
            self._refresh_agent_bar()
            if not self.messages:
                self._render_chat()
        elif chosen == custom_color_act:
            picked = QColorDialog.getColor(QColor(cur_color), self, f"Choose Color for {ag['name']}")
            if picked.isValid():
                _save_agent_appearance(agent_id, color=picked.name())
                self._refresh_agent_bar()
                if not self.messages:
                    self._render_chat()
        elif chosen == edit_act:
            modes.set_active_agent(agent_id)
            self._refresh_agent_bar()
            self._edit_active_agent()

    def _enhance_agent_editor_dialog(self, dlg, agent=None):
        """Inject live geometric shape & color pickers and Free News keyless handling into the editor."""
        p = self.palette
        init_color = (
            (agent.get("avatar_color") if isinstance(agent, dict) else None)
            or "#4f8cff"
        ).strip()
        init_shape = _resolve_agent_shape(agent) if isinstance(agent, dict) else "hexagon"
        state = {"color": init_color, "shape": init_shape}

        # Build custom Icon Shape & Color card
        appearance_card = QFrame(dlg)
        appearance_card.setObjectName("settingsCard")
        card_lay = QVBoxLayout(appearance_card)
        card_lay.setContentsMargins(12, 10, 12, 10)
        card_lay.setSpacing(8)

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(10)

        preview_lbl = QLabel()
        preview_lbl.setFixedSize(44, 44)
        hdr_row.addWidget(preview_lbl)

        hdr_text_col = QVBoxLayout()
        hdr_text_col.setSpacing(2)
        title_lbl = QLabel("Custom Geometric Icon & Color")
        title_lbl.setObjectName("settingTitle")
        sub_lbl = QLabel("Pick a geometric shape and customize its accent color")
        sub_lbl.setObjectName("muted")
        hdr_text_col.addWidget(title_lbl)
        hdr_text_col.addWidget(sub_lbl)
        hdr_row.addLayout(hdr_text_col, 1)
        card_lay.addLayout(hdr_row)

        # Shape selector buttons
        shape_row = QHBoxLayout()
        shape_row.setSpacing(5)
        shape_btns = {}
        for shape_key, shape_label in AGENT_ICON_SHAPES:
            sb = QToolButton()
            sb.setCheckable(True)
            sb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            sb.setText(shape_label[:4] if len(shape_label) > 6 else shape_label)
            sb.setToolTip(shape_label)
            sb.setIconSize(QSize(22, 22))
            sb.setFixedSize(48, 44)
            sb.setCursor(Qt.PointingHandCursor)
            shape_btns[shape_key] = sb
            shape_row.addWidget(sb)
        shape_row.addStretch()
        card_lay.addLayout(shape_row)

        # Color swatch buttons + custom color dialog button
        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        swatch_btns = {}
        for hex_col, col_name in AGENT_ICON_COLORS:
            cb = QPushButton()
            cb.setCheckable(True)
            cb.setFixedSize(24, 24)
            cb.setToolTip(f"{col_name} ({hex_col})")
            cb.setCursor(Qt.PointingHandCursor)
            swatch_btns[hex_col.lower()] = (cb, hex_col)
            color_row.addWidget(cb)

        custom_col_btn = QPushButton("Custom...")
        custom_col_btn.setFixedHeight(26)
        custom_col_btn.setToolTip("Choose any custom color")
        custom_col_btn.setCursor(Qt.PointingHandCursor)
        color_row.addWidget(custom_col_btn)
        color_row.addStretch()
        card_lay.addLayout(color_row)

        def _sync_appearance_ui():
            cur_c = state["color"]
            cur_s = state["shape"]
            preview_lbl.setPixmap(
                _make_custom_agent_icon(
                    {"avatar_color": cur_c, "avatar_badge": cur_s}, size=44, is_active=True
                ).pixmap(44, 44)
            )
            for s_key, sb in shape_btns.items():
                checked = s_key == cur_s
                sb.blockSignals(True)
                sb.setChecked(checked)
                sb.blockSignals(False)
                sb.setIcon(
                    _make_custom_agent_icon(
                        {"avatar_color": cur_c, "avatar_badge": s_key}, size=22, is_active=checked
                    )
                )
                sb.setStyleSheet(
                    f"QToolButton {{ background-color: {p['bg_elevated'] if checked else p['bg_input']}; "
                    f"color: {p['text_primary'] if checked else p['text_secondary']}; "
                    f"border: {'1.5px solid ' + cur_c if checked else '1px solid ' + p['border']}; "
                    f"border-radius: 8px; font-size: 10px; padding: 2px; }}"
                )
            for low_hex, (cb, orig_hex) in swatch_btns.items():
                is_sel = low_hex == cur_c.lower()
                cb.blockSignals(True)
                cb.setChecked(is_sel)
                cb.blockSignals(False)
                cb.setStyleSheet(
                    f"QPushButton {{ background-color: {orig_hex}; "
                    f"border: {'2.5px solid #ffffff' if is_sel else '1px solid rgba(255,255,255,0.35)'}; "
                    f"border-radius: 12px; padding: 0px; }}"
                )
            custom_col_btn.setStyleSheet(
                f"QPushButton {{ border-color: {cur_c}; font-size: 11px; padding: 2px 8px; }}"
            )

        for s_key, sb in shape_btns.items():
            sb.clicked.connect(
                lambda checked=False, sk=s_key: (state.update({"shape": sk}), _sync_appearance_ui())
            )
        for _low_hex, (cb, orig_hex) in swatch_btns.items():
            cb.clicked.connect(
                lambda checked=False, hc=orig_hex: (state.update({"color": hc}), _sync_appearance_ui())
            )

        def _pick_custom_color():
            picked = QColorDialog.getColor(QColor(state["color"]), dlg, "Choose Custom Icon Color")
            if picked.isValid():
                state["color"] = picked.name()
                _sync_appearance_ui()

        custom_col_btn.clicked.connect(_pick_custom_color)
        _sync_appearance_ui()

        # Insert the customizer card into the dialog's layout above its bottom action buttons
        # Keyless service helper (Free News, Wikipedia, arXiv, Crypto, FX Rates, Reddit)
        svc_combo = None
        for cb in dlg.findChildren(QComboBox):
            if cb.findData("free_news") >= 0 or cb.findData("wikipedia") >= 0:
                svc_combo = cb
                break
        if svc_combo is not None:
            key_edits = [
                le for le in dlg.findChildren(QLineEdit)
                if le.echoMode() == QLineEdit.Password
                or "key" in (le.placeholderText() or "").lower()
                or "token" in (le.placeholderText() or "").lower()
            ]
            sentinel = "KEYLESS_SERVICE_NO_KEY"

            def _sync_key_widgets():
                svc = (svc_combo.currentData() or "").strip().lower()
                is_keyless = svc in KEYLESS_SERVICES
                spec_meta = EXTRA_API_SERVICES.get(svc, {})
                for le in key_edits:
                    if is_keyless:
                        if not le.text().strip():
                            le.setText(sentinel)
                        le.setEnabled(False)
                        le.setPlaceholderText(
                            spec_meta.get("key_placeholder")
                            or "Not required — works with no account or key"
                        )
                    else:
                        if le.text().strip() in (sentinel, "FREE_NEWS_NO_KEY"):
                            le.clear()
                        if svc != "none":
                            le.setEnabled(True)
                            if spec_meta.get("key_placeholder"):
                                le.setPlaceholderText(spec_meta["key_placeholder"])

            svc_combo.currentIndexChanged.connect(lambda _idx: QTimer.singleShot(0, _sync_key_widgets))
            QTimer.singleShot(0, _sync_key_widgets)

        return state

    def _cleanup_keyless_agent_keys(self):
        for ag in modes.list_agents():
            stype = (ag.get("service_type") or "").strip().lower()
            raw_key = (ag.get("api_key") or "").strip()
            if stype in KEYLESS_SERVICES and raw_key in ("FREE_NEWS_NO_KEY", "KEYLESS_SERVICE_NO_KEY"):
                updated = dict(ag)
                updated["api_key"] = ""
                updater = getattr(modes, "update_agent", None) or getattr(modes, "save_agent", None)
                if callable(updater):
                    try:
                        updater(updated)
                    except TypeError:
                        updater(updated["id"], updated)

    def _select_mosaic_agent(self, agent_id):
        if self._is_busy():
            return
        modes.set_active_agent(agent_id)
        self._refresh_agent_bar()
        self._apply_starter_prompts_for_mode()
        self._update_input_placeholder()
        if not self.messages:
            self._render_chat()

    def _create_new_agent(self):
        before_ids = {ag.get("id") for ag in modes.list_agents()}
        dlg = modes.MosaicAgentEditorDialog(self, agent=None)
        appearance_state = self._enhance_agent_editor_dialog(dlg, agent=None)
        if dlg.exec() == QDialog.Accepted:
            self._cleanup_keyless_agent_keys()
            after_agents = modes.list_agents()
            new_ag = next((ag for ag in after_agents if ag.get("id") not in before_ids), None)
            if new_ag is None:
                new_ag = modes.get_active_agent()
            if isinstance(new_ag, dict) and new_ag.get("id"):
                _save_agent_appearance(
                    new_ag["id"],
                    shape=appearance_state["shape"],
                    color=appearance_state["color"],
                )
            self._refresh_agent_bar()
            self._apply_starter_prompts_for_mode()
            self._update_input_placeholder()
            if self.current_mode != "agent":
                self._switch_mode("agent")
            elif not self.messages:
                self._render_chat()

    def _edit_active_agent(self):
        active_ag = modes.get_active_agent()
        dlg = modes.MosaicAgentEditorDialog(self, agent=active_ag)
        appearance_state = self._enhance_agent_editor_dialog(dlg, agent=active_ag)
        if dlg.exec() == QDialog.Accepted:
            self._cleanup_keyless_agent_keys()
            if isinstance(active_ag, dict) and active_ag.get("id"):
                _save_agent_appearance(
                    active_ag["id"],
                    shape=appearance_state["shape"],
                    color=appearance_state["color"],
                )
            self._refresh_agent_bar()
            self._apply_starter_prompts_for_mode()
            self._update_input_placeholder()
            if not self.messages:
                self._render_chat()

    def _run_active_agent_mission(self):
        if self._is_busy():
            return
        active_ag = modes.get_active_agent()
        mission = (active_ag.get("standing_mission") or "").strip()
        if not mission:
            self._edit_active_agent()
            return
        self.input.setPlainText(mission)
        self._send()

    def _refresh_cowork_preview(self):
        _b64, w, h, pm = modes.capture_screen_base64(max_width=960)
        if not pm.isNull():
            thumb = pm.scaled(96, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.screen_thumb_lbl.setPixmap(thumb)
            self.cowork_title_lbl.setText(
                f"Cowork Mode — Screen ({w}×{h}) | Press Esc or move mouse to top-left corner to stop"
            )

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._switch_mode("chat"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self._switch_mode("agent"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self._switch_mode("cowork"))
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._new_chat)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self._open_settings)
        QShortcut(QKeySequence("Ctrl+Shift+I"), self, activated=self._open_api_hub)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self._toggle_chat_api_shortcut)
        QShortcut(QKeySequence("Ctrl+Shift+W"), self, activated=self._toggle_web_shortcut)
        QShortcut(QKeySequence("Escape"), self, activated=self._stop_if_running)

    def _toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _focus_search(self):
        if not self.sidebar.isVisible():
            self.sidebar.setVisible(True)
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _stop_if_running(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
        elif self._finishing_animation:
            self._displayed_reply = self.current_reply
            self._finalize_generation()

    def _init_ollama_connection(self, preferred):
        self._preferred_model = preferred or self._preferred_model
        if (
            self.ensure_ollama is not None
            and self.app_settings.get("auto_start_ollama", True)
            and (self.starter_worker is None or not self.starter_worker.isRunning())
        ):
            self._connection_state = "pending"
            self._update_status_dot()
            self.status_dot.setToolTip("Starting Ollama in system tray...")
            if self.model_box.count() == 0 and self._preferred_model:
                self.model_box.blockSignals(True)
                self.model_box.addItem(self._preferred_model)
                self.model_box.blockSignals(False)
            self.starter_worker = OllamaStarterWorker(self.ensure_ollama, self.base_url)
            self.starter_worker.finished_check.connect(self._on_ollama_started)
            self.starter_worker.start()
            return

        self._load_models(self._preferred_model)

    def _on_ollama_started(self, ok, message):
        self.starter_worker = None
        self._load_models(self._preferred_model)
        if not ok and self._startup_note is None:
            self._startup_note = f"Ollama auto-start: {message}"
        if self._startup_note and not self.messages and not self._is_busy():
            self._render_chat()

    def _load_models(self, preferred):
        self.model_box.blockSignals(True)
        self.model_box.clear()
        try:
            models = self.list_models(self.base_url)
        except Exception:
            models = []
            self._connection_state = "offline"
            self._update_status_dot()
            self.status_dot.setToolTip(f"Offline — cannot reach {self.base_url}")
            self._startup_note = (
                f"Couldn't reach Ollama at {self.base_url}. Make sure Ollama is installed, "
                "or start it with `ollama serve` and click the refresh button."
            )
        else:
            self._connection_state = "online"
            self._update_status_dot()
            self.status_dot.setToolTip(f"Connected to Ollama ({self.base_url})")
            if not models:
                self._startup_note = f"No models installed. Pull one with: `ollama pull {preferred}`"

        if not models:
            models = [preferred]
        self.model_box.addItems(models)

        for i, name in enumerate(models):
            if name == preferred or name.startswith(preferred + ":"):
                self.model_box.setCurrentIndex(i)
                break
        self.model_box.blockSignals(False)
        self._on_model_changed(self.model_box.currentText())

    def _on_model_changed(self, model_name):
        if model_name:
            self.app_settings = settings.save_settings({"last_model": model_name})

    def _format_rel_time(self, ts):
        diff = max(0, datetime.now().timestamp() - ts)
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff // 60)}m ago"
        if diff < 86400:
            return f"{int(diff // 3600)}h ago"
        return datetime.fromtimestamp(ts).strftime("%b %d")

    def _create_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            storage.create_folder(name)
            self._refresh_sidebar()

    def _refresh_sidebar(self):
        query = self.search_box.text() if hasattr(self, "search_box") else ""
        chats = storage.list_chats(query=query)
        folders = {f["id"]: f["name"] for f in storage.load_folders()}
        show_tokens = bool(self.app_settings.get("show_token_counts", True))
        self.chats_header.setText(f"Chats ({len(chats)})" if chats else "No matching chats")

        self.chat_list.clear()
        for c in chats:
            folder_prefix = f"[{folders[c['folder_id']]}] " if c.get("folder_id") in folders else ""
            token_suffix = f"  ({c['tokens_label']})" if show_tokens and c["tokens"] > 0 else ""
            item = QListWidgetItem(f"{folder_prefix}{c['title']}{token_suffix}")
            if c["pinned"]:
                item.setIcon(self._pin_icon)
            elif c.get("folder_id") in folders:
                item.setIcon(self._folder_icon)
            item.setData(Qt.UserRole, c["id"])
            item.setData(Qt.UserRole + 1, c["pinned"])
            item.setData(Qt.UserRole + 2, c["title"])
            item.setToolTip(
                f"{c['title']}\n{c['msg_count']} messages • {c['tokens_label']} • Updated {self._format_rel_time(c['updated_at'])}"
            )
            self.chat_list.addItem(item)
            if c["id"] == self.chat_data["id"]:
                self.chat_list.setCurrentItem(item)

    def _update_memory_button(self):
        count = len(memory.load_memories())
        self.memory_btn.setText(f"  Memories ({count})")

    def _on_chat_clicked(self, item):
        if self._is_busy():
            return
        chat_id = item.data(Qt.UserRole)
        if chat_id == self.chat_data["id"]:
            return
        data = storage.load_chat(chat_id)
        if data is None:
            self._refresh_sidebar()
            return
        self.chat_data = data
        self.messages = data["messages"]
        self._pending_memory_notes.clear()
        self._clear_attachments()
        if data.get("agent_id") and modes.get_agent(data["agent_id"]) is not None:
            modes.set_active_agent(data["agent_id"])
            self._refresh_agent_bar()
            self._apply_starter_prompts_for_mode()
            self._update_input_placeholder()
        if self.app_settings.get("web_search_always_on", False):
            self.web_btn.setChecked(True)
        self._render_chat()
        self.input.setFocus()

    def _new_chat(self):
        if self._is_busy():
            return
        self.chat_data = storage.new_chat()
        self.messages = self.chat_data["messages"]
        self._pending_memory_notes.clear()
        self._clear_attachments()
        if self.app_settings.get("web_search_always_on", False):
            self.web_btn.setChecked(True)
        self._render_chat()
        self._refresh_sidebar()
        self.input.setFocus()

    def _chat_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if item is None:
            return
        chat_id = item.data(Qt.UserRole)
        is_pinned = bool(item.data(Qt.UserRole + 1))
        raw_title = item.data(Qt.UserRole + 2) or item.text()

        menu = QMenu(self)
        pin_act = menu.addAction("Unpin chat" if is_pinned else "Pin to top")
        rename_act = menu.addAction("Rename")
        ai_title_act = menu.addAction("Generate AI Title")

        folders = storage.load_folders()
        folder_actions = {}
        if folders:
            folder_menu = menu.addMenu("Move to Folder")
            none_act = folder_menu.addAction("No Folder")
            folder_actions[none_act] = None
            folder_menu.addSeparator()
            for f in folders:
                act = folder_menu.addAction(f["name"])
                folder_actions[act] = f["id"]

        export_act = menu.addAction("Export as Markdown...")
        menu.addSeparator()
        delete_act = menu.addAction("Delete")

        chosen = menu.exec(self.chat_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == pin_act:
            storage.toggle_pin_chat(chat_id)
            self._refresh_sidebar()
        elif chosen == rename_act:
            self._rename_chat(chat_id, raw_title)
        elif chosen == ai_title_act:
            self._generate_ai_title_for_chat(chat_id, force=True)
        elif chosen in folder_actions:
            storage.set_chat_folder(chat_id, folder_actions[chosen])
            if chat_id == self.chat_data["id"]:
                self.chat_data["folder_id"] = folder_actions[chosen]
            self._refresh_sidebar()
        elif chosen == export_act:
            self._export_chat(chat_id)
        elif chosen == delete_act:
            self._delete_chat(chat_id, raw_title)

    def _rename_chat(self, chat_id, old_title):
        title, ok = QInputDialog.getText(self, "Rename chat", "New name:", text=old_title)
        title = title.strip()
        if not ok or not title:
            return
        data = storage.load_chat(chat_id)
        if data is None:
            return
        data["title"] = title
        storage.save_chat(data)
        if chat_id == self.chat_data["id"]:
            self.chat_data["title"] = title
            self.title_label.setText(title)
        self._refresh_sidebar()

    def _generate_ai_title_for_chat(self, chat_id, force=False):
        data = self.chat_data if chat_id == self.chat_data["id"] else storage.load_chat(chat_id)
        if data is None:
            return
        msgs = data.get("messages") or []
        first_user = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        first_assistant = next((m.get("content", "") for m in msgs if m.get("role") == "assistant"), "")
        if not first_user and not first_assistant:
            return

        self._launch_title_worker(
            chat_id=chat_id,
            expected_old_title=data.get("title", "New chat"),
            user_msg=first_user,
            assistant_msg=first_assistant,
            force=force,
        )

    def _launch_title_worker(self, chat_id, expected_old_title, user_msg, assistant_msg, force=False):
        model_name = self.model_box.currentText()
        if not model_name:
            return
        worker = TitleGeneratorWorker(
            self.stream_chat,
            self.base_url,
            model_name,
            chat_id=chat_id,
            expected_old_title=expected_old_title,
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            keep_alive=self.app_settings.get("keep_alive", "5m"),
            force=force,
        )
        worker.title_ready.connect(self._on_ai_title_ready)
        worker.finished.connect(lambda w=worker: self._cleanup_title_worker(w))
        self._title_workers.append(worker)
        worker.start()

    def _cleanup_title_worker(self, worker):
        if worker in self._title_workers:
            self._title_workers.remove(worker)

    def _on_ai_title_ready(self, chat_id, expected_old_title, new_title):
        if not new_title:
            return
        if chat_id == self.chat_data["id"]:
            cur_title = self.chat_data.get("title", "New chat")
            if not expected_old_title or cur_title in ("New chat", expected_old_title):
                self.chat_data["title"] = new_title
                self.title_label.setText(new_title)
                storage.save_chat(self.chat_data)
                self._refresh_sidebar()
        else:
            data = storage.load_chat(chat_id)
            if data is not None:
                cur_title = data.get("title", "New chat")
                if not expected_old_title or cur_title in ("New chat", expected_old_title):
                    data["title"] = new_title
                    storage.save_chat(data)
                    self._refresh_sidebar()

    def _export_chat(self, chat_id):
        data = storage.load_chat(chat_id)
        if data is None:
            return
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", data.get("title", "chat")) + ".md"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Chat as Markdown", safe_name, "Markdown Files (*.md)"
        )
        if path:
            Path(path).write_text(
                storage.export_chat_markdown(data, self.bot_name), encoding="utf-8"
            )

    def _export_all_chats(self):
        default_name = f"mosaic-backup-{datetime.now().strftime('%Y%m%d')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export All Chats", default_name, "JSON Files (*.json)"
        )
        if path:
            Path(path).write_text(storage.export_all_chats_json(), encoding="utf-8")

    def _clear_all_chats_action(self):
        storage.clear_all_chats()
        self.chat_data = storage.new_chat()
        self.messages = self.chat_data["messages"]
        self._pending_memory_notes.clear()
        self._render_chat()
        self._refresh_sidebar()

    def _delete_chat(self, chat_id, title):
        if self.app_settings.get("confirm_delete", True):
            answer = QMessageBox.question(
                self, "Delete chat", f'Delete "{title}"? This can\'t be undone.'
            )
            if answer != QMessageBox.Yes:
                return
        storage.delete_chat(chat_id)
        if chat_id == self.chat_data["id"]:
            self.chat_data = storage.new_chat()
            self.messages = self.chat_data["messages"]
            self._render_chat()
        self._refresh_sidebar()

    def _open_memories(self):
        MemoryDialog(self).exec()
        self.app_settings = settings.load_settings()
        self._update_memory_button()

    def _open_api_hub(self):
        dlg = api.ApiHubDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.app_settings = dlg.settings
            api_ready = bool(
                self.app_settings.get("chat_api_enabled", False)
                and self.app_settings.get("chat_api_service", "none") not in ("", "none")
            )
            self.chat_api_btn.blockSignals(True)
            self.chat_api_btn.setChecked(api_ready)
            self.chat_api_btn.blockSignals(False)
            self._sync_chat_api_button_ui()
            if not self.messages and not self._is_busy():
                self._render_chat()

    def _open_settings(self):
        models = [self.model_box.itemText(i) for i in range(self.model_box.count())]
        dlg = settings.SettingsDialog(
            self,
            available_models=models,
            on_manage_memories=self._open_memories,
            on_export_all=self._export_all_chats,
            on_clear_history=self._clear_all_chats_action,
        )
        if dlg.exec() == QDialog.Accepted:
            self.app_settings = dlg.settings
            new_url = self.app_settings.get("ollama_url", self.base_url)
            url_changed = new_url != self.base_url
            self.base_url = new_url

            if self.app_settings.get("web_search_always_on", False):
                self.web_btn.setChecked(True)

            api_ready = bool(
                self.app_settings.get("chat_api_enabled", False)
                and self.app_settings.get("chat_api_service", "none") not in ("", "none")
            )
            self.chat_api_btn.blockSignals(True)
            self.chat_api_btn.setChecked(api_ready)
            self.chat_api_btn.blockSignals(False)

            self._apply_theme()
            if url_changed:
                self._init_ollama_connection(self.model_box.currentText())
            self._render_chat()

    def _attach_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach Text or Code Files",
            "",
            "Code & Text (*.py *.js *.ts *.tsx *.jsx *.json *.md *.txt *.csv *.html *.css *.java *.c *.cpp *.rs *.go *.sh *.yaml *.yml *.toml);;All Files (*)",
        )
        for p in paths:
            file_path = Path(p)
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                QMessageBox.warning(self, "Attachment error", f"Couldn't read {file_path.name}: {e}")
                continue
            if len(content) > 60_000:
                content = content[:60_000] + "\n... [truncated]"
            self.attachments.append({"name": file_path.name, "content": content})
        self._refresh_chips()
        self.input.setFocus()

    def _remove_attachment(self, index):
        if 0 <= index < len(self.attachments):
            self.attachments.pop(index)
            self._refresh_chips()

    def _clear_attachments(self):
        self.attachments.clear()
        self._refresh_chips()

    def _refresh_chips(self):
        while self.chip_layout.count():
            item = self.chip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.attachments:
            self.chip_bar.setVisible(False)
            return

        for idx, att in enumerate(self.attachments):
            chip = QPushButton(f" {att['name']}  ×")
            chip.setObjectName("chip")
            chip.setIcon(self._file_icon)
            chip.setIconSize(QSize(14, 14))
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip("Click to remove attachment")
            chip.clicked.connect(lambda checked=False, i=idx: self._remove_attachment(i))
            self.chip_layout.addWidget(chip)
        self.chip_layout.addStretch()
        self.chip_bar.setVisible(True)

    def _on_scroll_value_changed(self, value):
        vbar = self.chat_scroll.verticalScrollBar()
        self._auto_scroll = (vbar.maximum() - value) <= 60

    def _on_scroll_range_changed(self, _min, maximum):
        if self._auto_scroll:
            self.chat_scroll.verticalScrollBar().setValue(maximum)

    def _make_rich_label(self, html_text):
        lbl = QLabel()
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setOpenExternalLinks(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lbl.setFont(self._make_chat_font())
        lbl.setText(html_text)
        return lbl

    def _format_msg_timestamp(self, msg):
        if not self.app_settings.get("show_timestamps", False):
            return ""
        ts = msg.get("timestamp")
        if not ts:
            return ""
        return datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")

    def _build_memory_pill(self, fact):
        row = QWidget()
        outer = QHBoxLayout(row)
        outer.setContentsMargins(0, 0, 0, 0)

        pill = QFrame()
        pill.setObjectName("memoryNote")
        inner = QHBoxLayout(pill)
        inner.setContentsMargins(10, 5, 12, 5)
        inner.setSpacing(7)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._memory_pill_pixmap)
        text_lbl = QLabel(f"Saved to memory: {fact}")
        text_lbl.setObjectName("memoryNoteText")

        inner.addWidget(icon_lbl)
        inner.addWidget(text_lbl)
        outer.addWidget(pill)
        outer.addStretch()
        return row

    def _build_user_widget(self, content, msg_index=None, timestamp_str=""):
        p = self.palette
        compact = bool(self.app_settings.get("compact_mode", False))
        frame = QFrame()
        frame.setObjectName("userBubble")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 7 if compact else 10, 12, 7 if compact else 10)
        box.setSpacing(3 if compact else 4)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        who = QLabel("You")
        who.setStyleSheet(f"color: {p['green']}; font-weight: bold; font-size: 12px;")
        hdr.addWidget(who)
        if timestamp_str:
            ts_lbl = QLabel(timestamp_str)
            ts_lbl.setObjectName("muted")
            hdr.addWidget(ts_lbl)
        hdr.addStretch()
        box.addLayout(hdr)

        body = self._make_rich_label(
            f'<div style="color:{p["text_primary"]};">{render_markdown_html(content, p)}</div>'
        )
        box.addWidget(body)

        if msg_index is not None:
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 2, 0, 0)
            actions.setSpacing(4)

            edit_btn = QPushButton()
            edit_btn.setObjectName("msgActionBtn")
            edit_btn.setIcon(self._edit_icon)
            edit_btn.setIconSize(QSize(16, 16))
            edit_btn.setFixedSize(26, 26)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setToolTip("Edit message and regenerate")
            edit_btn.clicked.connect(
                lambda checked=False, idx=msg_index: self._edit_message_at(idx)
            )

            copy_btn = QPushButton()
            copy_btn.setObjectName("msgActionBtn")
            copy_btn.setIcon(self._copy_icon)
            copy_btn.setIconSize(QSize(16, 16))
            copy_btn.setFixedSize(26, 26)
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setToolTip("Copy message")
            copy_btn.clicked.connect(
                lambda checked=False, txt=content, btn=copy_btn: self._copy_response(txt, btn)
            )

            del_btn = QPushButton()
            del_btn.setObjectName("msgActionBtn")
            del_btn.setIcon(self._trash_icon)
            del_btn.setIconSize(QSize(16, 16))
            del_btn.setFixedSize(26, 26)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setToolTip("Delete message")
            del_btn.clicked.connect(
                lambda checked=False, idx=msg_index: self._delete_message_at(idx)
            )

            actions.addWidget(edit_btn)
            actions.addWidget(copy_btn)
            actions.addWidget(del_btn)
            actions.addStretch()
            box.addLayout(actions)

        return frame

    def _build_sources_widget(self, sources):
        unique_sources = _dedupe_sources(sources)
        if not unique_sources:
            return None

        p = self.palette
        links = []
        for idx, src in enumerate(unique_sources[:10], start=1):
            title = html.escape(src["title"])
            if len(title) > 42:
                title = title[:39] + "..."
            url = html.escape(src["url"])
            links.append(
                f'<a href="{url}" style="color:{p["accent"]};text-decoration:none;">'
                f"[{idx}] {title}</a>"
            )

        extra = len(unique_sources) - 10
        extra_html = (
            f' <span style="color:{p["text_muted"]};">(+{extra} more)</span>'
            if extra > 0
            else ""
        )

        box = QFrame()
        box.setObjectName("sourcesBox")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(6)

        lbl = QLabel(
            f'<span style="color:{p["text_muted"]};font-weight:bold;">Sources:</span> '
            + " &nbsp;·&nbsp; ".join(links)
            + extra_html
        )
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setOpenExternalLinks(True)
        lbl.setStyleSheet("font-size: 12px;")
        lay.addWidget(lbl, 1)
        return box

    def _build_assistant_widget(
        self, content, msg_index=None, is_streaming=False, timestamp_str="", sources=None, sender_name=None
    ):
        p = self.palette
        compact = bool(self.app_settings.get("compact_mode", False))
        wrapper = QWidget()
        box = QVBoxLayout(wrapper)
        box.setContentsMargins(2, 1 if compact else 2, 2, 1 if compact else 2)
        box.setSpacing(4 if compact else 6)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        display_who = sender_name or (
            modes.get_active_agent()["name"] if self.current_mode == "agent" else self.bot_name
        )
        who = QLabel(display_who)
        who.setStyleSheet(f"color: {p['accent']}; font-weight: bold; font-size: 12px;")
        hdr.addWidget(who)
        if timestamp_str:
            ts_lbl = QLabel(timestamp_str)
            ts_lbl.setObjectName("muted")
            hdr.addWidget(ts_lbl)
        hdr.addStretch()
        box.addLayout(hdr)

        if is_streaming and not content:
            status_escaped = html.escape(self._stream_status_text or "Thinking...")
            body_html = f'<span style="color:{p["text_muted"]};font-style:italic;">{status_escaped}</span>'
        else:
            body_html = f'<div style="color:{p["text_primary"]};">{render_markdown_html(content, p)}</div>'

        body = self._make_rich_label(body_html)
        box.addWidget(body)

        if (
            not is_streaming
            and sources
            and self.app_settings.get("web_search_show_sources", True)
        ):
            src_widget = self._build_sources_widget(sources)
            if src_widget is not None:
                box.addWidget(src_widget)

        if is_streaming:
            self._active_stream_label = body
        elif msg_index is not None:
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 2, 0, 0)
            actions.setSpacing(4)

            regen_btn = QPushButton()
            regen_btn.setObjectName("msgActionBtn")
            regen_btn.setIcon(self._regen_icon)
            regen_btn.setIconSize(QSize(18, 18))
            regen_btn.setFixedSize(28, 28)
            regen_btn.setCursor(Qt.PointingHandCursor)
            regen_btn.setToolTip("Regenerate response")
            regen_btn.clicked.connect(
                lambda checked=False, idx=msg_index: self._regenerate_at(idx)
            )

            copy_btn = QPushButton()
            copy_btn.setObjectName("msgActionBtn")
            copy_btn.setIcon(self._copy_icon)
            copy_btn.setIconSize(QSize(18, 18))
            copy_btn.setFixedSize(28, 28)
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setToolTip("Copy response")
            copy_btn.clicked.connect(
                lambda checked=False, txt=content, btn=copy_btn: self._copy_response(txt, btn)
            )

            del_btn = QPushButton()
            del_btn.setObjectName("msgActionBtn")
            del_btn.setIcon(self._trash_icon)
            del_btn.setIconSize(QSize(16, 16))
            del_btn.setFixedSize(28, 28)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setToolTip("Delete response")
            del_btn.clicked.connect(
                lambda checked=False, idx=msg_index: self._delete_message_at(idx)
            )

            actions.addWidget(regen_btn)
            actions.addWidget(copy_btn)
            actions.addWidget(del_btn)
            actions.addStretch()
            box.addLayout(actions)

        return wrapper

    def _clear_chat_widgets(self):
        self._active_stream_label = None
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _append_chat_widget(self, widget):
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget)

    def _render_chat(self, streaming_reply=None):
        p = self.palette
        self._auto_scroll = True
        self._clear_chat_widgets()

        self.title_label.setText(self.chat_data["title"])
        self.starter_panel.setVisible(len(self.messages) == 0 and streaming_reply is None)

        if not self.messages and streaming_reply is None:
            if self.current_mode == "agent":
                ag = modes.get_active_agent()
                card = QFrame()
                card.setObjectName("settingsCard")
                cbox = QVBoxLayout(card)
                cbox.setContentsMargins(16, 14, 16, 14)
                cbox.setSpacing(6)

                top_r = QHBoxLayout()
                av_lbl = QLabel()
                av_lbl.setPixmap(
                    _make_custom_agent_icon(ag, size=40, is_active=True).pixmap(40, 40)
                )
                top_r.addWidget(av_lbl)

                title_col = QVBoxLayout()
                title_col.setSpacing(1)
                nm = QLabel(f"{ag['name']}  ({ag['handle']})")
                nm.setStyleSheet(
                    f"color: {ag.get('avatar_color', p['accent'])}; font-weight: bold; font-size: 15px;"
                )
                sub_tag = QLabel(
                    f"Isolated Service: {modes.get_agent_service_summary(ag)}  •  "
                    f"Boundary: {'Autonomous' if ag.get('boundary_mode') == 'auto' else 'Ask Before Tools'}"
                )
                sub_tag.setObjectName("muted")
                title_col.addWidget(nm)
                title_col.addWidget(sub_tag)
                top_r.addLayout(title_col, 1)
                cbox.addLayout(top_r)

                pers = html.escape(ag.get("personality") or "Helpful, proactive specialist agent.")
                inst = html.escape(ag.get("instructions") or "Ready to carry out tasks with your assigned API.")
                details = self._make_rich_label(
                    f'<div style="color:{p["text_primary"]};line-height:1.45;">'
                    f"<b>Personality:</b> {pers}<br>"
                    f"<b>What I Do:</b> {inst}"
                    f"</div>"
                )
                cbox.addWidget(details)
                self._append_chat_widget(card)
            else:
                welcome = QWidget()
                wbox = QVBoxLayout(welcome)
                wbox.setContentsMargins(2, 2, 2, 6)
                wbox.setSpacing(4)
                who = QLabel(f"{self.bot_name} ({self.current_mode.capitalize()} Mode)")
                who.setStyleSheet(f"color: {p['accent']}; font-weight: bold; font-size: 14px;")
                wbox.addWidget(who)

                chat_api_note = ""
                if (
                    self.current_mode == "chat"
                    and hasattr(self, "chat_api_btn")
                    and self.chat_api_btn.isChecked()
                ):
                    svc_key = self.app_settings.get("chat_api_service", "none")
                    svc_raw = (
                        EXTRA_API_SERVICES[svc_key]["short"]
                        if svc_key in EXTRA_API_SERVICES
                        else modes.SERVICE_SPECS.get(svc_key, {}).get("short", svc_key)
                    )
                    svc_name = html.escape(svc_raw)
                    chat_api_note = f" <b>API Access ({svc_name})</b> is active."

                mode_intro = {
                    "chat": (
                        f"Hi, I'm <b>{html.escape(self.bot_name)}</b>. Ask a question, paste code, "
                        f"attach a file, or toggle <b>API</b> / <b>Web</b> below.{chat_api_note}"
                    ),
                    "cowork": (
                        "<b>Cowork Mode</b> is active. I can inspect your screen and control your cursor "
                        "to help automate tasks. Use a vision-capable model (e.g. <code>llama3.2-vision</code> or <code>qwen2.5vl</code>) for best screen reading."
                    ),
                }[self.current_mode]

                msg = self._make_rich_label(
                    f'<div style="color:{p["text_primary"]};line-height:1.5;">{mode_intro}</div>'
                )
                wbox.addWidget(msg)
                self._append_chat_widget(welcome)

        for idx, m in enumerate(self.messages):
            role = m.get("role")
            content = m.get("content", "")
            ts_str = self._format_msg_timestamp(m)
            if role == "user":
                self._append_chat_widget(
                    self._build_user_widget(content, msg_index=idx, timestamp_str=ts_str)
                )
            elif role == "assistant":
                self._append_chat_widget(
                    self._build_assistant_widget(
                        content,
                        msg_index=idx,
                        is_streaming=False,
                        timestamp_str=ts_str,
                        sources=m.get("sources"),
                        sender_name=m.get("sender_name"),
                    )
                )

        for fact in self._pending_memory_notes:
            self._append_chat_widget(self._build_memory_pill(fact))

        if streaming_reply is not None:
            self._append_chat_widget(
                self._build_assistant_widget(streaming_reply, is_streaming=True)
            )

        if self._startup_note:
            note = self._make_rich_label(
                f'<div style="color:{p["red"]};font-style:italic;margin-top:6px;">'
                f"{render_markdown_html(self._startup_note, p)}</div>"
            )
            self._append_chat_widget(note)
            self._startup_note = None

    def _next_typing_step(self, remaining):
        speed = self.app_settings.get("smooth_typing_speed", "natural")
        if speed == "relaxed":
            base = 1 if remaining < 40 else 2
            catchup = remaining // 55
        elif speed == "fast":
            base = 5
            catchup = remaining // 18
        else:  # "natural"
            base = 2 if remaining < 25 else 3
            catchup = remaining // 32
        return max(base, catchup)

    def _flush_stream_render(self):
        smooth = bool(self.app_settings.get("smooth_responses", True))
        target_len = len(self.current_reply)
        cur_len = len(self._displayed_reply)

        if smooth:
            if cur_len < target_len:
                step = self._next_typing_step(target_len - cur_len)
                self._displayed_reply = self.current_reply[: min(target_len, cur_len + step)]
                self._stream_dirty = True
            elif self._worker_done and self._finishing_animation:
                self._finalize_generation()
                return
        else:
            if cur_len != target_len:
                self._displayed_reply = self.current_reply
                self._stream_dirty = True

        if self._stream_dirty and self._active_stream_label is not None:
            self._stream_dirty = False
            if not self._displayed_reply:
                status_escaped = html.escape(self._stream_status_text or "Thinking...")
                self._active_stream_label.setText(
                    f'<span style="color:{self.palette["text_muted"]};font-style:italic;">{status_escaped}</span>'
                )
            else:
                self._active_stream_label.setText(
                    f'<div style="color:{self.palette["text_primary"]};">{render_markdown_html(self._displayed_reply, self.palette)}</div>'
                )

    def _restore_copy_icon(self, btn):
        try:
            btn.setIcon(self._copy_icon)
        except RuntimeError:
            pass

    def _copy_response(self, content, btn):
        QApplication.clipboard().setText(content)
        btn.setIcon(self._check_icon)
        QTimer.singleShot(1500, lambda b=btn: self._restore_copy_icon(b))

    def _edit_message_at(self, msg_index):
        if self._is_busy():
            return
        if not (0 <= msg_index < len(self.messages)):
            return
        current_text = self.messages[msg_index].get("content", "")
        new_text, ok = QInputDialog.getMultiLineText(
            self, "Edit Message", "Update your prompt:", text=current_text
        )
        new_text = new_text.strip()
        if not ok or not new_text:
            return
        self._pending_memory_notes.clear()
        self.messages[msg_index]["content"] = new_text
        self.messages[msg_index]["timestamp"] = time.time()
        self.messages[:] = self.messages[: msg_index + 1]
        self._start_generation(query=new_text)

    def _delete_message_at(self, msg_index):
        if self._is_busy():
            return
        if not (0 <= msg_index < len(self.messages)):
            return
        self.messages.pop(msg_index)
        if self.messages:
            storage.save_chat(self.chat_data)
        self._refresh_sidebar()
        self._render_chat()

    def _regenerate_at(self, msg_index):
        if self._is_busy():
            return
        if not (0 <= msg_index < len(self.messages)):
            return
        self._pending_memory_notes.clear()
        self.messages[:] = self.messages[:msg_index]
        if not self.messages or self.messages[-1].get("role") != "user":
            self._render_chat()
            return
        last_user_text = self.messages[-1].get("content", "")
        self._start_generation(query=last_user_text)

    def _set_generating(self, generating):
        self.send_btn.setText("Stop" if generating else "Send")
        self.send_btn.setProperty("stopping", generating)
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)
        self.model_box.setEnabled(not generating)
        self.sidebar.setEnabled(not generating)
        self.mode_rail.setEnabled(not generating)
        self.agent_bar.setEnabled(not generating)
        self.attach_btn.setEnabled(not generating)
        self.chat_api_btn.setEnabled(not generating)
        self.web_btn.setEnabled(not generating)
        self.input.setReadOnly(generating)

    def _on_send_clicked(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            return
        if self._finishing_animation:
            self._displayed_reply = self.current_reply
            self._finalize_generation()
            return
        self._send()

    def _send(self):
        raw_text = self.input.toPlainText().strip()
        if not raw_text and not self.attachments:
            return
        self.input.clear()

        if self.app_settings.get("memory_enabled", True):
            saved_facts = memory.extract_memories_from_text(raw_text)
        else:
            saved_facts = []
        self._pending_memory_notes = list(saved_facts)
        if saved_facts:
            self._update_memory_button()

        first_att_name = self.attachments[0]["name"] if self.attachments else ""
        composed = raw_text
        if self.attachments:
            att_blocks = []
            for att in self.attachments:
                ext = Path(att["name"]).suffix.lstrip(".")
                att_blocks.append(f"**Attached: `{att['name']}`**\n```{ext}\n{att['content']}\n```")
            joined_atts = "\n\n".join(att_blocks)
            composed = f"{raw_text}\n\n{joined_atts}" if raw_text else joined_atts
            self._clear_attachments()

        if self.current_mode == "agent":
            self.chat_data["agent_id"] = modes.get_active_agent()["id"]

        self.messages.append({"role": "user", "content": composed, "timestamp": time.time()})
        if len(self.messages) == 1 and self.app_settings.get("auto_title", True):
            title_seed = raw_text or (f"File: {first_att_name}" if first_att_name else "New chat")
            self.chat_data["title"] = storage.make_title(title_seed)

        self._start_generation(query=raw_text)

    def _start_generation(self, query=""):
        current_settings = settings.load_settings()
        self.app_settings = current_settings
        mem_limit = int(current_settings.get("memory_limit", 20))
        if current_settings.get("memory_enabled", True):
            relevant_memories = memory.get_relevant_memories(query=query, limit=mem_limit)
        else:
            relevant_memories = []

        system = self.build_system_prompt(relevant_memories)

        initial_screen_b64 = ""
        screen_size = (1920, 1080)
        allow_cursor = False
        active_agent_id = None
        chat_api_enabled = False
        chat_agent_profile = None

        if self.current_mode == "agent":
            active_ag = modes.get_active_agent()
            active_agent_id = active_ag["id"]
            system = modes.build_agent_system_prompt(system, agent=active_ag)
            system = _augment_custom_api_system_prompt(system, active_ag)
        elif self.current_mode == "chat":
            chat_api_enabled = bool(
                self.chat_api_btn.isChecked()
                and current_settings.get("chat_api_service", "none") not in ("", "none")
            )
            if chat_api_enabled:
                chat_agent_profile = self._build_chat_mode_agent(current_settings)
                system = modes.build_agent_system_prompt(system, agent=chat_agent_profile)
                system = _augment_custom_api_system_prompt(system, chat_agent_profile)
        elif self.current_mode == "cowork":
            allow_vision = bool(self.cw_vision_cb.isChecked())
            allow_cursor = bool(self.cw_cursor_cb.isChecked())
            if allow_vision:
                b64, sw, sh, pm = modes.capture_screen_base64()
                initial_screen_b64 = b64
                screen_size = (sw, sh)
                if not pm.isNull():
                    self.screen_thumb_lbl.setPixmap(
                        pm.scaled(96, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
            else:
                scr = QApplication.primaryScreen()
                if scr is not None:
                    g = scr.geometry()
                    screen_size = (g.width(), g.height())
            system = modes.build_cowork_system_prompt(
                system, screen_size[0], screen_size[1], allow_cursor=allow_cursor
            )

        api_messages = [{"role": m["role"], "content": m["content"]} for m in self.messages]
        payload = [{"role": "system", "content": system}] + api_messages

        options = {
            "temperature": float(current_settings.get("temperature", 0.7)),
            "top_p": float(current_settings.get("top_p", 0.9)),
            "num_ctx": int(current_settings.get("num_ctx", 4096)),
            "repeat_penalty": float(current_settings.get("repeat_penalty", 1.1)),
        }
        num_predict = int(current_settings.get("num_predict", -1))
        if num_predict > 0:
            options["num_predict"] = num_predict

        use_web = bool(self.web_btn.isChecked() and query.strip() and self.current_mode != "agent")
        self.current_reply = ""
        self._displayed_reply = ""
        self._worker_done = False
        self._finishing_animation = False
        self._last_search_results = []
        if use_web:
            self._stream_status_text = "Searching the web..."
        elif self.current_mode == "cowork":
            self._stream_status_text = "Inspecting screen..."
        elif self.current_mode == "agent":
            ag_name = modes.get_active_agent()["name"]
            self._stream_status_text = f"{ag_name} thinking..."
        else:
            self._stream_status_text = "Thinking..."

        self._stream_dirty = False
        self._set_generating(True)
        self._render_chat(streaming_reply="")
        self.render_timer.setInterval(18 if current_settings.get("smooth_responses", True) else 35)
        self.render_timer.start()

        self.worker = ChatWorker(
            self.stream_chat,
            self.base_url,
            self.model_box.currentText(),
            payload,
            options=options,
            stream=bool(current_settings.get("stream_responses", True)),
            keep_alive=current_settings.get("keep_alive", "5m"),
            timeout=int(current_settings.get("request_timeout", 300)),
            use_web_search=use_web,
            search_web_fn=self.search_web,
            format_search_fn=self.format_search_context,
            search_query=query,
            max_search_results=int(current_settings.get("web_search_max_results", 5)),
            ollama_api_key=current_settings.get("ollama_api_key", ""),
            mode=self.current_mode,
            agent_id=active_agent_id,
            chat_api_enabled=chat_api_enabled,
            chat_agent=chat_agent_profile,
            cowork_allow_cursor=allow_cursor,
            cowork_confirm_actions=bool(self.cw_confirm_cb.isChecked()),
            cowork_screen_size=screen_size,
            initial_screen_b64=initial_screen_b64,
        )
        self.worker.status_changed.connect(self._on_worker_status)
        self.worker.search_completed.connect(self._on_search_completed)
        self.worker.agent_updated.connect(self._refresh_agent_bar)
        self.worker.request_screenshot.connect(self._on_cowork_screenshot_requested)
        self.worker.request_action_confirm.connect(self._on_cowork_confirm_requested)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.replace_reply.connect(self._on_replace_reply)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_cowork_screenshot_requested(self):
        if self.worker is None:
            return
        if self.cw_vision_cb.isChecked():
            b64, _w, _h, pm = modes.capture_screen_base64()
            if not pm.isNull():
                self.screen_thumb_lbl.setPixmap(
                    pm.scaled(96, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            self.worker.provide_screenshot(b64)
        else:
            self.worker.provide_screenshot("")

    def _on_cowork_confirm_requested(self, action_desc):
        if self.worker is None:
            return
        ans = QMessageBox.question(
            self,
            "Action Confirmation",
            f"Allow Mosaic to execute:\n\n{action_desc}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        self.worker.provide_confirm_result(ans == QMessageBox.Yes)

    def _on_worker_status(self, status_text):
        self._stream_status_text = status_text
        self._stream_dirty = True

    def _on_search_completed(self, results):
        self._last_search_results = _dedupe_sources(results)

    def _on_chunk(self, piece):
        self.current_reply += piece
        self._stream_dirty = True

    def _on_replace_reply(self, new_text):
        self.current_reply = new_text
        self._displayed_reply = new_text
        self._stream_dirty = True

    def _on_failed(self, message):
        self._startup_note = f"Error: {message}"

    def _on_auto_learned(self, facts):
        self._update_memory_button()
        for fact in facts:
            self._append_chat_widget(self._build_memory_pill(fact))

    def _on_finished(self):
        self.worker = None
        self._worker_done = True
        smooth = bool(self.app_settings.get("smooth_responses", True))
        if smooth and self.current_reply and len(self._displayed_reply) < len(self.current_reply):
            self._finishing_animation = True
            return
        self._finalize_generation()

    def _finalize_generation(self):
        self.render_timer.stop()
        self._finishing_animation = False
        self._displayed_reply = self.current_reply
        last_user_msg = ""

        if self.current_reply:
            if self.messages and self.messages[-1]["role"] == "user":
                last_user_msg = self.messages[-1]["content"]
            sender = (
                modes.get_active_agent()["name"]
                if self.current_mode == "agent"
                else self.bot_name
            )
            assistant_entry = {
                "role": "assistant",
                "content": self.current_reply,
                "timestamp": time.time(),
                "sender_name": sender,
            }
            if self._last_search_results:
                assistant_entry["sources"] = _dedupe_sources(self._last_search_results)
            self.messages.append(assistant_entry)
        elif self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()
            if not self.messages:
                self.chat_data["title"] = "New chat"

        if self.messages:
            storage.save_chat(self.chat_data)
            self._refresh_sidebar()

        completed_reply = self.current_reply
        self._last_search_results = []
        self._set_generating(False)
        self._render_chat()
        self._pending_memory_notes.clear()
        self.input.setFocus()

        cfg = settings.load_settings()

        if (
            completed_reply
            and last_user_msg
            and len(self.messages) == 2
            and cfg.get("auto_title", True)
        ):
            self._launch_title_worker(
                chat_id=self.chat_data["id"],
                expected_old_title=self.chat_data.get("title", "New chat"),
                user_msg=last_user_msg,
                assistant_msg=completed_reply,
                force=False,
            )

        if (
            completed_reply
            and last_user_msg
            and cfg.get("memory_enabled", True)
            and cfg.get("auto_memory", False)
            and (self.mem_worker is None or not self.mem_worker.isRunning())
        ):
            self.mem_worker = MemoryExtractorWorker(
                self.base_url,
                self.model_box.currentText(),
                last_user_msg,
                completed_reply,
            )
            self.mem_worker.learned.connect(self._on_auto_learned)
            self.mem_worker.start()

    def closeEvent(self, event):
        self.render_timer.stop()
        if self.starter_worker is not None and self.starter_worker.isRunning():
            self.starter_worker.wait(1500)
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(3000):
                self.worker.terminate()
                self.worker.wait()
        if self.mem_worker is not None and self.mem_worker.isRunning():
            self.mem_worker.wait(1500)
        for tw in list(self._title_workers):
            if tw.isRunning():
                tw.wait(1500)
        event.accept()