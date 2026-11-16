import json
import re
import time
import uuid
from pathlib import Path

import requests

DATA_DIR = Path.home() / ".mosaic"
MEMORIES_FILE = DATA_DIR / "memories.json"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_memories():
    _ensure_dir()
    if not MEMORIES_FILE.exists():
        return []
    try:
        data = json.loads(MEMORIES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cleaned = []
            for item in data:
                if isinstance(item, dict) and item.get("text"):
                    cleaned.append(
                        {
                            "id": item.get("id") or uuid.uuid4().hex[:12],
                            "text": str(item["text"]).strip(),
                            "category": item.get("category", "general"),
                            "created_at": item.get("created_at", 0),
                        }
                    )
            return cleaned
    except (OSError, json.JSONDecodeError):
        pass
    return []


def save_memories(memories):
    _ensure_dir()
    MEMORIES_FILE.write_text(
        json.dumps(memories, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _normalize(text):
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()


def add_memory(text, category="general", replace_prefix=None):
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return None
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."

    memories = load_memories()
    norm_new = _normalize(cleaned)

    updated = []
    for m in memories:
        existing = m["text"]
        if _normalize(existing) == norm_new:
            return None
        if replace_prefix and existing.lower().startswith(replace_prefix.lower()):
            continue
        updated.append(m)

    updated.insert(
        0,
        {
            "id": uuid.uuid4().hex[:12],
            "text": cleaned,
            "category": category,
            "created_at": time.time(),
        },
    )
    save_memories(updated)
    return cleaned


def update_memory(mem_id, new_text):
    cleaned = " ".join(new_text.strip().split())
    if not cleaned:
        return
    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    memories = load_memories()
    for m in memories:
        if m["id"] == mem_id:
            m["text"] = cleaned
            break
    save_memories(memories)


def delete_memory(mem_id):
    memories = [m for m in load_memories() if m.get("id") != mem_id]
    save_memories(memories)


def clear_memories():
    save_memories([])


_QUESTION_STARTERS = (
    "what ",
    "who ",
    "where ",
    "when ",
    "why ",
    "how ",
    "do you ",
    "did i ",
    "can you tell ",
    "could you tell ",
    "is my ",
    "am i ",
)

_EXPLICIT_PATTERNS = [
    re.compile(
        r"^\s*(?:please\s+|hey\s+mosaic[,\s]+)?(?:remember|memorize|keep in mind|note|don'?t forget)"
        r"(?:\s+that|\s+to|\s*:)?\s+(.+)$",
        flags=re.IGNORECASE | re.DOTALL,
    ),
]

_NATURAL_PATTERNS = [
    (
        re.compile(r"\b(?:my name is|call me|i go by)\s+([A-Za-z][A-Za-z0-9 _'-]{1,30})", re.I),
        "identity",
        "User's name is ",
        lambda m: f"User's name is {m.group(1).strip().rstrip('.,!')}",
    ),
    (
        re.compile(r"\bi(?:'m| am)\s+(\d{1,3})\s+years?\s+old\b", re.I),
        "identity",
        "User is ",
        lambda m: f"User is {m.group(1)} years old",
    ),
    (
        re.compile(r"\bi\s+(?:live in|am from|am based in)\s+([A-Za-z0-9 ,'-]{2,45})", re.I),
        "profile",
        "User lives in ",
        lambda m: f"User lives in {m.group(1).strip().rstrip('.,!')}",
    ),
    (
        re.compile(r"\bi\s+(?:prefer|like it when you|want you to)\s+([^.!?\n]{4,100})", re.I),
        "preference",
        None,
        lambda m: f"User prefers {m.group(1).strip()}",
    ),
    (
        re.compile(r"\bmy favorite\s+([a-zA-Z0-9 _-]{2,25})\s+is\s+([^.!?\n]{2,60})", re.I),
        "preference",
        None,
        lambda m: f"User's favorite {m.group(1).strip().lower()} is {m.group(2).strip()}",
    ),
    (
        re.compile(r"\bi(?:'m| am)\s+(?:learning|studying|building|working on)\s+([^.!?\n]{3,90})", re.I),
        "context",
        None,
        lambda m: f"User is working on/learning {m.group(1).strip()}",
    ),
]


def _humanize_explicit(raw_fact):
    text = raw_fact.strip().rstrip(".")
    replacements = [
        (r"\bmy\b", "the user's"),
        (r"\bi am\b", "the user is"),
        (r"\bi'm\b", "the user is"),
        (r"\bi have\b", "the user has"),
        (r"\bi've\b", "the user has"),
        (r"\bi\b", "the user"),
        (r"\bme\b", "the user"),
    ]
    out = text
    for pattern, repl in replacements:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    return out[0].upper() + out[1:] if out else text


def extract_memories_from_text(user_text):
    text = user_text.strip()
    if not text:
        return []

    lowered = text.lower()
    if text.endswith("?") or lowered.startswith(_QUESTION_STARTERS):
        return []

    saved = []

    for pat in _EXPLICIT_PATTERNS:
        match = pat.match(text)
        if match:
            raw_fact = match.group(1).strip()
            if len(raw_fact) >= 3:
                fact = _humanize_explicit(raw_fact)
                stored = add_memory(fact, category="explicit")
                if stored:
                    saved.append(stored)
            return saved

    for pat, category, prefix, formatter in _NATURAL_PATTERNS:
        match = pat.search(text)
        if match:
            fact = formatter(match)
            if len(fact) >= 6:
                stored = add_memory(fact, category=category, replace_prefix=prefix)
                if stored:
                    saved.append(stored)

    return saved


def extract_memories_with_llm(base_url, model, user_msg, assistant_msg):
    if not user_msg or len(user_msg.strip()) < 6:
        return []

    prompt = (
        "Analyze the user's message below and extract ONLY durable personal facts, "
        "identity details, ongoing projects, or lasting preferences about the user. "
        "Ignore temporary questions, math problems, code snippets, or general knowledge.\n"
        "Respond ONLY with a JSON array of short third-person strings "
        '(e.g., ["User is building a PySide6 app", "User prefers concise answers"]). '
        "If there is nothing worth remembering long-term, respond with [].\n\n"
        f"User message: {user_msg[:1500]}\n"
        f"Assistant reply: {assistant_msg[:600]}"
    )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        r = requests.post(f"{base_url}/api/chat", json=payload, timeout=25)
        if r.status_code != 200:
            return []
        raw = r.json().get("message", {}).get("content", "").strip()
        match = re.search(r"\[.*?\]", raw, flags=re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group(0))
        if not isinstance(items, list):
            return []
        saved = []
        for item in items[:3]:
            if isinstance(item, str) and 4 <= len(item.strip()) <= 140:
                stored = add_memory(item.strip(), category="auto")
                if stored:
                    saved.append(stored)
        return saved
    except Exception:
        return []


def get_relevant_memories(query="", limit=20):
    memories = load_memories()
    if not memories or not query:
        return memories[:limit]

    words = {w for w in re.findall(r"[a-z0-9]{3,}", query.lower())}
    if not words:
        return memories[:limit]

    scored = []
    for idx, m in enumerate(memories):
        mem_words = set(re.findall(r"[a-z0-9]{3,}", m["text"].lower()))
        overlap = len(words & mem_words)
        cat_boost = 1.5 if m.get("category") in ("identity", "preference") else 0.0
        recency_boost = max(0.0, 1.0 - (idx * 0.03))
        scored.append((overlap * 3.0 + cat_boost + recency_boost, m))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [m for _, m in scored[:limit]]


def build_memory_prompt(query="", memories=None, limit=20):
    items = memories if memories is not None else get_relevant_memories(query=query, limit=limit)
    if not items:
        return ""

    bullet_lines = "\n".join(f"- {m['text']}" for m in items)
    return (
        "\n\n### USER PROFILE & SAVED MEMORIES\n"
        "You know the following facts and preferences about the user. "
        "Apply them naturally and consistently in your responses whenever relevant "
        "(for example, use their name if known, respect their preferences, and tailor examples to their context). "
        "Do not recite this list unless the user asks what you remember:\n"
        f"{bullet_lines}"
    )