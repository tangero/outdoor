"""
Sdílené pomůcky pro automat webu: cesty, JSON soubory, stahování stránek.

Stahování stránek (`fetch_pages`) zkouší v pořadí:
  1. TinyFish Fetch (zdarma do 1000 URL/den, renderuje JS) – pokud je TINYFISH_API_KEY,
  2. Exa /contents (0,001 USD za stránku) – pokud je EXA_API_KEY,
  3. obyčejný requests + BeautifulSoup.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import requests
except ImportError:  # monitor.py hlásí chybějící moduly sám
    requests = None

AUTOMAT_DIR = "_automat"
SOURCES_PATH = os.path.join(AUTOMAT_DIR, "zdroje.yml")
STATE_PATH = os.path.join(AUTOMAT_DIR, "stav.json")
QUEUE_PATH = os.path.join(AUTOMAT_DIR, "kandidati.json")

USER_AGENT = "Mozilla/5.0 (compatible; VybaveniDoPrirodyBot/1.0; +https://www.vybavenidoprirody.com)"
REQUEST_TIMEOUT = 20

TINYFISH_FETCH_URL = "https://api.fetch.tinyfish.ai"
TINYFISH_SEARCH_URL = "https://api.search.tinyfish.ai"
EXA_CONTENTS_URL = "https://api.exa.ai/contents"

VERBOSE = False


def log(msg: str, verbose_only: bool = False) -> None:
    if verbose_only and not VERBOSE:
        return
    print(msg, file=sys.stderr)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# Stahování stránek
# --------------------------------------------------------------------------- #

def _tinyfish_fetch(urls: list[str]) -> dict[str, dict[str, str]]:
    key = os.environ.get("TINYFISH_API_KEY")
    if not key or requests is None:
        return {}
    out: dict[str, dict[str, str]] = {}
    for i in range(0, len(urls), 10):  # max 10 URL na požadavek
        batch = urls[i:i + 10]
        try:
            resp = requests.post(
                TINYFISH_FETCH_URL,
                headers={"X-API-Key": key, "Content-Type": "application/json"},
                json={"urls": batch, "format": "markdown"},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log(f"⚠️  TinyFish Fetch selhal: {e}")
            continue
        for r in data.get("results", []):
            text = r.get("text") or ""
            if text:
                out[r.get("url", "")] = {
                    "url": r.get("final_url") or r.get("url", ""),
                    "title": r.get("title") or "",
                    "text": text,
                    "via": "tinyfish",
                }
        for err in data.get("errors", []):
            log(f"   TinyFish: {err.get('url')} → {err.get('error') or err}", verbose_only=True)
    return out


def exa_image(url: str) -> str:
    """Hlavní obrázek stránky podle Exa (pole `image`), nebo prázdný řetězec."""
    for page in _exa_contents([url]).values():
        return page.get("image", "")
    return ""


def _exa_contents(urls: list[str]) -> dict[str, dict[str, str]]:
    key = os.environ.get("EXA_API_KEY")
    if not key or requests is None or not urls:
        return {}
    try:
        resp = requests.post(
            EXA_CONTENTS_URL,
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={"urls": urls, "text": {"maxCharacters": 20000}},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log(f"⚠️  Exa contents selhal: {e}")
        return {}
    out = {}
    for r in data.get("results", []):
        if r.get("text"):
            out[r.get("url", "")] = {"url": r.get("url", ""), "title": r.get("title") or "",
                                     "text": r["text"], "via": "exa", "image": r.get("image") or ""}
    return out


def _plain_fetch(url: str) -> Optional[dict[str, str]]:
    if requests is None:
        return None
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        log(f"   requests: {url} → {e}", verbose_only=True)
        return None
    title_m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, flags=re.S | re.I)
    return {"url": resp.url, "title": strip_html(title_m.group(1)) if title_m else "",
            "text": strip_html(resp.text), "via": "requests"}


def fetch_pages(urls: list[str], max_chars: int = 20000) -> dict[str, dict[str, str]]:
    """Stáhne stránky a vrátí {původní_url: {url, title, text, via}}. Chybějící URL vynechá."""
    urls = [u for u in dict.fromkeys(urls) if u]
    result = _tinyfish_fetch(urls)
    missing = [u for u in urls if u not in result]
    if missing:
        result.update(_exa_contents(missing))
    for u in [u for u in urls if u not in result]:
        page = _plain_fetch(u)
        if page:
            result[u] = page
        time.sleep(1)
    for page in result.values():
        page["text"] = page["text"][:max_chars]
    return result


def tinyfish_search(query: str, after_date: Optional[str] = None) -> list[dict[str, str]]:
    """TinyFish Search (zdarma). Vrací [{title, url, snippet, site_name}]."""
    key = os.environ.get("TINYFISH_API_KEY")
    if not key or requests is None:
        return []
    params: dict[str, Any] = {"query": query}
    if after_date:
        params["after_date"] = after_date
    try:
        resp = requests.get(TINYFISH_SEARCH_URL, headers={"X-API-Key": key}, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log(f"⚠️  TinyFish Search selhal: {e}")
        return []
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", ""),
         "site_name": r.get("site_name", "")}
        for r in data.get("results", []) if r.get("url")
    ]


# --------------------------------------------------------------------------- #
# Claude API a evidence nákladů
# --------------------------------------------------------------------------- #

COSTS_PATH = os.path.join(AUTOMAT_DIR, "naklady.json")
WEEKLY_LIMIT_USD = float(os.environ.get("AUTOMAT_TYDENNI_LIMIT_USD", "2.0"))

MODEL_TRIAGE = "claude-haiku-5-5"
MODEL_WRITER = "claude-sonnet-5-5"

# USD za 1M tokenů: (vstup, výstup, čtení cache, zápis cache)
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
}


def iso_week(dt: Optional[datetime] = None) -> str:
    y, w, _ = (dt or datetime.now(timezone.utc)).isocalendar()
    return f"{y}-W{w:02d}"


def spent_this_week() -> float:
    return load_json(COSTS_PATH, {"tydny": {}})["tydny"].get(iso_week(), {}).get("usd", 0.0)


def record_cost(usd: float, label: str) -> None:
    data = load_json(COSTS_PATH, {"tydny": {}})
    week = data["tydny"].setdefault(iso_week(), {"usd": 0.0, "volani": 0, "polozky": {}})
    week["usd"] = round(week["usd"] + usd, 5)
    week["volani"] += 1
    week["polozky"][label] = round(week["polozky"].get(label, 0.0) + usd, 5)
    save_json(COSTS_PATH, data)


def usage_cost(model: str, usage: Any) -> float:
    p_in, p_out, p_cr, p_cw = PRICES[model]
    return (
        (getattr(usage, "input_tokens", 0) or 0) * p_in
        + (getattr(usage, "output_tokens", 0) or 0) * p_out
        + (getattr(usage, "cache_read_input_tokens", 0) or 0) * p_cr
        + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * p_cw
    ) / 1_000_000


class BudgetExceeded(Exception):
    pass


_client = None


def claude_json(model: str, system: str, user: str, schema: dict[str, Any], label: str,
                effort: str = "medium", max_tokens: int = 16000) -> dict[str, Any]:
    """Zavolá Claude se strukturovaným výstupem (JSON schéma) a zaeviduje náklady."""
    global _client
    import anthropic

    if spent_this_week() >= WEEKLY_LIMIT_USD:
        raise BudgetExceeded(f"Týdenní limit {WEEKLY_LIMIT_USD} USD vyčerpán ({spent_this_week():.2f} USD).")
    if _client is None:
        _client = anthropic.Anthropic()

    params: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if model in ("claude-sonnet-5-5", "claude-opus-5-5"):
        # Při odmítnutí bezpečnostním klasifikátorem API samo zkusí záložní model.
        with _client.beta.messages.stream(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
        ) as stream:
            response = stream.get_final_message()
    else:
        with _client.messages.stream(**params) as stream:
            response = stream.get_final_message()

    cost = usage_cost(model, response.usage)
    record_cost(cost, label)
    log(f"   💰 {label}: {cost:.4f} USD ({response.usage.input_tokens} in / "
        f"{response.usage.output_tokens} out)", verbose_only=True)

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Model odmítl odpovědět ({label}).")
    if response.stop_reason == "max_tokens":
        raise RuntimeError(f"Odpověď uříznuta na max_tokens ({label}).")
    text = "".join(b.text for b in response.content if b.type == "text")
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Stávající recenze
# --------------------------------------------------------------------------- #

RUBRIKY = ["batohy", "boty", "karimatky"]
POSTS_DIR = "_posts"
PRODUCTS_PATH = os.path.join("_data", "products.yml")


def load_reviews() -> list[dict[str, Any]]:
    """Načte recenze z _posts/<rubrika>/*.md: [{path, rubrika, fm, body}]."""
    import yaml

    reviews = []
    for rubrika in RUBRIKY:
        folder = os.path.join(POSTS_DIR, rubrika)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, flags=re.S)
            if not m:
                continue
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                continue
            reviews.append({"path": path, "rubrika": rubrika, "fm": fm, "body": m.group(2)})
    return reviews


def exa_search(query: str, num_results: int = 6, exclude_domains: Optional[list[str]] = None) -> list[dict[str, str]]:
    """Exa vyhledávání i s textem stránek. Vrací [{title, url, text}]."""
    key = os.environ.get("EXA_API_KEY")
    if not key or requests is None:
        return []
    payload: dict[str, Any] = {"query": query, "type": "fast", "numResults": num_results,
                               "contents": {"text": {"maxCharacters": 12000}}}
    if exclude_domains:
        payload["excludeDomains"] = exclude_domains
    try:
        resp = requests.post("https://api.exa.ai/search",
                             headers={"x-api-key": key, "Content-Type": "application/json"},
                             json=payload, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        log(f"⚠️  Exa search selhal: {e}")
        return []
    return [{"title": r.get("title") or "", "url": r.get("url") or "", "text": r.get("text") or ""}
            for r in resp.json().get("results", []) if r.get("url")]
