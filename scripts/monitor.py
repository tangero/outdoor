#!/usr/bin/env python3
"""
Automatický monitoring webů výrobců outdoorového vybavení.
Detekuje nové produkty a zapisuje je jako kandidáty na recenzi do
_automat/kandidati.json (třídí je scripts/trideni.py, píše scripts/recenze.py).

Použití:
    python scripts/monitor.py              # Normální běh
    python scripts/monitor.py --dry-run    # Simulace bez zápisu souborů
    python scripts/monitor.py --verbose    # Podrobný výstup
    python scripts/monitor.py --only Keen  # Jen vybraný zdroj (podle name)
"""

import argparse
import hashlib
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import automat_lib as lib  # noqa: E402
from automat_lib import log  # noqa: E402

# Volitelné importy - ošetříme, pokud nejsou nainstalovány
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    from slugify import slugify
except ImportError:
    # Fallback slugify
    def slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')


RATE_LIMIT_SECONDS = 1.5
SHOPIFY_MAX_PAGES = 8          # 8 × 250 produktů
SHOPIFY_DEFAULT_MAX_AGE = 45   # dní
EXA_DEFAULT_LOOKBACK = 30      # dní, když zdroj ještě nemá last_check
STATE_ITEMS_PER_SOURCE = 2000
QUEUE_MAX_ITEMS = 3000


def load_sources() -> list[dict[str, Any]]:
    """Načte konfiguraci zdrojů z YAML."""
    if not os.path.exists(lib.SOURCES_PATH):
        log(f"❌ Soubor {lib.SOURCES_PATH} neexistuje.")
        return []
    with open(lib.SOURCES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    return [item for item in data if isinstance(item, dict)]


def fetch_url(url: str) -> Optional[str]:
    """Stáhne obsah URL s respektováním rate limitingu."""
    if not HAS_REQUESTS:
        log("⚠️  Modul 'requests' není nainstalován. Přeskočeno.")
        return None
    try:
        headers = {"User-Agent": lib.USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=lib.REQUEST_TIMEOUT)
        resp.raise_for_status()
        time.sleep(RATE_LIMIT_SECONDS)
        return resp.text
    except Exception as e:
        log(f"⚠️  Chyba při stahování {url}: {e}")
        return None


# Klíčová slova pro odhad rubriky (jen nápověda pro třídění; rozhoduje scripts/trideni.py)
CATEGORY_KEYWORDS = {
    "batohy": ["backpack", "batoh", "rucksack", "daypack", "hiking pack", "trekking pack"],
    "boty": ["shoe", "boot", "footwear", "sandal", "trail running", "approach"],
    "karimatky": ["sleeping pad", "sleeping mat", "karimatka", "mattress", "self-inflating", "air pad"],
    "stany": ["tent", "shelter", "bivy", "tarp"],
    "powerbanky": ["power bank", "powerbank", "solar charger"],
}


def detect_category(*texts: str) -> str:
    """Odhadne rubriku podle klíčových slov."""
    text = " ".join(texts).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(kw), text) for kw in keywords):
            return category
    return ""


