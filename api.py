from datetime import datetime
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import modes
import settings


EXTRA_API_SERVICES = {
    "free_news": {
        "label": "Free News (No Account / No Key)",
        "name": "Free News",
        "short": "Free News",
        "category": "No Key Needed",
        "description": "Live global news headlines and topic search with zero signup, account, or API key required.",
        "key_label": "API Key (Not Required)",
        "key_placeholder": "Not required — works out of the box with no account",
        "setup_hint": "Ready immediately! Just enable Chat Mode API Access and ask for top headlines or news on any topic.",
        "requires_key": False,
        "base_url": "",
        "tools": [
            ("free_news", "Fetch top live news headlines or search news by topic (no key required)")
        ],
    },
    "wikipedia": {
        "label": "Wikipedia (Encyclopedia — No Account / No Key)",
        "name": "Wikipedia",
        "short": "Wikipedia",
        "category": "No Key Needed",
        "description": "Search Wikipedia articles and pull clean encyclopedic summaries with zero setup.",
        "key_label": "API Key (Not Required)",
        "key_placeholder": "Not required — free public encyclopedia API",
        "setup_hint": "Ready immediately! Ask Mosaic to look up concepts, historical events, or biographies on Wikipedia.",
        "requires_key": False,
        "base_url": "https://en.wikipedia.org",
        "tools": [
            ("wiki_search", "Search Wikipedia articles matching a topic"),
            ("wiki_summary", "Fetch the full summary and link for an exact Wikipedia page title"),
        ],
    },
    "arxiv": {
        "label": "arXiv Research Papers (No Account / No Key)",
        "name": "arXiv Research",
        "short": "arXiv",
        "category": "No Key Needed",
        "description": "Search open-access preprints in AI, computer science, physics, and mathematics.",
        "key_label": "API Key (Not Required)",
        "key_placeholder": "Not required — free open-access research archive",
        "setup_hint": "Ready immediately! Search peer-reviewed preprints by topic, title, or researcher name.",
        "requires_key": False,
        "base_url": "http://export.arxiv.org/api",
        "tools": [
            ("arxiv_search", "Search arXiv research papers by topic, title, or author"),
        ],
    },
    "crypto": {
        "label": "Crypto & Markets (CoinGecko — No Key)",
        "name": "Crypto Markets",
        "short": "Crypto",
        "category": "No Key Needed",
        "description": "Live cryptocurrency prices in USD & AUD, 24h percentage changes, and trending coins.",
        "key_label": "API Key (Not Required)",
        "key_placeholder": "Not required — free live market data",
        "setup_hint": "Ready immediately! Ask for live Bitcoin, Ethereum, or Solana prices or trending coins.",
        "requires_key": False,
        "base_url": "https://api.coingecko.com/api/v3",
        "tools": [
            ("crypto_price", "Get live USD/AUD prices and 24h change for coins (e.g. 'bitcoin,ethereum,solana')"),
            ("crypto_trending", "Get the top trending cryptocurrencies right now"),
        ],
    },
    "currency": {
        "label": "Currency & FX Rates (No Account / No Key)",
        "name": "FX Rates",
        "short": "FX Rates",
        "category": "No Key Needed",
        "description": "Live foreign exchange rates and instant currency conversion across 160+ currencies.",
        "key_label": "API Key (Not Required)",
        "key_placeholder": "Not required — free live exchange rates",
        "setup_hint": "Ready immediately! Ask Mosaic to convert amounts like '100 USD to AUD' or check major rates.",
        "requires_key": False,
        "base_url": "https://open.er-api.com/v6",
        "tools": [
            ("fx_convert", "Convert currency or get rates (e.g. '100 USD to AUD' or 'EUR')"),
        ],
    },
    "reddit": {
        "label": "Reddit (Subreddits & Posts — No Key Needed)",
        "name": "Reddit",
        "short": "Reddit",
        "category": "No Key Needed",
        "description": "Browse hot posts in any subreddit or search Reddit discussions without an account.",
        "key_label": "Optional Bearer Token (Not Required)",
        "key_placeholder": "Optional — works out of the box without a key",
        "setup_hint": "Works without an API key! Ask for hot posts in r/technology, r/python, or search any keyword.",
        "requires_key": False,
        "base_url": "https://www.reddit.com",
        "tools": [
            ("reddit_hot", "Get top hot posts from a subreddit (e.g. 'python' or 'technology')"),
            ("reddit_search", "Search Reddit posts across all subreddits by keyword"),
        ],
    },
    "gmail": {
        "label": "Gmail (Inbox, Search & Send)",
        "name": "Gmail",
        "short": "Gmail",
        "category": "Productivity",
        "description": "Search inbox messages, read email threads, list labels, and send emails via the Gmail REST API.",
        "key_label": "Gmail OAuth Access Token",
        "key_placeholder": "Paste Google OAuth Bearer token (ya29....) with gmail.modify / gmail.send scope",
        "setup_hint": "Generate a Bearer token from Google OAuth 2.0 Playground with Gmail API scopes and paste it above.",
        "requires_key": True,
        "base_url": "https://gmail.googleapis.com/gmail/v1",
        "tools": [
            ("gmail_search", "Search Gmail messages (e.g. 'is:unread' or 'from:boss@company.com')"),
            ("gmail_read", "Read the full body of a Gmail message by its message ID"),
            ("gmail_send", "Send an email formatted as: recipient@email.com | Subject | Message body"),
            ("gmail_labels", "List all Gmail folders and labels"),
        ],
    },
    "google_calendar": {
        "label": "Google Calendar (Schedule & Events)",
        "name": "Google Calendar",
        "short": "Calendar",
        "category": "Productivity",
        "description": "View upcoming events, search your schedule, and quick-add new calendar events.",
        "key_label": "Calendar OAuth Access Token",
        "key_placeholder": "Paste Google OAuth Bearer token (ya29....) with calendar scope",
        "setup_hint": "Use a Google OAuth 2.0 access token with https://www.googleapis.com/auth/calendar scope.",
        "requires_key": True,
        "base_url": "https://www.googleapis.com/calendar/v3",
        "tools": [
            ("gcal_upcoming", "List upcoming events on your primary Google Calendar"),
            ("gcal_search", "Search Google Calendar events by keyword"),
            ("gcal_quick_add", "Create an event from natural text (e.g. 'Team sync tomorrow at 3pm')"),
        ],
    },
    "slack": {
        "label": "Slack (Channels & Messaging)",
        "name": "Slack",
        "short": "Slack",
        "category": "Productivity",
        "description": "List workspace channels, read recent channel history, and post Slack messages.",
        "key_label": "Slack Bot / User Token",
        "key_placeholder": "Paste Slack token (xoxb-... or xoxp-...)",
        "setup_hint": "Create a Slack App at api.slack.com/apps with channels:read, channels:history, and chat:write.",
        "requires_key": True,
        "base_url": "https://slack.com/api",
        "tools": [
            ("slack_channels", "List public and private Slack channels with their IDs"),
            ("slack_history", "Read recent messages from a Slack channel ID"),
            ("slack_post", "Post a message formatted as: CHANNEL_ID | Message text"),
        ],
    },
    "discord": {
        "label": "Discord (Servers, Channels & Webhooks)",
        "name": "Discord",
        "short": "Discord",
        "category": "Productivity",
        "description": "Read Discord channel messages, list servers, or post messages via Bot Token or Webhook URL.",
        "key_label": "Discord Bot Token or Webhook URL",
        "key_placeholder": "Paste Discord Bot Token OR full https://discord.com/api/webhooks/... URL",
        "setup_hint": "Paste a Discord Channel Webhook URL for instant posting, or a Bot Token for reading/listing servers.",
        "requires_key": True,
        "base_url": "https://discord.com/api/v10",
        "tools": [
            ("discord_guilds", "List Discord servers (guilds) your bot belongs to"),
            ("discord_messages", "Read recent messages from a Discord channel ID"),
            ("discord_send", "Send a message (CHANNEL_ID | message, or plain text if using a Webhook URL)"),
        ],
    },
    "trello": {
        "label": "Trello (Boards & Cards)",
        "name": "Trello",
        "short": "Trello",
        "category": "Productivity",
        "description": "Inspect Trello boards, view cards, and create new task cards.",
        "key_label": "Trello API Key:Token",
        "key_placeholder": "Paste api_key:oauth_token (colon-separated)",
        "setup_hint": "Combine your Trello API Key and Token with a colon: your_api_key:your_token",
        "requires_key": True,
        "base_url": "https://api.trello.com/1",
        "tools": [
            ("trello_boards", "List your Trello boards and their IDs"),
            ("trello_cards", "List cards on a Trello board by board ID"),
            ("trello_create_card", "Create a card formatted as: LIST_ID | Card title | Description"),
        ],
    },
    "linear": {
        "label": "Linear (Issues & Project Tracking)",
        "name": "Linear",
        "short": "Linear",
        "category": "Dev & Media",
        "description": "Query Linear issues, list teams, and create new issues via GraphQL.",
        "key_label": "Linear Personal API Key",
        "key_placeholder": "Paste Linear API key (lin_api_...)",
        "setup_hint": "Generate a Personal API Key in Linear under Settings → Security & Access → Personal API keys.",
        "requires_key": True,
        "base_url": "https://api.linear.app/graphql",
        "tools": [
            ("linear_issues", "List or filter recent Linear issues"),
            ("linear_teams", "List Linear teams and their team IDs"),
            ("linear_create_issue", "Create an issue formatted as: TEAM_ID | Issue title | Description"),
        ],
    },
    "spotify": {
        "label": "Spotify (Now Playing, Search & Top Tracks)",
        "name": "Spotify",
        "short": "Spotify",
        "category": "Dev & Media",
        "description": "Check currently playing music, search tracks/artists, and inspect your top tracks.",
        "key_label": "Spotify OAuth Access Token",
        "key_placeholder": "Paste Spotify Bearer token (BQ...)",
        "setup_hint": "Paste a Spotify Web API OAuth token with user-read-currently-playing and user-top-read scopes.",
        "requires_key": True,
        "base_url": "https://api.spotify.com/v1",
        "tools": [
            ("spotify_now_playing", "Get the currently playing track on your Spotify account"),
            ("spotify_search", "Search Spotify for tracks or artists by query"),
            ("spotify_top", "List your top played Spotify tracks"),
        ],
    },
}

