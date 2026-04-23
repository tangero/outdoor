#!/usr/bin/env python3
"""
Automatický monitoring webů výrobců outdoorového vybavení.
Detekuje nové produkty a blogové příspěvky, generuje Jekyll drafty.

Použití:
    python scripts/monitor.py              # Normální běh
    python scripts/monitor.py --dry-run    # Simulace bez zápisu souborů
    python scripts/monitor.py --verbose    # Podrobný výstup
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import yaml

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


# Konfigurace
USER_AGENT = "VybaveniDoPrirodyBot/1.0 (+https://github.com/patrickzandl/outdoor)"
REQUEST_TIMEOUT = 15
RATE_LIMIT_SECONDS = 1.5
SOURCES_PATH = os.path.join("_data", "monitor_sources.yml")
STATE_PATH = os.path.join("_data", "monitor_state.json")
DRAFTS_DIR = "_drafts"


def log(msg: str, verbose_only: bool = False):
    """Vytiskne zprávu na stderr."""
    if verbose_only and not VERBOSE:
        return
    print(msg, file=sys.stderr)


def load_sources() -> list[dict[str, Any]]:
    """Načte konfiguraci zdrojů z YAML."""
    if not os.path.exists(SOURCES_PATH):
        log(f"❌ Soubor {SOURCES_PATH} neexistuje.")
        return []
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    # Filtrovat komentáře a None hodnoty
    return [item for item in data if isinstance(item, dict)]


def load_state() -> dict[str, Any]:
    """Načte persistovaný stav."""
    if not os.path.exists(STATE_PATH):
        return {"version": 1, "last_run": None, "sources": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, Any], dry_run: bool = False):
    """Uloží persistovaný stav."""
    if dry_run:
        log("[DRY-RUN] Stav by se uložil do " + STATE_PATH)
        return
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_url(url: str) -> Optional[str]:
    """Stáhne obsah URL s respektováním rate limitingu."""
    if not HAS_REQUESTS:
        log("⚠️  Modul 'requests' není nainstalován. Přeskočeno.")
        return None
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        time.sleep(RATE_LIMIT_SECONDS)
        return resp.text
    except Exception as e:
        log(f"⚠️  Chyba při stahování {url}: {e}")
        return None


def item_hash(title: str, url: str, snippet: str = "") -> str:
    """Vytvoří hash pro identifikaci položky."""
    content = f"{title.strip()}|{url.strip()}|{snippet.strip()[:200]}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def parse_rss(source: dict[str, Any]) -> list[dict[str, str]]:
    """Parsuje RSS/Atom feed a vrací seznam položek."""
    if not HAS_FEEDPARSER:
        log("⚠️  Modul 'feedparser' není nainstalován. Přeskočeno.")
        return []
    url = source.get("rss_url", "")
    if not url:
        return []
    log(f"📡 RSS: {url}", verbose_only=True)
    try:
        parsed = feedparser.parse(url, agent=USER_AGENT, request_headers={"User-Agent": USER_AGENT})
        items = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            if not title or not link:
                continue
            # Zkusíme najít obrázek
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
                "snippet": summary.strip(),
                "thumbnail": thumbnail,
            })
        return items
    except Exception as e:
        log(f"⚠️  Chyba při parsování RSS {url}: {e}")
        return []


def parse_sitemap(source: dict[str, Any]) -> list[dict[str, str]]:
    """Parsuje XML sitemapu a vrací seznam URL s recentními změnami."""
    url = source.get("sitemap_url", "")
    if not url:
        return []
    log(f"🗺️  Sitemap: {url}", verbose_only=True)
    content = fetch_url(url)
    if not content:
        return []
    try:
        root = ET.fromstring(content.encode("utf-8"))
        # XML namespace handling
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        items = []
        for elem in root.findall(".//ns:url", ns) or root.findall(".//url"):
            loc = elem.find("ns:loc", ns) or elem.find("loc")
            lastmod = elem.find("ns:lastmod", ns) or elem.find("lastmod")
            if loc is not None and loc.text:
                url_text = loc.text.strip()
                lastmod_text = lastmod.text.strip() if lastmod is not None and lastmod.text else ""
                # Pro sitemap detekujeme nové URL nebo recentní lastmod
                # Název odvodíme z URL
                title = os.path.basename(urlparse(url_text).path).replace("-", " ").replace("_", " ").title()
                items.append({
                    "title": title,
                    "url": url_text,
                    "snippet": f"Last modified: {lastmod_text}" if lastmod_text else "",
                    "thumbnail": "",
                    "lastmod": lastmod_text,
                })
        return items
    except Exception as e:
        log(f"⚠️  Chyba při parsování sitemap {url}: {e}")
        return []


def parse_exa(source: dict[str, Any]) -> list[dict[str, str]]:
    """Použije Exa.ai API pro vyhledávání a extrakci obsahu."""
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        log("⚠️  EXA_API_KEY není nastaveno. Přeskočeno.")
        return []
    if not HAS_REQUESTS:
        log("⚠️  Modul 'requests' není nainstalován. Přeskočeno.")
        return []

    query = source.get("exa_query", source.get("name", ""))
    domains = source.get("exa_domains", [])
    num_results = source.get("exa_num_results", 10)
    after = source.get("exa_after")
    search_type = source.get("exa_type", "auto")

    log(f"🤖 Exa.ai: {query}", verbose_only=True)

    payload: dict[str, Any] = {
        "query": query,
        "type": search_type,
        "numResults": num_results,
        "contents": {
            "text": {"maxCharacters": 2000}
        }
    }
    if domains:
        payload["includeDomains"] = domains
    if after:
        payload["startPublishedDate"] = after

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(
            "https://api.exa.ai/search",
            headers=headers,
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
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = ""
        contents = result.get("contents", {})
        if isinstance(contents, dict):
            snippet = contents.get("text", "")[:800]
        if not title or not url:
            continue
        items.append({
            "title": title.strip(),
            "url": url.strip(),
            "snippet": snippet.strip(),
            "thumbnail": "",
        })
    return items


def parse_scrape(source: dict[str, Any]) -> list[dict[str, str]]:
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
        # Titulek
        title_node = elem.select_one(title_sel) if title_sel else elem
        title = title_node.get_text(strip=True) if title_node else ""

        # Odkaz
        link = ""
        if link_sel:
            link_node = elem.select_one(link_sel)
            if link_node:
                raw_link = link_node.get(link_attr, "")
                link = urljoin(base_url or list_url, raw_link)

        # Popis
        snippet = ""
        if desc_sel:
            desc_node = elem.select_one(desc_sel)
            if desc_node:
                snippet = desc_node.get_text(strip=True)

        # Thumbnail
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
            items.append({
                "title": title,
                "url": link,
                "snippet": snippet,
                "thumbnail": thumbnail,
            })
    return items


def generate_draft(item: dict[str, str], source: dict[str, Any], dry_run: bool = False) -> Optional[str]:
    """Vygeneruje Jekyll draft a vrací cestu k souboru."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(item["title"])[:50]
    filename = f"{today}-{slug}.md"
    filepath = os.path.join(DRAFTS_DIR, filename)

    category = source.get("category", "ostatni")
    source_name = source.get("name", "Neznámý zdroj")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Front matter
    fm = {
        "layout": "post",
        "title": f"Novinka: {item['title']}",
        "categories": category,
        "source_url": item["url"],
        "source_name": source_name,
        "scraped_at": now_iso,
        "featured": False,
    }
    if item.get("thumbnail"):
        fm["thumbnail"] = item["thumbnail"]

    # Sestavení obsahu
    lines = ["---"]
    lines.append(yaml.dump(fm, allow_unicode=True, sort_keys=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(f"Toto je automaticky vygenerovaný návrh článku z webu **{source_name}**.")
    lines.append("")
    lines.append("## Detaily novinky")
    lines.append("")
    lines.append(f"**Zdroj:** [{item['title']}]({item['url']})")
    lines.append(f"**Detekováno:** {now_iso}")
    lines.append("")
    if item.get("snippet"):
        lines.append("## Shrnutí")
        lines.append("")
        # Odstranit HTML tagy ze snippetu
        snippet_clean = re.sub(r'<[^>]+>', '', item["snippet"])
        lines.append(snippet_clean)
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Vygenerováno automaticky. Před publikací zkontrolujte fakta, doplňte parametry (model, objem, vaha, ...) a přepište obsah do finální podoby.*")
    lines.append("")

    content = "\n".join(lines)

    if dry_run:
        log(f"[DRY-RUN] Draft by se vytvořil: {filepath}")
        log(content[:300] + "\n...")
        return filepath

    os.makedirs(DRAFTS_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def process_source(source: dict[str, Any], state: dict[str, Any], dry_run: bool = False) -> list[str]:
    """Zpracuje jeden zdroj a vrátí seznam cest k novým draftům."""
    source_id = slugify(source.get("name", "unknown"))
    strategy = source.get("strategy", "rss")
    log(f"\n🔍 Zpracovávám: {source.get('name')} ({strategy})")

    # Načtení položek podle strategie
    if strategy == "rss":
        items = parse_rss(source)
    elif strategy == "sitemap":
        items = parse_sitemap(source)
    elif strategy == "exa":
        items = parse_exa(source)
    elif strategy == "scrape":
        items = parse_scrape(source)
    else:
        log(f"⚠️  Neznámá strategie: {strategy}")
        return []

    log(f"   Nalezeno {len(items)} položek.", verbose_only=True)

    # Načtení historie tohoto zdroje
    source_state = state.get("sources", {}).get(source_id, {"items": []})
    known_hashes = {it["hash"] for it in source_state.get("items", [])}
    known_urls = {it["url"] for it in source_state.get("items", [])}

    new_drafts = []
    new_items_state = []

    for item in items:
        h = item_hash(item["title"], item["url"], item.get("snippet", ""))
        # Novinka = neznámý hash nebo neznámá URL
        if h in known_hashes or item["url"] in known_urls:
            new_items_state.append({"url": item["url"], "hash": h, "detected_at": source_state.get("items", [])[0].get("detected_at") if source_state.get("items") else datetime.now(timezone.utc).isoformat()})
            continue

        log(f"   ✨ Novinka: {item['title'][:60]}...")
        draft_path = generate_draft(item, source, dry_run=dry_run)
        if draft_path:
            new_drafts.append(draft_path)
        new_items_state.append({
            "url": item["url"],
            "hash": h,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })

    # Aktualizace stavu - sloučit staré a nové, omezit na posledních 500 položek
    existing_items = {it["url"]: it for it in source_state.get("items", [])}
    for it in new_items_state:
        existing_items[it["url"]] = it
    final_items = sorted(existing_items.values(), key=lambda x: x.get("detected_at", ""), reverse=True)[:500]

    state.setdefault("sources", {})[source_id] = {
        "last_check": datetime.now(timezone.utc).isoformat(),
        "items": final_items,
    }

    return new_drafts


def main():
    parser = argparse.ArgumentParser(description="Monitor webů výrobců outdoor vybavení")
    parser.add_argument("--dry-run", action="store_true", help="Simulace bez zápisu")
    parser.add_argument("--verbose", action="store_true", help="Podrobný výstup")
    parser.add_argument("--init-state", action="store_true", help="Pouze inicializuje stav bez generování draftů (vhodné při prvním spuštění)")
    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    log("🚀 Spouštím monitoring výrobců...")
    if args.dry_run:
        log("🏷️  DRY-RUN mód: nic se nezapíše.")
    if args.init_state:
        log("🗃️  INIT-STATE mód: ukládám stav, ale negeneruji drafty.")

    sources = load_sources()
    if not sources:
        log("❌ Nejsou nakonfigurovány žádné zdroje.")
        sys.exit(1)

    log(f"📋 Načteno {len(sources)} zdrojů.")

    state = load_state()
    all_new_drafts = []

    for source in sources:
        if args.init_state:
            # Inicializace stavu bez generování draftů
            source_id = slugify(source.get("name", "unknown"))
            strategy = source.get("strategy", "rss")
            log(f"\n🔍 Inicializuji: {source.get('name')} ({strategy})")
            if strategy == "rss":
                items = parse_rss(source)
            elif strategy == "sitemap":
                items = parse_sitemap(source)
            elif strategy == "exa":
                items = parse_exa(source)
            elif strategy == "scrape":
                items = parse_scrape(source)
            else:
                log(f"⚠️  Neznámá strategie: {strategy}")
                continue
            log(f"   Nalezeno {len(items)} položek (uloženo do stavu).")
            source_state = state.setdefault("sources", {}).get(source_id, {"items": []})
            existing = {it["url"] for it in source_state.get("items", [])}
            new_items = []
            for item in items:
                h = item_hash(item["title"], item["url"], item.get("snippet", ""))
                if item["url"] not in existing:
                    new_items.append({"url": item["url"], "hash": h, "detected_at": datetime.now(timezone.utc).isoformat()})
            # Sloučit a uložit
            all_items = source_state.get("items", []) + new_items
            state["sources"][source_id] = {
                "last_check": datetime.now(timezone.utc).isoformat(),
                "items": all_items[:500],
            }
        else:
            drafts = process_source(source, state, dry_run=args.dry_run)
            all_new_drafts.extend(drafts)

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state, dry_run=args.dry_run)

    log("\n" + "=" * 50)
    log(f"🏁 Hotovo. Detekováno {len(all_new_drafts)} novinek.")
    if all_new_drafts:
        for d in all_new_drafts:
            log(f"   📝 {d}")
    else:
        log("   Žádné nové položky.")
    log("=" * 50)


if __name__ == "__main__":
    main()