def item_hash(title: str, url: str) -> str:
    """Vytvoří hash pro identifikaci položky."""
    content = f"{title.strip()}|{url.strip()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def parse_rss(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """Parsuje RSS/Atom feed a vrací seznam položek."""
    if not HAS_FEEDPARSER:
        log("⚠️  Modul 'feedparser' není nainstalován. Přeskočeno.")
        return []
    url = source.get("rss_url", "")
    if not url:
        return []
    log(f"📡 RSS: {url}", verbose_only=True)
    try:
        parsed = feedparser.parse(url, agent=lib.USER_AGENT, request_headers={"User-Agent": lib.USER_AGENT})
        items = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            if not title or not link:
                continue
            thumbnail = ""
            if "media_thumbnail" in entry and entry.media_thumbnail:
                thumbnail = entry.media_thumbnail[0].get("url", "")
            elif "links" in entry:
                for l in entry.links:
                    if l.get("type", "").startswith("image/"):
                        thumbnail = l.get("href", "")
                        break
            items.append({
                "title": title.strip(),
                "url": link.strip(),
                "snippet": lib.strip_html(summary)[:1500],
                "thumbnail": thumbnail,
            })
        return items
    except Exception as e:
        log(f"⚠️  Chyba při parsování RSS {url}: {e}")
        return []


def parse_sitemap(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """Parsuje XML sitemapu; vrací URL odpovídající `url_pattern` se změnou po `since`."""
    url = source.get("sitemap_url", "")
    if not url:
        return []
    pattern = re.compile(source.get("url_pattern", "."))
    log(f"🗺️  Sitemap: {url}", verbose_only=True)
    content = fetch_url(url)
    if not content:
        return []
    try:
        root = ET.fromstring(content.encode("utf-8"))
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        items = []
        for elem in root.findall(".//ns:url", ns) or root.findall(".//url"):
            loc = elem.find("ns:loc", ns)
            if loc is None:
                loc = elem.find("loc")
            lastmod = elem.find("ns:lastmod", ns)
            if lastmod is None:
                lastmod = elem.find("lastmod")
            if loc is None or not loc.text or not pattern.search(loc.text):
                continue
            url_text = loc.text.strip()
            lastmod_text = lastmod.text.strip() if lastmod is not None and lastmod.text else ""
            if lastmod_text:
                try:
                    if datetime.fromisoformat(lastmod_text.replace("Z", "+00:00")) < since:
                        continue
                except ValueError:
                    pass
            title = os.path.basename(urlparse(url_text).path.rstrip("/")).replace("-", " ").replace("_", " ").title()
            items.append({"title": title, "url": url_text, "snippet": "", "thumbnail": "",
                          "published_at": lastmod_text})
        return items
    except Exception as e:
        log(f"⚠️  Chyba při parsování sitemap {url}: {e}")
        return []


def parse_shopify(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """Projde veřejný Shopify katalog a vrátí produkty publikované po `since`."""
    if not HAS_REQUESTS:
        log("⚠️  Modul 'requests' není nainstalován. Přeskočeno.")
        return []
    base = source.get("shop_url", "").rstrip("/")
    if not base:
        return []
    # Okno podle published_at nezávisí na posledním běhu; duplicity odfiltruje stav.
    max_age = int(source.get("max_age_days", SHOPIFY_DEFAULT_MAX_AGE))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)
    log(f"🛍️  Shopify: {base} (od {cutoff.date()})", verbose_only=True)

    items: dict[str, dict[str, Any]] = {}
    for page in range(1, SHOPIFY_MAX_PAGES + 1):
        try:
            resp = requests.get(f"{base}/products.json", params={"limit": 250, "page": page},
                                headers={"User-Agent": lib.USER_AGENT}, timeout=30)
            resp.raise_for_status()
            products = resp.json().get("products", [])
        except Exception as e:
            log(f"⚠️  Shopify {base} strana {page}: {e}")
            break
        if not products:
            break
        for p in products:
            handle = p.get("handle")
            published = p.get("published_at") or p.get("created_at") or ""
            if not handle or not published or handle in items:
                continue
            try:
                published_dt = datetime.fromisoformat(published)
            except ValueError:
                continue
            if published_dt < cutoff:
                continue
            variants = p.get("variants") or []
            grams = sorted({v.get("grams") for v in variants if v.get("grams")})
            prices = sorted({float(v["price"]) for v in variants if v.get("price")})
            images = p.get("images") or []
            items[handle] = {
                "title": (p.get("title") or "").strip(),
                "url": f"{base}/products/{handle}",
                "snippet": lib.strip_html(p.get("body_html") or "")[:1500],
                "thumbnail": images[0].get("src", "") if images else "",
                "published_at": published,
                "data": {
                    "vendor": p.get("vendor") or "",
                    "product_type": p.get("product_type") or "",
                    "tags": (p.get("tags") or [])[:30] if isinstance(p.get("tags"), list)
                            else str(p.get("tags") or "").split(", ")[:30],
                    "grams": grams[:5],
                    "price_range": [prices[0], prices[-1]] if prices else [],
                    "variants": len(variants),
                },
            }
        time.sleep(RATE_LIMIT_SECONDS)
    return list(items.values())


def parse_exa(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """Exa.ai vyhledávání na doménách výrobce, jen stránky publikované po `since`."""
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        log("⚠️  EXA_API_KEY není nastaveno. Přeskočeno.")
        return []
    if not HAS_REQUESTS:
        log("⚠️  Modul 'requests' není nainstalován. Přeskočeno.")
        return []

    query = source.get("exa_query", source.get("name", ""))
    payload: dict[str, Any] = {
        "query": query,
        "type": source.get("exa_type", "fast"),
        "numResults": source.get("exa_num_results", 5),
        "startPublishedDate": since.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "contents": {"text": {"maxCharacters": 1500}},
    }
    if source.get("exa_domains"):
        payload["includeDomains"] = source["exa_domains"]

    log(f"🤖 Exa.ai: {query} (od {since.date()})", verbose_only=True)
    try:
        resp = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log(f"⚠️  Chyba Exa.ai API: {e}")
        return []

    items = []
    for result in data.get("results", []):
        title = (result.get("title") or "").strip()
        url = (result.get("url") or "").strip()
        if not title or not url:
            continue
        items.append({
            "title": title,
            "url": url,
            "snippet": (result.get("text") or "").strip()[:1500],
            "thumbnail": result.get("image") or "",
            "published_at": result.get("publishedDate") or "",
        })
    return items


MD_LINK_RE = re.compile(r"\[([^\]]{3,200})\]\((https?://[^)\s]+)\)")


def parse_tinyfish(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """Stáhne stránku s novinkami přes TinyFish a vrátí produktové odkazy (`product_url_pattern`)."""
    list_url = source.get("list_url", "")
    if not list_url:
        return []
    pattern = re.compile(source.get("product_url_pattern", "/products?/"))
    log(f"🐟 TinyFish: {list_url}", verbose_only=True)
    page = lib.fetch_pages([list_url], max_chars=200000).get(list_url)
    if not page:
        return []
    items: dict[str, dict[str, Any]] = {}
    for text, url in MD_LINK_RE.findall(page["text"]):
        url = url.split("#")[0]
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text).strip()
        if not pattern.search(url) or url in items or len(text) < 3:
            continue
        items[url] = {"title": text, "url": url, "snippet": "", "thumbnail": ""}
    return list(items.values())


def parse_scrape(source: dict[str, Any], since: datetime) -> list[dict[str, Any]]:
    """Scrapuje HTML stránku pomocí CSS selektorů."""
    if not HAS_REQUESTS:
        log("⚠️  Modul 'requests' není nainstalován. Přeskočeno.")
        return []
    list_url = source.get("list_url", "")
    base_url = source.get("base_url", "")
    item_sel = source.get("item_selector", "")
    title_sel = source.get("title_selector", "")
    link_sel = source.get("link_selector", "")
    link_attr = source.get("link_attr", "href")
    desc_sel = source.get("description_selector", "")
    thumb_sel = source.get("thumbnail_selector", "")

    if not list_url or not item_sel:
        log(f"⚠️  Zdroj {source.get('name')} nemá list_url nebo item_selector.")
        return []

    log(f"🌐 Scrape: {list_url}", verbose_only=True)
    html = fetch_url(list_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = []
    for elem in soup.select(item_sel):
        title_node = elem.select_one(title_sel) if title_sel else elem
        title = title_node.get_text(strip=True) if title_node else ""

        link = ""
        if link_sel:
            link_node = elem.select_one(link_sel)
            if link_node:
                link = urljoin(base_url or list_url, link_node.get(link_attr, ""))

        snippet = ""
        if desc_sel:
            desc_node = elem.select_one(desc_sel)
            if desc_node:
                snippet = desc_node.get_text(strip=True)

        thumbnail = ""
        if thumb_sel:
            thumb_node = elem.select_one(thumb_sel)
            if thumb_node:
                if thumb_node.name == "img":
                    thumbnail = thumb_node.get("src", "") or thumb_node.get("data-src", "")
                else:
                    thumbnail = thumb_node.get_text(strip=True)
                thumbnail = urljoin(base_url or list_url, thumbnail)

        if title and link:
            items.append({"title": title, "url": link, "snippet": snippet, "thumbnail": thumbnail})
    return items


PARSERS = {
    "rss": parse_rss,
    "sitemap": parse_sitemap,
    "shopify": parse_shopify,
    "exa": parse_exa,
    "tinyfish": parse_tinyfish,
    "scrape": parse_scrape,
}


def title_key(brand: str, title: str) -> str:
    """Klíč pro sloučení barevných variant: značka + název bez části za „|“."""
    base = title.split("|")[0]
    return f"{brand}|" + re.sub(r"\W+", " ", base).strip().lower()


def make_candidate(item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    hint = detect_category(item["title"], item["url"], data.get("product_type", ""),
                           " ".join(data.get("tags", []))) or source.get("category", "")
    return {
        "id": item_hash(item["title"], item["url"]),
        "url": item["url"],
        "title": item["title"],
        "brand": source.get("name", ""),
        "strategy": source.get("strategy", ""),
        "category_hint": hint,
        "snippet": item.get("snippet", ""),
        "thumbnail": item.get("thumbnail", ""),
        "published_at": item.get("published_at", ""),
        "detected_at": lib.now_iso(),
        "data": data,
        "status": "novy",
    }


def process_source(source: dict[str, Any], state: dict[str, Any], queue: dict[str, Any],
                   init_only: bool = False) -> int:
    """Zpracuje jeden zdroj, nové položky přidá do fronty. Vrací počet nových."""
    source_id = slugify(source.get("name", "unknown"))
    strategy = source.get("strategy", "rss")
    parser = PARSERS.get(strategy)
    if not parser:
        log(f"⚠️  Neznámá strategie: {strategy}")
        return 0
    log(f"\n🔍 Zpracovávám: {source.get('name')} ({strategy})")

    source_state = state.setdefault("sources", {}).get(source_id, {"items": []})
    last_check = source_state.get("last_check")
    if last_check:
        since = datetime.fromisoformat(last_check) - timedelta(days=2)
    else:
        since = datetime.now(timezone.utc) - timedelta(days=EXA_DEFAULT_LOOKBACK)

    items = parser(source, since)
    log(f"   Nalezeno {len(items)} položek.", verbose_only=True)

    known_urls = {it["url"] for it in source_state.get("items", [])}
    queued_urls = {c["url"] for c in queue["items"]}
    queued_keys = {title_key(c["brand"], c["title"]) for c in queue["items"]}
    new_state_items = []
    new_count = 0
    for item in items:
        if item["url"] in known_urls:
            continue
        new_state_items.append({"url": item["url"], "hash": item_hash(item["title"], item["url"]),
                                "detected_at": lib.now_iso()})
        key = title_key(source.get("name", ""), item["title"])
        if init_only or item["url"] in queued_urls or key in queued_keys:
            continue
        log(f"   ✨ Novinka: {item['title'][:70]}")
        queue["items"].append(make_candidate(item, source))
        queued_urls.add(item["url"])
        queued_keys.add(key)
        new_count += 1

    all_items = new_state_items + source_state.get("items", [])
    state["sources"][source_id] = {
        "last_check": lib.now_iso(),
        "items": all_items[:STATE_ITEMS_PER_SOURCE],
    }
    return new_count


def main():
    parser = argparse.ArgumentParser(description="Monitor webů výrobců outdoor vybavení")
    parser.add_argument("--dry-run", action="store_true", help="Simulace bez zápisu")
    parser.add_argument("--verbose", action="store_true", help="Podrobný výstup")
    parser.add_argument("--init-state", action="store_true",
                        help="Pouze uloží současné položky do stavu, kandidáty negeneruje")
    parser.add_argument("--only", help="Zpracovat jen zdroj s tímto name")
    args = parser.parse_args()

    lib.VERBOSE = args.verbose

    log("🚀 Spouštím monitoring výrobců...")
    if args.dry_run:
        log("🏷️  DRY-RUN mód: nic se nezapíše.")

    sources = load_sources()
    if args.only:
        sources = [s for s in sources if s.get("name") == args.only]
    if not sources:
        log("❌ Nejsou nakonfigurovány žádné zdroje.")
        sys.exit(1)
    log(f"📋 Načteno {len(sources)} zdrojů.")

    state = lib.load_json(lib.STATE_PATH, {"version": 1, "last_run": None, "sources": {}})
    queue = lib.load_json(lib.QUEUE_PATH, {"version": 1, "items": []})

    total_new = 0
    for source in sources:
        total_new += process_source(source, state, queue, init_only=args.init_state)

    state["last_run"] = lib.now_iso()
    queue["items"] = queue["items"][-QUEUE_MAX_ITEMS:]

    if args.dry_run:
        for c in queue["items"][-total_new:] if total_new else []:
            log(f"[DRY-RUN] {c['brand']}: {c['title'][:60]} ({c['category_hint'] or '?'}) {c['url']}")
    else:
        lib.save_json(lib.STATE_PATH, state)
        lib.save_json(lib.QUEUE_PATH, queue)

    log("\n" + "=" * 50)
    log(f"🏁 Hotovo. Nových kandidátů: {total_new}.")
    log("=" * 50)


if __name__ == "__main__":
    main()