BUILTIN_CATALOG_EXTRAS = {
    "github": {
        "category": "Dev & Media",
        "setup_hint": "Create a Personal Access Token at github.com/settings/tokens (repo / read:user scopes).",
        "default_base_url": "https://api.github.com",
    },
    "youtube": {
        "category": "Dev & Media",
        "setup_hint": "Enable YouTube Data API v3 in Google Cloud Console and paste your API key.",
        "default_base_url": "https://www.googleapis.com/youtube/v3",
    },
    "google_drive": {
        "category": "Productivity",
        "setup_hint": "Paste a Google OAuth 2.0 Bearer token with drive.readonly or drive.metadata.readonly scope.",
        "default_base_url": "https://www.googleapis.com/drive/v3",
    },
    "notion": {
        "category": "Productivity",
        "setup_hint": "Create an Internal Integration at notion.so/my-integrations and share pages with it.",
        "default_base_url": "https://api.notion.com/v1",
    },
    "weather": {
        "category": "Dev & Media",
        "setup_hint": "Paste an OpenWeatherMap API key from home.openweathermap.org/api_keys.",
        "default_base_url": "https://api.openweathermap.org/data/2.5",
    },
    "custom": {
        "category": "Custom",
        "setup_hint": "Set your REST API Base URL (e.g. https://newsapi.org/v2) and optional API key / Bearer token.",
        "default_base_url": "https://newsapi.org/v2",
    },
}

KEYLESS_SERVICES = {
    k for k, v in EXTRA_API_SERVICES.items() if not v.get("requires_key", True)
}

