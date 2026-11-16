from datetime import datetime
import html
import os
import re
from urllib.parse import parse_qs, unquote, urlparse

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_TRIVIAL_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "yo",
    "sup",
    "thanks",
    "thank you",
    "thx",
    "ok",
    "okay",
    "cool",
    "nice",
    "great",
    "bye",
    "goodbye",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
}

_FOLLOWUP_TOKENS = {
    "it",
    "its",
    "this",
    "that",
    "those",
    "these",
    "they",
    "them",
    "their",
    "he",
    "him",
    "his",
    "she",
    "her",
    "hers",
    "more",
    "details",
    "elaborate",
    "explain",
    "why",
    "when",
    "where",
    "who",
    "how",
}


def should_search_web(user_text):
    cleaned = re.sub(r"[^\w\s]", "", (user_text or "").strip().lower())
    if not cleaned:
        return False
    if cleaned in _TRIVIAL_MESSAGES:
        return False
    return True


def build_search_query(user_text, history_messages=None):
    text = re.sub(r"\s+", " ", (user_text or "")).strip()
    if not text:
        return ""

    words = re.findall(r"[a-zA-Z0-9']+", text.lower())
    if (
        history_messages
        and len(words) <= 6
        and any(w in _FOLLOWUP_TOKENS for w in words)
    ):
        for prev in reversed(history_messages):
            if prev.get("role") == "user":
                prev_text = prev.get("content", "")
                prev_text = re.sub(r"\*\*Attached:.*$", "", prev_text, flags=re.DOTALL).strip()
                prev_text = re.sub(r"\s+", " ", prev_text)
                if prev_text and prev_text.lower() != text.lower():
                    combined = f"{prev_text[:110]} {text}"
                    return combined[:180].strip()
    return text[:180].strip()


def _clean_ddg_url(raw_href):
    href = html.unescape(raw_href or "").strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return href


def _strip_tags(text):
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_ddg_html(page_html, max_results=5):
    results = []
    seen_urls = set()
    link_re = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snip_re = re.compile(
        r'<(?:a|div|span)[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div|span)>',
        re.IGNORECASE | re.DOTALL,
    )
    links = link_re.findall(page_html)
    snippets = snip_re.findall(page_html)
    for idx, (href, raw_title) in enumerate(links):
        url = _clean_ddg_url(href)
        title = _strip_tags(raw_title)
        snippet = _strip_tags(snippets[idx]) if idx < len(snippets) else ""
        if not title or not url or not url.startswith(("http://", "https://")):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


def _parse_ddg_lite(page_html, max_results=5):
    results = []
    seen_urls = set()
    link_re = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]+class=[\'"]?result-link[\'"]?[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snip_re = re.compile(
        r'<td[^>]+class=[\'"]?result-snippet[\'"]?[^>]*>(.*?)</td>',
        re.IGNORECASE | re.DOTALL,
    )
    links = link_re.findall(page_html)
    snippets = snip_re.findall(page_html)
    for idx, (href, raw_title) in enumerate(links):
        url = _clean_ddg_url(href)
        title = _strip_tags(raw_title)
        snippet = _strip_tags(snippets[idx]) if idx < len(snippets) else ""
        if not title or not url or not url.startswith(("http://", "https://")):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


def _search_ollama_cloud(query, max_results=5, timeout=8.0):
    api_key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not api_key:
        return []
    r = requests.post(
        "https://ollama.com/api/web_search",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": query, "max_results": max_results},
        timeout=timeout,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("results", [])[:max_results]:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        snippet = (item.get("content") or item.get("snippet") or "").strip()
        if title and url:
            out.append({"title": title, "url": url, "snippet": snippet[:500]})
    return out


def _search_ddg_html(query, max_results=5, timeout=8.0):
    r = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=_HEADERS,
        timeout=timeout,
    )
    r.raise_for_status()
    return _parse_ddg_html(r.text, max_results=max_results)


def _search_ddg_lite(query, max_results=5, timeout=8.0):
    r = requests.post(
        "https://lite.duckduckgo.com/lite/",
        data={"q": query},
        headers=_HEADERS,
        timeout=timeout,
    )
    r.raise_for_status()
    return _parse_ddg_lite(r.text, max_results=max_results)


def _search_ddg_instant(query, max_results=5, timeout=6.0):
    r = requests.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
        headers=_HEADERS,
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    results = []
    abstract = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or query).strip()
    if abstract and abstract_url:
        results.append({"title": heading, "url": abstract_url, "snippet": abstract})

    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if isinstance(topic, dict) and "FirstURL" in topic and "Text" in topic:
            results.append(
                {
                    "title": topic["Text"].split(" - ")[0][:90],
                    "url": topic["FirstURL"],
                    "snippet": topic["Text"],
                }
            )
    return results[:max_results]


def search_web(query, max_results=5):
    clean_q = (query or "").strip()
    if not clean_q:
        return []

    providers = (
        _search_ollama_cloud,
        _search_ddg_html,
        _search_ddg_lite,
        _search_ddg_instant,
    )
    for provider in providers:
        try:
            items = provider(clean_q, max_results=max_results)
            if items:
                return items
        except Exception:
            continue
    return []


def format_search_context(query, results):
    if not results:
        return ""
    now_str = datetime.now().strftime("%A, %B %d, %Y")
    lines = [
        f"\n\n[Live Web Search Results — Current Date: {now_str}]",
        f'Search Query: "{query}"',
        "Use the web search results below when answering questions that benefit from current, factual, or real-time information. "
        "Cite sources inline as Markdown links like [Source Title](URL) when you use them. "
        "If the results are unrelated to the user's request, rely on your own knowledge.",
        "",
    ]
    for idx, item in enumerate(results, 1):
        title = item.get("title", "Source")
        url = item.get("url", "")
        snippet = item.get("snippet", "")
        lines.append(f"{idx}. {title} ({url})")
        if snippet:
            lines.append(f"   Snippet: {snippet}")
    return "\n".join(lines)