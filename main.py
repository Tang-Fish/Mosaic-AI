import argparse
from datetime import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

import memory
import settings

DEFAULT_MODEL = "llama3.2:3b"
BOT_NAME = "Mosaic"


def is_local_ollama_url(base_url):
    try:
        parsed = urlparse(base_url or settings.DEFAULT_OLLAMA_URL)
        host = (parsed.hostname or "").lower()
        return host in ("", "localhost", "127.0.0.1", "0.0.0.0", "::1")
    except Exception:
        return True


def is_ollama_running(base_url, timeout=1.0):
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _find_windows_ollama_tray():
    candidates = []
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.append(Path(local_app) / "Programs" / "Ollama" / "ollama app.exe")
    prog_files = os.environ.get("PROGRAMFILES", "")
    if prog_files:
        candidates.append(Path(prog_files) / "Ollama" / "ollama app.exe")

    for name in ("ollama app.exe", "ollama app"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    ollama_cli = shutil.which("ollama")
    if ollama_cli:
        candidates.append(Path(ollama_cli).resolve().with_name("ollama app.exe"))

    for path in candidates:
        if path and path.is_file():
            return str(path)
    return None


def launch_ollama_tray(base_url=None):
    target_url = (base_url or settings.DEFAULT_OLLAMA_URL).rstrip("/")
    if not is_local_ollama_url(target_url):
        return False, "Remote Ollama URL configured."

    if is_ollama_running(target_url, timeout=0.8):
        return True, "Ollama is already running."

    try:
        if sys.platform == "win32":
            detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            tray_exe = _find_windows_ollama_tray()
            if tray_exe:
                subprocess.Popen(
                    [tray_exe],
                    creationflags=detached,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                )
                return True, "Launched Ollama in system tray."

            ollama_cli = shutil.which("ollama")
            if not ollama_cli and os.environ.get("LOCALAPPDATA"):
                fallback = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe"
                if fallback.is_file():
                    ollama_cli = str(fallback)
            if ollama_cli:
                no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.Popen(
                    [ollama_cli, "serve"],
                    creationflags=detached | no_win,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                )
                return True, "Started Ollama background server."
            return False, "Ollama executable was not found."

        if sys.platform == "darwin":
            app_paths = [
                Path("/Applications/Ollama.app"),
                Path.home() / "Applications" / "Ollama.app",
            ]
            if any(p.exists() for p in app_paths):
                subprocess.Popen(
                    ["open", "-g", "-a", "Ollama"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return True, "Launched Ollama in menu bar."

        ollama_cli = shutil.which("ollama")
        if ollama_cli:
            subprocess.Popen(
                [ollama_cli, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True, "Started Ollama background server."
        return False, "Ollama executable was not found."
    except Exception as e:
        return False, str(e)


def ensure_ollama_running(base_url, wait_seconds=12.0):
    if is_ollama_running(base_url, timeout=0.8):
        return True, "Connected"

    launched, msg = launch_ollama_tray(base_url)
    if not launched:
        return False, msg

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_ollama_running(base_url, timeout=0.8):
            return True, msg
        time.sleep(0.4)
    return False, "Timed out waiting for Ollama to start."


def _clean_html_text(fragment):
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_ddg_url(raw_href):
    href = html.unescape((raw_href or "").strip())
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return href


def _search_ollama_cloud(query, max_results, api_key, timeout=12):
    r = requests.post(
        "https://ollama.com/api/web_search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"query": query, "max_results": max_results},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    out = []
    for item in data.get("results", [])[:max_results]:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        snippet = (item.get("content") or item.get("snippet") or "").strip()
        if title and url:
            out.append({"title": title, "url": url, "snippet": snippet[:600]})
    return out


def _search_duckduckgo_html(query, max_results, timeout=12):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers=headers,
        timeout=timeout,
    )
    r.raise_for_status()
    page = r.text

    link_matches = re.findall(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )
    snippet_matches = re.findall(
        r'<(?:a|div)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>',
        page,
        flags=re.DOTALL | re.IGNORECASE,
    )

    results = []
    seen = set()
    for idx, (raw_href, raw_title) in enumerate(link_matches):
        url = _decode_ddg_url(raw_href)
        title = _clean_html_text(raw_title)
        snippet = _clean_html_text(snippet_matches[idx]) if idx < len(snippet_matches) else ""
        if not url.startswith(("http://", "https://")) or not title or url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "snippet": snippet[:600]})
        if len(results) >= max_results:
            break
    return results


def _search_wikipedia_fallback(query, max_results, timeout=10):
    headers = {"User-Agent": "MosaicLocalStudio/1.0"}
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": max_results,
        },
        headers=headers,
        timeout=timeout,
    )
    r.raise_for_status()
    items = r.json().get("query", {}).get("search", [])
    results = []
    for item in items[:max_results]:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        snippet = _clean_html_text(item.get("snippet", ""))
        results.append({"title": f"{title} - Wikipedia", "url": url, "snippet": snippet[:600]})
    return results


def search_web(query, max_results=5, api_key="", timeout=12):
    clean_q = re.sub(r"\s+", " ", (query or "")).strip()
    if not clean_q:
        return []
    if len(clean_q) > 280:
        clean_q = clean_q[:280].rsplit(" ", 1)[0]

    limit = max(1, min(10, int(max_results or 5)))
    key = (api_key or os.environ.get("OLLAMA_API_KEY") or "").strip()

    if key:
        try:
            cloud_hits = _search_ollama_cloud(clean_q, limit, key, timeout=timeout)
            if cloud_hits:
                return cloud_hits
        except Exception:
            pass

    try:
        ddg_hits = _search_duckduckgo_html(clean_q, limit, timeout=timeout)
        if ddg_hits:
            return ddg_hits
    except Exception:
        pass

    try:
        return _search_wikipedia_fallback(clean_q, limit, timeout=timeout)
    except Exception:
        return []


def format_search_context(query, results):
    today_str = datetime.now().strftime("%A, %B %d, %Y")
    if not results:
        return (
            f"\n\n[WEB SEARCH ATTEMPTED on {today_str} for: \"{query}\"]\n"
            "No live web search results could be retrieved (check your internet connection). "
            "Let the user know if you are unsure about current events or real-time facts."
        )

    lines = [
        f"\n\n[LIVE WEB SEARCH RESULTS — {today_str} — Query: \"{query}\"]",
        "Use the following up-to-date internet search results to answer the user's request accurately. "
        "Cite sources inline using [1], [2], etc. when referencing facts from these results:\n",
    ]
    for idx, item in enumerate(results, start=1):
        lines.append(f"[{idx}] {item['title']}")
        lines.append(f"URL: {item['url']}")
        if item.get("snippet"):
            lines.append(f"Snippet: {item['snippet']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def build_system_prompt(memories=None, base_prompt=None, query=""):
    saved = settings.load_settings()
    prompt = (base_prompt or saved.get("system_prompt") or "").strip()
    if not prompt:
        prompt = settings.DEFAULT_SYSTEM_PROMPT
    if not saved.get("memory_enabled", True):
        return prompt
    limit = int(saved.get("memory_limit", 20))
    mem_block = memory.build_memory_prompt(query=query, memories=memories, limit=limit)
    return f"{prompt}{mem_block}"


def build_ollama_options(saved=None):
    cfg = saved if saved is not None else settings.load_settings()
    opts = {
        "temperature": float(cfg.get("temperature", 0.7)),
        "top_p": float(cfg.get("top_p", 0.9)),
        "num_ctx": int(cfg.get("num_ctx", 4096)),
        "repeat_penalty": float(cfg.get("repeat_penalty", 1.1)),
    }
    num_predict = int(cfg.get("num_predict", -1))
    if num_predict > 0:
        opts["num_predict"] = num_predict
    return opts


def list_models(base_url):
    r = requests.get(f"{base_url}/api/tags", timeout=5)
    r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


def stream_chat(base_url, model, messages, options=None, stream=True, keep_alive=None, timeout=300):
    payload = {"model": model, "messages": messages, "stream": bool(stream)}
    if options:
        payload["options"] = options
    if keep_alive is not None and str(keep_alive) != "":
        ka_str = str(keep_alive).strip()
        if ka_str in ("-1", "0"):
            payload["keep_alive"] = int(ka_str)
        else:
            payload["keep_alive"] = ka_str

    with requests.post(f"{base_url}/api/chat", json=payload, stream=bool(stream), timeout=timeout) as r:
        if r.status_code != 200:
            raise RuntimeError(f"Ollama error {r.status_code}: {r.text.strip()}")
        if not stream:
            data = r.json()
            if "error" in data:
                raise RuntimeError(data["error"])
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            return
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(data["error"])
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break


def new_history():
    return [{"role": "system", "content": build_system_prompt()}]


def run_gui(base_url, model):
    from PySide6.QtWidgets import QApplication
    from ui import MosaicWindow

    app = QApplication([sys.argv[0]])
    window = MosaicWindow(
        base_url=base_url,
        model=model,
        build_system_prompt=build_system_prompt,
        stream_chat=stream_chat,
        list_models=list_models,
        ensure_ollama=ensure_ollama_running,
        search_web=search_web,
        format_search_context=format_search_context,
        bot_name=BOT_NAME,
    )
    window.show()
    sys.exit(app.exec())


def run_cli(base_url, model, web_enabled=False):
    saved_cfg = settings.load_settings()
    if saved_cfg.get("auto_start_ollama", True):
        ensure_ollama_running(base_url)

    try:
        installed = list_models(base_url)
    except requests.exceptions.RequestException:
        print(f"Couldn't reach Ollama at {base_url}.")
        print("Make sure it's installed and running (try: ollama serve).")
        sys.exit(1)

    if not any(m == model or m.startswith(model + ":") for m in installed):
        print(f"Model '{model}' isn't installed. Installed models:")
        for m in installed:
            print(f"  - {m}")
        print(f"\nPull it with: ollama pull {model}")
        sys.exit(1)

    history = new_history()
    web_on = bool(web_enabled or saved_cfg.get("web_search_always_on", False))
    print(f"=== {BOT_NAME} ===")
    print(f"Model: {model}   |   Web Search: {'ON' if web_on else 'OFF'} (/web to toggle, /clear, /quit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{BOT_NAME}: Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit"):
            print(f"{BOT_NAME}: Goodbye!")
            break
        if user_input.lower() == "/clear":
            history = new_history()
            print("(conversation cleared)\n")
            continue
        if user_input.lower() == "/web":
            web_on = not web_on
            print(f"(web search: {'ON' if web_on else 'OFF'})\n")
            continue

        saved_cfg = settings.load_settings()
        if saved_cfg.get("memory_enabled", True):
            saved = memory.extract_memories_from_text(user_input)
            for fact in saved:
                print(f"[Saved to memory: {fact}]")

        history[0]["content"] = build_system_prompt(query=user_input)
        history.append({"role": "user", "content": user_input})

        payload_messages = list(history)
        if web_on:
            print("[Searching the web...]", flush=True)
            results = search_web(
                user_input,
                max_results=int(saved_cfg.get("web_search_max_results", 5)),
                api_key=saved_cfg.get("ollama_api_key", ""),
            )
            payload_messages[-1] = {
                "role": "user",
                "content": user_input + format_search_context(user_input, results),
            }

        print(f"{BOT_NAME}: ", end="", flush=True)
        reply = ""
        try:
            opts = build_ollama_options(saved_cfg)
            for chunk in stream_chat(
                base_url,
                model,
                payload_messages,
                options=opts,
                stream=saved_cfg.get("stream_responses", True),
                keep_alive=saved_cfg.get("keep_alive", "5m"),
                timeout=int(saved_cfg.get("request_timeout", 300)),
            ):
                print(chunk, end="", flush=True)
                reply += chunk
            print("\n")
            history.append({"role": "assistant", "content": reply})
        except KeyboardInterrupt:
            print("\n(interrupted)\n")
            history.pop()
        except (requests.exceptions.RequestException, RuntimeError) as e:
            print(f"\n[Error] {e}\n")
            history.pop()


def main():
    parser = argparse.ArgumentParser(description=f"{BOT_NAME} - chat with Ollama")
    parser.add_argument("--model", default=None, help="Ollama model name")
    parser.add_argument("--url", default=None, help="Ollama server URL")
    parser.add_argument("--cli", action="store_true", help="use the terminal instead of the GUI")
    parser.add_argument("--web", action="store_true", help="enable web search in CLI mode")
    args = parser.parse_args()

    saved = settings.load_settings()
    model = args.model or saved.get("last_model") or DEFAULT_MODEL
    base_url = (args.url or saved.get("ollama_url") or settings.DEFAULT_OLLAMA_URL).rstrip("/")

    if args.cli:
        run_cli(base_url, model, web_enabled=args.web)
    else:
        run_gui(base_url, model)


if __name__ == "__main__":
    main()