EXTRA_TOOL_PREFIXES = (
    "free_news",
    "gmail_",
    "gcal_",
    "slack_",
    "discord_",
    "trello_",
    "linear_",
    "spotify_",
    "reddit_",
    "wiki_",
    "arxiv_",
    "crypto_",
    "fx_",
)


def get_all_service_catalog():
    """Return ordered list of service metadata dicts combining EXTRA_API_SERVICES and modes.SERVICE_SPECS."""
    catalog = []
    seen = set()

    for key, meta in EXTRA_API_SERVICES.items():
        seen.add(key)
        catalog.append(
            {
                "key": key,
                "name": meta["name"],
                "short": meta["short"],
                "label": meta["label"],
                "category": meta.get("category", "Productivity"),
                "requires_key": bool(meta.get("requires_key", True)),
                "requires_base_url": False,
                "default_base_url": meta.get("base_url", ""),
                "key_label": meta.get("key_label", "API Key"),
                "key_placeholder": meta.get("key_placeholder", "Paste API key or token"),
                "setup_hint": meta.get("setup_hint", ""),
                "description": meta.get("description", ""),
                "tools": list(meta.get("tools", [])),
            }
        )

    specs = getattr(modes, "SERVICE_SPECS", {}) or {}
    for key, spec in specs.items():
        if key in ("none", "") or key in seen or not isinstance(spec, dict):
            continue
        seen.add(key)
        extra = BUILTIN_CATALOG_EXTRAS.get(key, {})
        raw_tools = spec.get("tools") or []
        tools_list = []
        if isinstance(raw_tools, dict):
            tools_list = [(tid, desc) for tid, desc in raw_tools.items()]
        elif isinstance(raw_tools, list):
            for entry in raw_tools:
                if isinstance(entry, tuple) and len(entry) >= 2:
                    tools_list.append((entry[0], entry[1]))
                elif isinstance(entry, str):
                    tools_list.append((entry, f"Run {entry} tool"))

        catalog.append(
            {
                "key": key,
                "name": spec.get("name") or spec.get("short") or key.replace("_", " ").title(),
                "short": spec.get("short") or spec.get("name") or key,
                "label": spec.get("label") or spec.get("name") or key,
                "category": extra.get("category", "Custom" if key == "custom" else "Dev & Media"),
                "requires_key": bool(spec.get("requires_key", True)),
                "requires_base_url": key == "custom",
                "default_base_url": extra.get("default_base_url", spec.get("base_url", "")),
                "key_label": spec.get("key_label") or "API Key / Token",
                "key_placeholder": spec.get("key_placeholder")
                or spec.get("placeholder")
                or "Paste API key or Bearer token",
                "setup_hint": extra.get("setup_hint", ""),
                "description": spec.get("description") or spec.get("desc") or "",
                "tools": tools_list,
            }
        )

    return catalog


def register_extra_api_services():
    """Register all extended API services into modes.SERVICE_SPECS and wrap prompt/summary helpers."""
    specs = getattr(modes, "SERVICE_SPECS", None)
    if isinstance(specs, dict):
        sample_spec = next(
            (v for k, v in specs.items() if k != "none" and isinstance(v, dict)),
            {},
        )
        sample_tools = sample_spec.get("tools")

        built_specs = {}
        for svc_key, meta in EXTRA_API_SERVICES.items():
            raw_tools = meta["tools"]
            if isinstance(sample_tools, list) and sample_tools and isinstance(sample_tools[0], tuple):
                tools_val = list(raw_tools)
            elif isinstance(sample_tools, dict):
                tools_val = {tid: desc for tid, desc in raw_tools}
            else:
                tools_val = [tid for tid, _ in raw_tools]

            entry = {
                "label": meta["label"],
                "name": meta["name"],
                "short": meta["short"],
                "description": meta["description"],
                "desc": meta["description"],
                "key_label": meta["key_label"],
                "key_placeholder": meta["key_placeholder"],
                "placeholder": meta["key_placeholder"],
                "requires_key": bool(meta.get("requires_key", True)),
                "base_url": meta.get("base_url", ""),
                "tools": tools_val,
            }
            for extra_k, extra_v in sample_spec.items():
                if extra_k not in entry and isinstance(extra_v, str):
                    entry[extra_k] = ""
            built_specs[svc_key] = entry

        reordered = {}
        inserted = False
        for k, v in specs.items():
            if k in built_specs:
                continue
            reordered[k] = v
            if k == "none":
                reordered.update(built_specs)
                inserted = True
        if not inserted:
            reordered.update(built_specs)
        specs.clear()
        specs.update(reordered)

    orig_summary = getattr(modes, "get_agent_service_summary", None)
    if callable(orig_summary) and not getattr(orig_summary, "_extra_apis_wrapped", False):
        def _wrapped_service_summary(agent):
            if isinstance(agent, dict):
                stype = (agent.get("service_type") or "").strip().lower()
                if stype in EXTRA_API_SERVICES:
                    short_name = EXTRA_API_SERVICES[stype]["short"]
                    return f"{short_name} (No Key Needed)" if stype in KEYLESS_SERVICES else short_name
            return orig_summary(agent)

        _wrapped_service_summary._extra_apis_wrapped = True
        modes.get_agent_service_summary = _wrapped_service_summary

    orig_prompt = getattr(modes, "build_agent_system_prompt", None)
    if callable(orig_prompt) and not getattr(orig_prompt, "_extra_apis_wrapped", False):
        def _wrapped_build_agent_prompt(base_prompt, agent=None, *args, **kwargs):
            if isinstance(agent, dict):
                stype = (agent.get("service_type") or "").strip().lower()
                if stype in KEYLESS_SERVICES and not (agent.get("api_key") or "").strip():
                    patched_agent = dict(agent)
                    patched_agent["api_key"] = "built-in-keyless"
                    return orig_prompt(base_prompt, agent=patched_agent, *args, **kwargs)
            return orig_prompt(base_prompt, agent=agent, *args, **kwargs)

        _wrapped_build_agent_prompt._extra_apis_wrapped = True
        modes.build_agent_system_prompt = _wrapped_build_agent_prompt


def extract_agent_base_url(agent_profile):
    if not isinstance(agent_profile, dict):
        return ""
    for key in ("base_url", "custom_base_url", "api_base_url", "endpoint_url", "url"):
        val = (agent_profile.get(key) or "").strip()
        if val:
            return val.rstrip("/")
    return ""


def augment_custom_api_system_prompt(system_prompt, agent_profile):
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

    base_url = extract_agent_base_url(agent_profile)
    if service_type != "custom" and not base_url:
        return system_prompt

    if "newsapi.org" in base_url.lower():
        guidance = (
            "\n\n[CUSTOM REST API — NEWSAPI INSTRUCTIONS]\n"
            f"Base URL: {base_url}\n"
            "Authentication is injected automatically via request headers — NEVER put apiKey or YOUR_API_KEY in the URL.\n"
            "To fetch news, output ONLY a tool call tag using one of these endpoints:\n"
            "• [[CALL_API: custom_get | /top-headlines?country=us&pageSize=8]]\n"
            "• [[CALL_API: custom_get | /everything?q=your+search+terms&sortBy=publishedAt&language=en&pageSize=8]]\n"
            "Note: /top-headlines requires country, category, sources, or q; /everything requires q."
        )
    else:
        guidance = (
            "\n\n[CUSTOM REST API INSTRUCTIONS]\n"
            f"Base URL: {base_url or '(configured in API Studio)'}\n"
            "Authentication headers are attached automatically — do not embed placeholder API keys in URLs.\n"
            "Invoke endpoints with [[CALL_API: custom_get | /relative/endpoint?param=value]]."
        )
    return system_prompt + guidance


def infer_custom_api_fallback(user_query, agent_profile):
    if not isinstance(agent_profile, dict):
        return None
    service_type = (agent_profile.get("service_type") or "").strip().lower()
    base_url = extract_agent_base_url(agent_profile)
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
        topic = re.sub(
            r"^(?:search|find|play|look up)\s+(?:spotify\s+for\s+)?", "", q, flags=re.IGNORECASE
        ).strip(" ?!.")
        return ("spotify_search", topic or "top hits")

    if service_type == "reddit":
        sub_m = re.search(r"\br/([a-zA-Z0-9_]+)", q)
        if sub_m:
            return ("reddit_hot", sub_m.group(1))
        topic = re.sub(
            r"^(?:search|find|show|get)\s+(?:reddit\s+(?:for|about)\s+)?", "", q, flags=re.IGNORECASE
        ).strip(" ?!.")
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


def _http_json_request(url, headers=None, data_bytes=None, method="GET", timeout=25):
    req_headers = {"User-Agent": "Mosaic-Local-AI-Studio/1.0", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


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
        if service_type == "gmail" or tid.startswith("gmail_"):
            if not api_key:
                return ("Gmail requires a Google OAuth Access Token in API Studio or Edit Agent.", [])
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
                lines.append(
                    f"• {cid.capitalize()}: ${usd:,} USD / ${aud:,} AUD{chg_str}"
                    if isinstance(usd, (int, float)) and isinstance(aud, (int, float))
                    else f"• {cid.capitalize()}: {usd} USD / {aud} AUD{chg_str}"
                )
                sources.append({"title": f"{cid.capitalize()} Live Price", "url": f"https://www.coingecko.com/en/coins/{cid}"})
            return ("\n".join(lines), sources)

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


def execute_custom_api_request(tool_id, raw_arg, agent_profile, user_query=""):
    service_type = (agent_profile.get("service_type") or "").strip().lower()
    if service_type == "free_news" or tool_id.lower().startswith("free_news"):
        return _execute_free_news_request(raw_arg, user_query=user_query)
    if service_type in EXTRA_API_SERVICES or tool_id.lower().startswith(EXTRA_TOOL_PREFIXES):
        return _execute_extra_service_request(
            service_type, tool_id, raw_arg, agent_profile, user_query=user_query
        )

    base_url = extract_agent_base_url(agent_profile)
    api_key = (agent_profile.get("api_key") or "").strip()

    if not base_url:
        return (
            "Configuration Error: No API Base URL is configured for this Custom REST API. "
            "Open API Studio (or Edit Agent) and set the Base URL (for NewsAPI, use https://newsapi.org/v2).",
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
            inferred = infer_custom_api_fallback(user_query, agent_profile)
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


class ApiTestWorker(QThread):
    """Background worker that verifies live connectivity for any selected API service."""

    test_finished = Signal(bool, str)

    def __init__(self, service_key, api_key="", base_url=""):
        super().__init__()
        self._service_key = (service_key or "").strip().lower()
        self._api_key = (api_key or "").strip()
        self._base_url = (base_url or "").strip().rstrip("/")

    def run(self):
        svc = self._service_key
        key = self._api_key
        burl = self._base_url

        try:
            if svc == "free_news":
                out, _ = _execute_free_news_request("top")
                ok = not out.startswith("Free News lookup error:")
                self.test_finished.emit(ok, "Connected! Live news feed is reachable." if ok else out)
                return

            if svc == "wikipedia":
                data = _http_json_request(
                    "https://en.wikipedia.org/api/rest_v1/page/summary/Python_(programming_language)",
                    timeout=15,
                )
                ok = bool(data.get("title"))
                self.test_finished.emit(ok, "Connected! Wikipedia REST API is online." if ok else "Unexpected response.")
                return

            if svc == "arxiv":
                req = urllib.request.Request(
                    "http://export.arxiv.org/api/query?search_query=all:ai&max_results=1",
                    headers={"User-Agent": "Mosaic-Local-AI-Studio/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    ok = resp.status == 200
                self.test_finished.emit(ok, "Connected! arXiv preprint archive is reachable.")
                return

            if svc == "crypto":
                data = _http_json_request(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
                    timeout=15,
                )
                btc = (data.get("bitcoin") or {}).get("usd")
                if btc is not None:
                    self.test_finished.emit(True, f"Connected! CoinGecko live BTC price: ${btc:,} USD")
                else:
                    self.test_finished.emit(False, "CoinGecko returned an empty response.")
                return

            if svc == "currency":
                data = _http_json_request("https://open.er-api.com/v6/latest/USD", timeout=15)
                aud = (data.get("rates") or {}).get("AUD")
                if aud is not None:
                    self.test_finished.emit(True, f"Connected! Live FX rate: 1 USD = {aud} AUD")
                else:
                    self.test_finished.emit(False, "FX API did not return exchange rates.")
                return

            if svc == "reddit":
                data = _http_json_request(
                    "https://www.reddit.com/r/technology/hot.json?limit=1",
                    headers={"User-Agent": "desktop:MosaicLocalAI:v1.0 (by /u/mosaic_studio)"},
                    timeout=15,
                )
                ok = isinstance(data.get("data"), dict)
                self.test_finished.emit(ok, "Connected! Reddit public feed is reachable.")
                return

            if svc == "gmail":
                if not key:
                    self.test_finished.emit(False, "Paste your Gmail OAuth Bearer token first.")
                    return
                data = _http_json_request(
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                email = data.get("emailAddress", "authenticated account")
                self.test_finished.emit(True, f"Connected to Gmail ({email})!")
                return

            if svc == "google_calendar":
                if not key:
                    self.test_finished.emit(False, "Paste your Google Calendar OAuth token first.")
                    return
                data = _http_json_request(
                    "https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                ok = "items" in data
                self.test_finished.emit(ok, "Connected to Google Calendar!")
                return

            if svc == "slack":
                if not key:
                    self.test_finished.emit(False, "Paste your Slack xoxb- or xoxp- token first.")
                    return
                data = _http_json_request(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                if data.get("ok"):
                    self.test_finished.emit(True, f"Connected to Slack workspace '{data.get('team', 'Slack')}'!")
                else:
                    self.test_finished.emit(False, f"Slack auth failed: {data.get('error', 'invalid_auth')}")
                return

            if svc == "discord":
                if not key:
                    self.test_finished.emit(False, "Paste a Discord Webhook URL or Bot Token first.")
                    return
                if key.startswith(("http://", "https://")) and "/webhooks/" in key:
                    data = _http_json_request(key, timeout=15)
                    self.test_finished.emit(True, f"Connected to Discord Webhook '{data.get('name', 'Webhook')}'!")
                else:
                    auth = key if key.startswith("Bot ") else f"Bot {key}"
                    data = _http_json_request(
                        "https://discord.com/api/v10/users/@me",
                        headers={"Authorization": auth},
                        timeout=15,
                    )
                    self.test_finished.emit(True, f"Connected as Discord Bot '{data.get('username', 'Bot')}'!")
                return

            if svc == "trello":
                if ":" not in key:
                    self.test_finished.emit(False, "Enter Trello credentials as api_key:token.")
                    return
                tk, tt = key.split(":", 1)
                data = _http_json_request(
                    f"https://api.trello.com/1/members/me?key={urllib.parse.quote(tk.strip())}&token={urllib.parse.quote(tt.strip())}",
                    timeout=15,
                )
                self.test_finished.emit(True, f"Connected to Trello (@{data.get('username', 'user')})!")
                return

            if svc == "linear":
                if not key:
                    self.test_finished.emit(False, "Paste your Linear Personal API Key first.")
                    return
                data = _http_json_request(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": key, "Content-Type": "application/json"},
                    data_bytes=json.dumps({"query": "{ viewer { name } }"}).encode("utf-8"),
                    method="POST",
                    timeout=15,
                )
                viewer = ((data.get("data") or {}).get("viewer") or {}).get("name")
                if viewer:
                    self.test_finished.emit(True, f"Connected to Linear as {viewer}!")
                else:
                    self.test_finished.emit(False, "Linear authentication failed.")
                return

            if svc == "spotify":
                if not key:
                    self.test_finished.emit(False, "Paste your Spotify OAuth Bearer token first.")
                    return
                data = _http_json_request(
                    "https://api.spotify.com/v1/me",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                self.test_finished.emit(True, f"Connected to Spotify ({data.get('display_name', 'Account')})!")
                return

            if svc == "github":
                if not key:
                    self.test_finished.emit(False, "Paste your GitHub Personal Access Token first.")
                    return
                data = _http_json_request(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                self.test_finished.emit(True, f"Connected to GitHub (@{data.get('login', 'user')})!")
                return

            if svc == "youtube":
                if not key:
                    self.test_finished.emit(False, "Paste your YouTube Data API v3 key first.")
                    return
                data = _http_json_request(
                    f"https://www.googleapis.com/youtube/v3/search?part=snippet&q=python&maxResults=1&key={urllib.parse.quote(key)}",
                    timeout=15,
                )
                ok = "items" in data
                self.test_finished.emit(ok, "Connected to YouTube Data API v3!")
                return

            if svc == "google_drive":
                if not key:
                    self.test_finished.emit(False, "Paste your Google Drive OAuth Bearer token first.")
                    return
                data = _http_json_request(
                    "https://www.googleapis.com/drive/v3/about?fields=user",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=15,
                )
                user_name = ((data.get("user") or {}).get("displayName")) or "Google Drive"
                self.test_finished.emit(True, f"Connected to Google Drive ({user_name})!")
                return

            if svc == "notion":
                if not key:
                    self.test_finished.emit(False, "Paste your Notion Integration Secret first.")
                    return
                data = _http_json_request(
                    "https://api.notion.com/v1/users/me",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Notion-Version": "2022-06-28",
                    },
                    timeout=15,
                )
                self.test_finished.emit(True, f"Connected to Notion ({data.get('name', 'Integration')})!")
                return

            if svc == "weather":
                if not key:
                    self.test_finished.emit(False, "Paste your OpenWeatherMap API key first.")
                    return
                data = _http_json_request(
                    f"https://api.openweathermap.org/data/2.5/weather?q=Melbourne&appid={urllib.parse.quote(key)}",
                    timeout=15,
                )
                ok = str(data.get("cod")) == "200"
                self.test_finished.emit(ok, "Connected to OpenWeatherMap!")
                return

            if svc == "custom":
                if not burl:
                    self.test_finished.emit(False, "Enter an API Base URL first (e.g. https://newsapi.org/v2).")
                    return
                target = burl if burl.startswith(("http://", "https://")) else f"https://{burl}"
                if "newsapi.org" in target.lower():
                    if not key:
                        self.test_finished.emit(False, "NewsAPI requires your API key from newsapi.org.")
                        return
                    data = _http_json_request(
                        f"{target}/top-headlines?country=us&pageSize=1",
                        headers={"X-Api-Key": key},
                        timeout=15,
                    )
                    ok = data.get("status") == "ok"
                    self.test_finished.emit(ok, "Connected to NewsAPI!" if ok else str(data.get("message", "Error")))
                    return

                hdrs = {}
                if key:
                    hdrs["Authorization"] = key if key.lower().startswith(("bearer ", "token ")) else f"Bearer {key}"
                    hdrs["X-Api-Key"] = key
                req = urllib.request.Request(
                    target,
                    headers={"User-Agent": "Mosaic-Local-AI-Studio/1.0", **hdrs},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    self.test_finished.emit(True, f"Endpoint reachable (HTTP {resp.status})!")
                return

            self.test_finished.emit(False, "Select an API service from the left catalog first.")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                raw_e = e.read().decode("utf-8", errors="replace")
                parsed_e = json.loads(raw_e)
                detail = parsed_e.get("message") or parsed_e.get("error", {}).get("message") or raw_e[:140]
            except Exception:
                detail = str(e.reason)
            self.test_finished.emit(False, f"HTTP {e.code}: {detail}")
        except Exception as e:
            self.test_finished.emit(False, f"Connection failed: {e}")


def _make_badge_dot(color_hex, size=10):
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QPen(QColor(255, 255, 255, 90), 1.0))
    painter.setBrush(QColor(color_hex))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.end()
    return QIcon(pm)


class ApiHubDialog(QDialog):
    """Dedicated UI for browsing, configuring, and testing external APIs in Mosaic."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mosaic API & Integrations Studio")
        self.resize(840, 620)
        self.settings = settings.load_settings()
        self.palette = settings.get_palette(self.settings)
        self.setStyleSheet(settings.build_stylesheet(self.palette))

        self._catalog = get_all_service_catalog()
        self._catalog_by_key = {item["key"]: item for item in self._catalog}
        self._selected_key = self.settings.get("chat_api_service", "free_news")
        if self._selected_key not in self._catalog_by_key:
            self._selected_key = "free_news"

        # Per-session credentials store so switching services in the list doesn't lose edits
        self._draft_keys = {self._selected_key: self.settings.get("chat_api_key", "")}
        self._draft_urls = {self._selected_key: self.settings.get("chat_api_base_url", "")}
        self._active_category = "All"
        self._test_worker = None

        self._build_ui()
        self._populate_catalog()
        self._select_service_in_list(self._selected_key)

    def _build_ui(self):
        p = self.palette
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        # Header Bar
        hdr_row = QHBoxLayout()
        hdr_col = QVBoxLayout()
        hdr_col.setSpacing(2)
        title = QLabel("API & Integrations Studio")
        title.setObjectName("sectionHeading")
        subtitle = QLabel(
            "Connect external services or zero-key live data feeds to Chat Mode — separate from general Settings."
        )
        subtitle.setObjectName("muted")
        hdr_col.addWidget(title)
        hdr_col.addWidget(subtitle)
        hdr_row.addLayout(hdr_col, 1)

        self.enable_chat_api_cb = QCheckBox("Enable API Access in Chat Mode")
        self.enable_chat_api_cb.setChecked(
            bool(
                self.settings.get("chat_api_enabled", False)
                and self.settings.get("chat_api_service", "none") not in ("", "none")
            )
        )
        self.enable_chat_api_cb.setStyleSheet("font-weight: bold;")
        hdr_row.addWidget(self.enable_chat_api_cb)
        outer.addLayout(hdr_row)

        # Category Filter Pills + Search Row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self._cat_buttons = {}
        for cat in ("All", "No Key Needed", "Productivity", "Dev & Media", "Custom"):
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setChecked(cat == "All")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked=False, c=cat: self._set_category(c))
            self._cat_buttons[cat] = btn
            filter_row.addWidget(btn)

        filter_row.addSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter APIs (e.g. Gmail, Free News, Crypto, Slack)...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._populate_catalog)
        filter_row.addWidget(self.search_input, 1)
        outer.addLayout(filter_row)
        self._style_category_buttons()

        # Two-Pane Body
        body_row = QHBoxLayout()
        body_row.setSpacing(14)

        # Left Pane: Service Catalog
        left_card = QFrame()
        left_card.setObjectName("settingsCard")
        left_card.setFixedWidth(275)
        left_lay = QVBoxLayout(left_card)
        left_lay.setContentsMargins(8, 8, 8, 8)
        left_lay.setSpacing(6)

        cat_hdr = QLabel("Available Services")
        cat_hdr.setObjectName("settingTitle")
        cat_hdr.setStyleSheet("padding: 2px 4px;")
        left_lay.addWidget(cat_hdr)

        self.service_list = QListWidget()
        self.service_list.setObjectName("chatList")
        self.service_list.setIconSize(QSize(10, 10))
        self.service_list.currentItemChanged.connect(self._on_service_item_changed)
        left_lay.addWidget(self.service_list, 1)
        body_row.addWidget(left_card)

        # Right Pane: Selected Service Inspector & Credentials
        right_scroll = QScrollArea()
        right_scroll.setObjectName("settingsScroll")
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)

        right_page = QWidget()
        right_page.setObjectName("settingsPage")
        right_lay = QVBoxLayout(right_page)
        right_lay.setContentsMargins(0, 0, 4, 0)
        right_lay.setSpacing(12)

        # Card 1: Service Overview
        overview_card = QFrame()
        overview_card.setObjectName("settingsCard")
        ov_lay = QVBoxLayout(overview_card)
        ov_lay.setContentsMargins(16, 14, 16, 14)
        ov_lay.setSpacing(8)

        ov_top = QHBoxLayout()
        self.svc_title_lbl = QLabel("Free News")
        self.svc_title_lbl.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {p['text_primary']};")
        ov_top.addWidget(self.svc_title_lbl)

        self.svc_auth_badge = QLabel("NO KEY NEEDED")
        self.svc_auth_badge.setObjectName("brandBadge")
        ov_top.addWidget(self.svc_auth_badge)
        ov_top.addStretch()
        ov_lay.addLayout(ov_top)

        self.svc_desc_lbl = QLabel("")
        self.svc_desc_lbl.setWordWrap(True)
        self.svc_desc_lbl.setStyleSheet(f"color: {p['text_secondary']}; line-height: 1.4;")
        ov_lay.addWidget(self.svc_desc_lbl)

        self.svc_hint_lbl = QLabel("")
        self.svc_hint_lbl.setWordWrap(True)
        self.svc_hint_lbl.setObjectName("muted")
        ov_lay.addWidget(self.svc_hint_lbl)
        right_lay.addWidget(overview_card)

        # Card 2: Credentials & Endpoint Configuration
        cred_card = QFrame()
        cred_card.setObjectName("settingsCard")
        cred_lay = QVBoxLayout(cred_card)
        cred_lay.setContentsMargins(16, 14, 16, 14)
        cred_lay.setSpacing(10)

        cred_hdr = QLabel("Authentication & Endpoint")
        cred_hdr.setObjectName("settingTitle")
        cred_lay.addWidget(cred_hdr)

        self.keyless_banner = QLabel(
            "✓ No account, API key, or Base URL required — this integration works out of the box."
        )
        self.keyless_banner.setWordWrap(True)
        self.keyless_banner.setStyleSheet(
            f"background-color: {p['bg_elevated']}; color: {p['green']}; "
            f"border: 1px solid {p['green']}; border-radius: 8px; padding: 8px 10px; font-weight: 600;"
        )
        cred_lay.addWidget(self.keyless_banner)

        key_row = QHBoxLayout()
        self.key_lbl = QLabel("API Key:")
        self.key_lbl.setFixedWidth(115)
        key_row.addWidget(self.key_lbl)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.textEdited.connect(self._on_key_edited)
        key_row.addWidget(self.key_edit, 1)

        self.show_key_btn = QPushButton("Show")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.setFixedWidth(62)
        self.show_key_btn.toggled.connect(self._toggle_key_vis)
        key_row.addWidget(self.show_key_btn)
        cred_lay.addLayout(key_row)

        url_row = QHBoxLayout()
        self.url_lbl = QLabel("Base URL:")
        self.url_lbl.setFixedWidth(115)
        url_row.addWidget(self.url_lbl)

        self.url_edit = QLineEdit()
        self.url_edit.textEdited.connect(self._on_url_edited)
        url_row.addWidget(self.url_edit, 1)
        cred_lay.addLayout(url_row)

        # Live Test Connection Row
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.clicked.connect(self._run_connection_test)
        test_row.addWidget(self.test_btn)

        self.test_status_lbl = QLabel("")
        self.test_status_lbl.setWordWrap(True)
        self.test_status_lbl.setObjectName("muted")
        test_row.addWidget(self.test_status_lbl, 1)
        cred_lay.addLayout(test_row)

        self.confirm_tools_cb = QCheckBox("Ask my confirmation before running API calls in Chat Mode")
        self.confirm_tools_cb.setChecked(bool(self.settings.get("chat_api_confirm", False)))
        cred_lay.addWidget(self.confirm_tools_cb)

        right_lay.addWidget(cred_card)

        # Card 3: Built-In Tools Available to Mosaic
        tools_card = QFrame()
        tools_card.setObjectName("settingsCard")
        tools_lay = QVBoxLayout(tools_card)
        tools_lay.setContentsMargins(16, 14, 16, 14)
        tools_lay.setSpacing(6)

        tools_hdr = QLabel("Tools Exposed to Mosaic")
        tools_hdr.setObjectName("settingTitle")
        tools_lay.addWidget(tools_hdr)

        self.tools_list_lbl = QLabel("")
        self.tools_list_lbl.setWordWrap(True)
        self.tools_list_lbl.setStyleSheet(f"color: {p['text_secondary']}; line-height: 1.45; font-size: 12px;")
        tools_lay.addWidget(self.tools_list_lbl)
        right_lay.addWidget(tools_card)

        right_lay.addStretch()
        right_scroll.setWidget(right_page)
        body_row.addWidget(right_scroll, 1)
        outer.addLayout(body_row, 1)

        # Footer Action Bar
        footer = QHBoxLayout()
        disable_btn = QPushButton("Turn Off Chat API")
        disable_btn.setToolTip("Disable Chat Mode API calls without deleting your saved credentials")
        disable_btn.clicked.connect(self._disable_and_close)
        footer.addWidget(disable_btn)

        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save & Activate")
        save_btn.setObjectName("send")
        save_btn.clicked.connect(self._save_and_accept)

        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)
        outer.addLayout(footer)

    def _style_category_buttons(self):
        p = self.palette
        for cat, btn in self._cat_buttons.items():
            active = cat == self._active_category
            btn.blockSignals(True)
            btn.setChecked(active)
            btn.blockSignals(False)
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {p['accent']}; color: #ffffff; "
                    f"border: 1px solid {p['accent']}; border-radius: 14px; padding: 3px 12px; font-weight: bold; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {p['bg_card']}; color: {p['text_secondary']}; "
                    f"border: 1px solid {p['border']}; border-radius: 14px; padding: 3px 12px; }}"
                )

    def _set_category(self, cat):
        self._active_category = cat
        self._style_category_buttons()
        self._populate_catalog()

    def _populate_catalog(self):
        p = self.palette
        query = (self.search_input.text() if hasattr(self, "search_input") else "").strip().lower()
        current_key = self._selected_key

        self.service_list.blockSignals(True)
        self.service_list.clear()

        for item in self._catalog:
            if self._active_category != "All" and item["category"] != self._active_category:
                continue
            if query:
                hay = f"{item['name']} {item['short']} {item['category']} {item['description']}".lower()
                if query not in hay:
                    continue

            suffix = "  •  Free" if not item["requires_key"] else ""
            lw_item = QListWidgetItem(f"{item['name']}{suffix}")
            lw_item.setData(Qt.UserRole, item["key"])
            dot_col = p["green"] if not item["requires_key"] else p["accent"]
            lw_item.setIcon(_make_badge_dot(dot_col, size=9))
            lw_item.setToolTip(item["description"])
            self.service_list.addItem(lw_item)
            if item["key"] == current_key:
                self.service_list.setCurrentItem(lw_item)

        self.service_list.blockSignals(False)
        if self.service_list.currentItem() is None and self.service_list.count() > 0:
            self.service_list.setCurrentRow(0)
            self._on_service_item_changed(self.service_list.currentItem(), None)

    def _select_service_in_list(self, service_key):
        for i in range(self.service_list.count()):
            it = self.service_list.item(i)
            if it and it.data(Qt.UserRole) == service_key:
                self.service_list.setCurrentRow(i)
                self._load_service_details(service_key)
                return
        if self._catalog:
            self._load_service_details(self._catalog[0]["key"])

    def _on_service_item_changed(self, current, _previous):
        if current is None:
            return
        svc_key = current.data(Qt.UserRole)
        if svc_key:
            self._selected_key = svc_key
            self._load_service_details(svc_key)

    def _load_service_details(self, svc_key):
        p = self.palette
        meta = self._catalog_by_key.get(svc_key)
        if not meta:
            return

        self.svc_title_lbl.setText(meta["name"])
        if meta["requires_key"]:
            self.svc_auth_badge.setText("API KEY / TOKEN")
            self.svc_auth_badge.setStyleSheet(
                f"background-color: {p['bg_elevated']}; color: {p['accent']}; "
                f"border: 1px solid {p['border']}; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
            )
        else:
            self.svc_auth_badge.setText("FREE • NO KEY NEEDED")
            self.svc_auth_badge.setStyleSheet(
                f"background-color: {p['bg_elevated']}; color: {p['green']}; "
                f"border: 1px solid {p['green']}; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold;"
            )

        self.svc_desc_lbl.setText(meta["description"])
        self.svc_hint_lbl.setText(meta["setup_hint"])

        is_keyless = not meta["requires_key"]
        self.keyless_banner.setVisible(is_keyless)
        self.key_lbl.setVisible(not is_keyless)
        self.key_edit.setVisible(not is_keyless)
        self.show_key_btn.setVisible(not is_keyless)

        show_url = bool(meta["requires_base_url"] or meta["key"] == "custom")
        self.url_lbl.setVisible(show_url)
        self.url_edit.setVisible(show_url)

        self.key_lbl.setText(f"{meta['short']} Key:")
        self.key_edit.setPlaceholderText(meta["key_placeholder"])
        self.key_edit.blockSignals(True)
        self.key_edit.setText(self._draft_keys.get(svc_key, ""))
        self.key_edit.blockSignals(False)

        self.url_edit.setPlaceholderText(
            f"e.g. {meta['default_base_url'] or 'https://api.example.com/v1'}"
        )
        self.url_edit.blockSignals(True)
        self.url_edit.setText(self._draft_urls.get(svc_key, ""))
        self.url_edit.blockSignals(False)

        self.test_status_lbl.setText("")
        self.test_status_lbl.setStyleSheet(f"color: {p['text_muted']}; font-size: 12px;")

        if meta["tools"]:
            lines = [f"• <b>{tid}</b> — {desc}" for tid, desc in meta["tools"]]
            self.tools_list_lbl.setText("<br>".join(lines))
        else:
            self.tools_list_lbl.setText("• Custom REST GET/POST endpoints via your configured Base URL.")

    def _on_key_edited(self, text):
        self._draft_keys[self._selected_key] = text

    def _on_url_edited(self, text):
        self._draft_urls[self._selected_key] = text

    def _toggle_key_vis(self, checked):
        self.key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.show_key_btn.setText("Hide" if checked else "Show")

    def _run_connection_test(self):
        if self._test_worker is not None and self._test_worker.isRunning():
            return
        p = self.palette
        self.test_btn.setEnabled(False)
        self.test_status_lbl.setStyleSheet(f"color: {p['yellow']}; font-size: 12px;")
        self.test_status_lbl.setText("Testing live connection...")

        self._test_worker = ApiTestWorker(
            service_key=self._selected_key,
            api_key=self.key_edit.text().strip(),
            base_url=self.url_edit.text().strip(),
        )
        self._test_worker.test_finished.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success, message):
        self._test_worker = None
        self.test_btn.setEnabled(True)
        p = self.palette
        col = p["green"] if success else p["red"]
        self.test_status_lbl.setStyleSheet(f"color: {col}; font-weight: 600; font-size: 12px;")
        self.test_status_lbl.setText(message)

    def _disable_and_close(self):
        self.settings = settings.save_settings({"chat_api_enabled": False})
        self.accept()

    def _save_and_accept(self):
        svc_key = self._selected_key or "free_news"
        meta = self._catalog_by_key.get(svc_key, {})
        key_val = "" if not meta.get("requires_key", True) else self.key_edit.text().strip()
        url_val = self.url_edit.text().strip().rstrip("/")

        updates = {
            "chat_api_enabled": bool(self.enable_chat_api_cb.isChecked()),
            "chat_api_service": svc_key,
            "chat_api_key": key_val,
            "chat_api_base_url": url_val,
            "chat_api_confirm": bool(self.confirm_tools_cb.isChecked()),
        }
        self.settings = settings.save_settings(updates)
        self.accept()

    def closeEvent(self, event):
        if self._test_worker is not None and self._test_worker.isRunning():
            self._test_worker.wait(1500)
        event.accept()


register_extra_api_services()