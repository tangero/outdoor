#!/usr/bin/env python3
"""
Automatické psaní recenzí z kandidátů ve stavu `vhodny` (_automat/kandidati.json).

Postup pro každý produkt:
  1. rešerše – stránka výrobce + nezávislé testy (TinyFish Search/Fetch, záložně Exa),
  2. text recenze ve stylu webu (Sonnet) se strukturovanými parametry,
  3. kontrola faktů proti zdrojům (Haiku), při závažném problému jedna oprava,
  4. zápis do _posts/<rubrika>/ a do _data/products.yml (automatické prolinkování).

Bez aspoň dvou nezávislých zdrojů se recenze nepíše (stav `malo_zdroju`, nový pokus za 14 dní).

Použití:
    python scripts/recenze.py --pocet 2 [--id <kandidat>] [--dry-run] [--verbose]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import automat_lib as lib  # noqa: E402
from automat_lib import log  # noqa: E402

try:
    from slugify import slugify
except ImportError:
    def slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        return re.sub(r"[-\s]+", "-", text).strip("-")

MIN_SOURCES = 2
FIX_ROUNDS = 2
MAX_SOURCES = 6
SOURCE_CHARS = 12000
RETRY_AFTER_DAYS = 14
BRAND_PAUSE_DAYS = 14
EST_COST_PER_REVIEW = 0.45  # USD, horní odhad: psaní ~0,11 + až 2 opravy po ~0,10 + kontroly

SKIP_DOMAINS = ("youtube.com", "youtu.be", "facebook.com", "instagram.com", "pinterest.",
                "tiktok.com", "x.com", "twitter.com", "amazon.", "ebay.", "aliexpress.")

CLOUDINARY = "https://res.cloudinary.com/dvwv5cne3/image/fetch/w_auto,h_450,c_fill,g_auto,f_auto,q_auto/"

PARAMS_BY_RUBRIKA = {
    "batohy": ["vaha", "objem", "material", "sex"],
    "boty": ["vaha", "tvar", "pohlavi", "material", "urceni"],
    "karimatky": ["vaha", "R-faktor", "tloustka", "typ"],
}
REQUIRED_BY_RUBRIKA = {
    "batohy": ["objem"],
    "boty": ["tvar"],
    "karimatky": ["R-faktor", "typ"],
}

SYSTEM_WRITER = """Jsi redaktor českého webu Vybavení do přírody (vybavenidoprirody.com) a píšeš recenze
outdoorového vybavení. Recenze je rešeršní: vychází výhradně z podkladů, které dostaneš
(stránka výrobce a nezávislé testy), a ze srovnání s produkty, které web už recenzoval.

Pravidla:
- Každé číslo a každé tvrzení o produktu musí mít oporu v podkladech. Co v podkladech není,
  nepiš; raději parametr vynech (null) nebo napiš, že ho výrobce neuvádí.
- Nepiš vymyšlené osobní zážitky („nosil jsem“, „na našem testu“). Zkušenosti testerů
  z podkladů můžeš převyprávět („testeři oceňují…“, „v dlouhodobém testu se ukázalo…“).
- Nezmiňuj, že text vznikl automaticky nebo z rešerše, a neodkazuj na „podklady“.
- Nezmiňuj interní věci webu: tabulku recenzovaných produktů, rubriku, hodnoticí
  rubriku ani kalibraci hodnocení. Čtenáři můžeš hodnocení v závěru krátce zdůvodnit
  vlastnostmi produktu, ale nepiš procenta, váhy kritérií ani srovnání se známkami jiných
  recenzí.
- Pohlaví (sex/pohlavi) urči podle toho, jaké verze výrobce nabízí (viz varianty
  v katalogu a podklady), ne podle jedné konkrétní varianty v URL.
- Piš česky, přirozeně, věcně a srozumitelně pro turistu, který vybírá vybavení. Bez
  marketingových superlativů, bez anglicismů, kde existuje český výraz. Jednotky metrické
  (g, l, cm, °C).
- Rozsah těla recenze 600–900 slov. Struktura jako na webu:
  úvodní 1–2 odstavce (pro koho produkt je a v čem vyniká), potom nadpisy úrovně ###:
  „Klíčové parametry a technologie“, „Výhody“, „Nevýhody“, „Srovnání s konkurencí“,
  „Pro koho je ideální?“, „Kdo by měl zvážit jinou variantu?“, „Závěrečné zhodnocení“.
  Obrázek do textu nevkládej.
- Ve srovnání s konkurencí používej přednostně produkty z tabulky už recenzovaných
  (stejný název modelu, aby se automaticky prolinkovaly). O srovnávaných produktech uváděj
  jen to, co stojí v tabulce (parametry, pro, proti), nic dalšího jim nepřisuzuj.
- Titulek ve tvaru „<Model>: <krátký výstižný podtitulek>“.
- pro / proti: jedna věta s výčtem 3–5 bodů oddělených čárkou.

Hodnocení 0–10 (krok 0,5) podle stejné rubriky pro celou rubriku webu:
- funkce a užitné vlastnosti pro hlavní účel (váha 40 %),
- hmotnost a konstrukce vůči konkurenci stejné třídy z tabulky (20 %),
- ohlasy nezávislých testů a uživatelů – odolnost, pohodlí, problémy (25 %),
- poměr cena/výkon (15 %).
Škála: 9+ výjimečný produkt bez zásadních slabin, 8 velmi dobrý, 7 dobrý s výhradami,
6 a méně průměr nebo zásadní problémy. Drž se škály stávajících hodnocení v tabulce.
"""

SYSTEM_CHECK = """Kontroluješ fakta v recenzi outdoorového vybavení proti podkladům.
Projdi každé konkrétní tvrzení v recenzi (čísla, materiály, technologie, vlastnosti, ohlasy
testů, srovnání) a ověř, že má oporu v podkladech nebo v tabulce už recenzovaných produktů.
Za problém považuj: tvrzení bez opory, číslo odlišné od zdroje, vymyšlenou osobní zkušenost
autora, zmínku o automatickém vzniku textu nebo o interních věcech webu (tabulka
recenzovaných produktů, hodnoticí rubrika, váhy kritérií) – to vše je „vysoka“.
Krátké zdůvodnění hodnocení vlastnostmi produktu („hodnocení snižuje hmotnost“) problém není. Obecné rady k výběru vybavení problém nejsou.
Závažnost „vysoka“ = chybné nebo vymyšlené faktum o produktu; „nizka“ = nepřesná formulace.
"""

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "problemy": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tvrzeni": {"type": "string"},
                    "problem": {"type": "string"},
                    "zavaznost": {"type": "string", "enum": ["vysoka", "nizka"]},
                },
                "required": ["tvrzeni", "problem", "zavaznost"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["problemy"],
    "additionalProperties": False,
}


def writer_schema(rubrika: str) -> dict:
    num_or_null = {"type": ["number", "null"]}
    params: dict = {
        "vaha": {**num_or_null, "description": "hmotnost v gramech (u bot jedna bota v nejběžnější velikosti)"},
    }
    if rubrika == "batohy":
        params["objem"] = {**num_or_null, "description": "objem v litrech; u více velikostí ta recenzovaná"}
        params["material"] = {"type": "string"}
        params["sex"] = {"type": "string", "enum": ["unisex", "muži", "ženy"]}
    elif rubrika == "boty":
        params["tvar"] = {"type": "string", "enum": ["nízké", "střední", "vysoké"]}
        params["pohlavi"] = {"type": "string", "enum": ["mužské", "ženské", "mužské, ženské", "unisex"]}
        params["material"] = {"type": "string"}
        params["urceni"] = {"type": "string", "description": "např. turistika, dlouhé výlety, technicky náročné trasy"}
    elif rubrika == "karimatky":
        params["R-faktor"] = {**num_or_null, "description": "R-hodnota podle ASTM F3340"}
        params["tloustka"] = {**num_or_null, "description": "tloušťka v cm"}
        params["typ"] = {"type": "string", "enum": ["nafukovací", "samonafukovací", "pěnová"]}
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "model": {"type": "string"},
            "parametry": {"type": "object", "properties": params,
                          "required": list(params), "additionalProperties": False},
            "pro": {"type": "string"},
            "proti": {"type": "string"},
            "hodnoceni": {"type": "number"},
            "zduvodneni_hodnoceni": {"type": "string"},
            "telo": {"type": "string", "description": "Markdown těla recenze bez front matter a bez obrázku"},
            "pouzite_zdroje": {"type": "array", "items": {"type": "string"},
                               "description": "URL podkladů, ze kterých recenze čerpá"},
        },
        "required": ["title", "model", "parametry", "pro", "proti", "hodnoceni",
                     "zduvodneni_hodnoceni", "telo", "pouzite_zdroje"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------- #
# Výběr a rešerše
# --------------------------------------------------------------------------- #

def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def model_tokens(model: str, brand: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", model.lower())
    brand_words = set(re.findall(r"[a-z0-9]+", brand.lower()))
    return [w for w in words if w not in brand_words and len(w) > 1] or words


def mentions_model(text: str, model: str, brand: str) -> bool:
    low = text.lower()
    tokens = model_tokens(model, brand)
    return sum(1 for t in tokens if t in low) >= max(1, len(tokens) - 1)


def variant_titles(queue: dict, c: dict) -> list[str]:
    """Názvy všech položek fronty se stejným modelem (pánské/dámské verze apod.)."""
    key = lib.model_key(c.get("model") or "")
    return sorted({x["title"] for x in queue["items"] if key and lib.model_key(x.get("model") or "") == key})


def recent_brands(days: int) -> set[str]:
    """Značky recenzí z posledních `days` dní (podle data v názvu souboru)."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return {lib.brand_of(str(r["fm"].get("model", "")), str(r["fm"].get("znacka", "")))
            for r in lib.load_reviews() if os.path.basename(r["path"])[:10] >= since}


def newest_by_rubric() -> dict[str, str]:
    """Datum nejnovějšího článku v každé rubrice (z názvu souboru), prázdná rubrika = ''."""
    out = {}
    for r in lib.RUBRIKY:
        folder = os.path.join(lib.POSTS_DIR, r)
        names = sorted(n for n in os.listdir(folder) if n.endswith(".md")) if os.path.isdir(folder) else []
        out[r] = names[-1][:10] if names else ""
    return out


def pick_candidates(queue: dict, count: int, only_id: str | None,
                    rubriky: list[str] | None = None) -> list[dict]:
    """Seřazení kandidáti: rubriky se střídají od té, kde je nejnovější článek nejstarší."""
    now = datetime.now(timezone.utc)
    ready = []
    for c in queue["items"]:
        if only_id:
            if c["id"] == only_id:
                return [c]
            continue
        if c.get("status") not in ("vhodny", "malo_zdroju", "chybi_obrazek"):
            continue
        last = c.get("pokus_at")  # neúspěšné pokusy (zdroje, obrázek) zkusit znovu až po čase
        if c.get("status") != "vhodny" and last and \
                datetime.fromisoformat(last) > now - timedelta(days=RETRY_AFTER_DAYS):
            continue
        if c.get("rubrika") not in (rubriky or lib.RUBRIKY):
            continue
        ready.append(c)
    # Značky, o kterých se psalo v posledních dnech, dostanou přednost až po ostatních.
    recent = recent_brands(BRAND_PAUSE_DAYS)
    ready.sort(key=lambda c: (lib.brand_of(c.get("model", ""), c.get("brand", "")) not in recent,
                              c.get("priorita", 0), c.get("published_at") or ""), reverse=True)
    # Střídat rubriky; začíná ta, která má nejstarší poslední článek (ať nezaostává).
    newest = newest_by_rubric()
    queues, rounds = {}, {}
    for c in ready:  # v rámci rubriky střídat značky (stabilně podle pořadí výše)
        brand = lib.brand_of(c.get("model", ""), c.get("brand", ""))
        rounds[brand] = rounds.get(brand, 0) + 1
        queues.setdefault(c["rubrika"], []).append((rounds[brand], c))
    queues = {r: [c for _, c in sorted(q, key=lambda x: x[0])] for r, q in queues.items()}
    order = sorted(queues, key=lambda r: newest.get(r, ""))
    picked = []
    while any(queues.values()):
        for r in order:
            if queues[r]:
                picked.append(queues[r].pop(0))
    return picked


MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")


def page_images(markdown: str) -> list[str]:
    """Obrázky produktu z markdownu stránky (bez log, ikon a SVG)."""
    out = []
    for url in MD_IMAGE_RE.findall(markdown):
        low = url.lower()
        if any(x in low for x in (".svg", "logo", "icon", "sprite", "badge", "flag", "payment")):
            continue
        if re.search(r"\.(jpe?g|png|webp)(\?|$)", low) or "/image" in low:
            out.append(url)
    return out


def research(c: dict, variants: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Vrátí (podklady [{url, title, text, druh: vyrobce|nezavisly}], obrázky ze stránky výrobce)."""
    model, brand = c["model"], c["brand"]
    maker = domain(c["url"])
    sources = []

    page = lib.fetch_pages([c["url"]], max_chars=SOURCE_CHARS).get(c["url"])
    maker_text = (page or {}).get("text", "")
    images = page_images(maker_text)
    extra = []
    data = c.get("data") or {}
    if data.get("grams"):
        extra.append(f"Hmotnost podle e-shopu výrobce (gramy, varianty): {data['grams']}")
    if data.get("price_range"):
        extra.append(f"Cena v e-shopu výrobce: {data['price_range']}")
    if variants:
        extra.append("Varianty produktu v katalogu výrobce: " + "; ".join(variants[:12]))
    if c.get("snippet") and c["snippet"] not in maker_text:
        extra.append("Popis z katalogu výrobce: " + c["snippet"])
    if maker_text or extra:
        sources.append({"url": c["url"], "title": (page or {}).get("title") or c["title"],
                        "text": "\n".join(extra + [maker_text])[:SOURCE_CHARS], "druh": "vyrobce"})

    urls: list[str] = []
    for q in (f"{model} review", f"{model} test"):
        for r in lib.tinyfish_search(q):
            u = r["url"]
            d = domain(u)
            if d == maker or any(s in d for s in SKIP_DOMAINS) or u in urls:
                continue
            urls.append(u)
    independent = []
    if urls:
        pages = lib.fetch_pages(urls[:MAX_SOURCES * 2], max_chars=SOURCE_CHARS)
        for u in urls:
            p = pages.get(u)
            if p and len(p["text"]) > 1500 and mentions_model(p["text"], model, brand):
                independent.append({"url": p["url"], "title": p["title"], "text": p["text"], "druh": "nezavisly"})
            if len(independent) >= MAX_SOURCES:
                break
    if len(independent) < MIN_SOURCES:
        log("   TinyFish nestačil, zkouším Exa.", verbose_only=True)
        known = {s["url"] for s in independent}
        for r in lib.exa_search(f"{model} review", num_results=8, exclude_domains=[maker]):
            if r["url"] in known or any(s in domain(r["url"]) for s in SKIP_DOMAINS):
                continue
            if len(r["text"]) > 1500 and mentions_model(r["text"], model, brand):
                independent.append({"url": r["url"], "title": r["title"], "text": r["text"], "druh": "nezavisly"})
            if len(independent) >= MAX_SOURCES:
                break
    log(f"   Podklady: výrobce {len(sources)}, nezávislé {len(independent)}")
    return sources + independent, images


def peers_table(reviews: list[dict], rubrika: str) -> str:
    cols = ["model", "hodnoceni"] + PARAMS_BY_RUBRIKA[rubrika] + ["pro", "proti"]
    lines = [" | ".join(cols)]
    for r in reviews:
        if r["rubrika"] != rubrika or not r["fm"].get("model"):
            continue
        lines.append(" | ".join(str(r["fm"].get(k, "")).replace("\n", " ") for k in cols))
    return "\n".join(lines)


def style_sample(reviews: list[dict], rubrika: str) -> str:
    same = [r for r in reviews if r["rubrika"] == rubrika]
    same.sort(key=lambda r: (float(str(r["fm"].get("hodnoceni", 0)).replace(",", ".") or 0), len(r["body"])),
              reverse=True)
    if not same:
        return ""
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)\s*", "", same[0]["body"]).strip()
    return body[:6000]


def format_sources(sources: list[dict]) -> str:
    out = []
    for i, s in enumerate(sources, 1):
        out.append(f"<podklad cislo=\"{i}\" druh=\"{s['druh']}\" url=\"{s['url']}\">\n"
                   f"# {s['title']}\n{s['text']}\n</podklad>")
    return "\n\n".join(out)


# --------------------------------------------------------------------------- #
# Psaní, kontrola, zápis
# --------------------------------------------------------------------------- #

def write_review(c: dict, sources: list[dict], reviews: list[dict]) -> dict:
    rubrika = c["rubrika"]
    system = SYSTEM_WRITER + "\n\nUkázka stylu existující recenze z rubriky:\n<ukazka>\n" \
        + style_sample(reviews, rubrika) + "\n</ukazka>"
    user = (f"Napiš recenzi produktu {c['model']} do rubriky {rubrika}.\n\n"
            f"Už recenzované produkty v rubrice (pro srovnání a kalibraci hodnocení):\n"
            f"<recenzovane>\n{peers_table(reviews, rubrika)}\n</recenzovane>\n\n"
            f"Podklady:\n{format_sources(sources)}")
    return lib.claude_json(lib.MODEL_WRITER, system, user, writer_schema(rubrika), "recenze-psani")


PUBLISHED_FIELDS = ("title", "model", "parametry", "pro", "proti", "hodnoceni", "telo")


def check_review(draft: dict, sources: list[dict], reviews: list[dict], rubrika: str) -> list[dict]:
    published = {k: draft[k] for k in PUBLISHED_FIELDS}
    user = (f"Recenze ke kontrole:\n<recenze>\n{json.dumps(published, ensure_ascii=False, indent=1)}\n</recenze>\n\n"
            f"Už recenzované produkty:\n<recenzovane>\n{peers_table(reviews, rubrika)}\n</recenzovane>\n\n"
            f"Podklady:\n{format_sources(sources)}")
    result = lib.claude_json(lib.MODEL_TRIAGE, SYSTEM_CHECK, user, CHECK_SCHEMA, "recenze-kontrola", effort="high")
    return result.get("problemy", [])


def fix_review(c: dict, draft: dict, problems: list[dict], sources: list[dict], reviews: list[dict]) -> dict:
    rubrika = c["rubrika"]
    user = (f"Oprav recenzi produktu {c['model']}. Kontrola faktů našla tyto problémy:\n"
            + "\n".join(f"- „{p['tvrzeni']}“: {p['problem']}" for p in problems)
            + "\n\nProblematická tvrzení oprav podle podkladů, nebo je odstraň. Zbytek textu zachovej.\n\n"
            f"<recenze>\n{json.dumps(draft, ensure_ascii=False, indent=1)}\n</recenze>\n\n"
            f"Už recenzované produkty:\n<recenzovane>\n{peers_table(reviews, rubrika)}\n</recenzovane>\n\n"
            f"Podklady:\n{format_sources(sources)}")
    system = SYSTEM_WRITER
    return lib.claude_json(lib.MODEL_WRITER, system, user, writer_schema(rubrika), "recenze-oprava")


def find_image(c: dict, page_imgs: list[str]) -> str:
    """První obrázek, který projde přes Cloudinary (náhled z monitoru → og:image → stránka → Exa)."""
    log(f"   Obrázky ze stránky výrobce: {len(page_imgs)}", verbose_only=True)
    tried = set()
    for get in (lambda: [c.get("thumbnail") or ""], lambda: shopify_images(c["url"]),
                lambda: [og_image(c["url"])], lambda: page_imgs[:3], lambda: [lib.exa_image(c["url"])]):
        for url in get():
            url = "https:" + url if url.startswith("//") else url
            if url and url not in tried and not re.search(r"logo|og[-_]?image|placeholder", url, re.I):
                tried.add(url)
                if lib.image_ok(url):
                    return url
    return ""


def shopify_images(page_url: str) -> list[str]:
    """Obrázky produktu ze Shopify (`/products/<handle>.json`) — jsou na cdn.shopify.com,
    kterou Cloudinary propouští, na rozdíl od domén jednotlivých výrobců."""
    m = re.match(r"(https?://[^/]+)/(?:[a-z]{2}(?:-[a-z]{2})?/)?products/([^/?#]+)", page_url)
    if not m or lib.requests is None:
        return []
    try:
        resp = lib.requests.get(f"{m.group(1)}/products/{m.group(2)}.json",
                                headers={"User-Agent": lib.USER_AGENT}, timeout=20)
        images = resp.json()["product"].get("images") or []
    except Exception:
        return []
    return [i["src"] for i in images[:3] if i.get("src")]


def og_image(page_url: str) -> str:
    if lib.requests is None:
        return ""
    try:
        html = lib.requests.get(page_url, headers={"User-Agent": lib.USER_AGENT}, timeout=20).text
    except Exception:
        return ""
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, flags=re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html, flags=re.I)
    return m.group(1) if m else ""


def build_post(c: dict, draft: dict, image: str) -> tuple[str, str, str]:
    """Vrátí (cesta, obsah, url_na_webu)."""
    rubrika = c["rubrika"]
    model = draft["model"].strip() or c["model"]
    slug = slugify(model)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(lib.POSTS_DIR, rubrika, f"{date}-{slug}.md")

    fm: dict = {"layout": "post", "title": draft["title"].strip(), "categories": rubrika,
                "feature-img": "", "thumbnail": image, "model": model,
                "znacka": lib.brand_of(model, c.get("brand", ""))}
    for k in PARAMS_BY_RUBRIKA[rubrika]:
        v = draft["parametry"].get(k)
        if v is None or v == "":
            continue
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        fm[k] = v
    hodnoceni = round(float(draft["hodnoceni"]) * 2) / 2
    fm.update({"pro": draft["pro"].strip(), "proti": draft["proti"].strip(),
               "hodnoceni": int(hodnoceni) if hodnoceni.is_integer() else hodnoceni,
               "automat": True, "zdroje": draft["pouzite_zdroje"]})

    body = draft["telo"].strip()
    paragraphs = body.split("\n\n", 1)
    image_md = f"![{model}]({CLOUDINARY}{image})"
    body = paragraphs[0] + "\n\n" + image_md + ("\n\n" + paragraphs[1] if len(paragraphs) > 1 else "")

    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n\n" + body + "\n"
    return path, content, f"/{rubrika}/{slug}/"


def append_product(model: str, url: str) -> None:
    with open(lib.PRODUCTS_PATH, "r", encoding="utf-8") as f:
        existing = f.read()
    if f'url: "{url}"' in existing:
        return
    entry = {"name": model, "url": url}
    m = re.search(r"\d", model)
    if m:
        variant = model[:m.start()].strip()
        if len(variant) > 3 and variant != model:
            entry["variants"] = [variant]
    block = yaml.safe_dump([entry], allow_unicode=True, sort_keys=False, default_style=None)
    block = block.replace(f"url: {url}", f'url: "{url}"')
    with open(lib.PRODUCTS_PATH, "a", encoding="utf-8") as f:
        if not existing.endswith("\n"):
            f.write("\n")
        f.write(block)


def validate(c: dict, draft: dict) -> list[str]:
    errors = []
    for k in REQUIRED_BY_RUBRIKA[c["rubrika"]]:
        if draft["parametry"].get(k) in (None, ""):
            errors.append(f"chybí parametr {k}")
    words = len(draft["telo"].split())
    if words < 400:
        errors.append(f"krátký text ({words} slov)")
    if not 0 <= float(draft["hodnoceni"]) <= 10:
        errors.append("hodnocení mimo 0–10")
    # „podklad“ nekontrolujeme – u bot běžně znamená povrch terénu.
    if re.search(r"\bAI\b|umělá inteligence|automaticky vygener|jazykový model", draft["telo"]):
        errors.append("text zmiňuje AI")
    return errors


def process(c: dict, reviews: list[dict], dry_run: bool, variants: list[str] | None = None) -> str:
    log(f"\n✍️  {c['model']} ({c['rubrika']}, {c['brand']})")
    c["pokus_at"] = lib.now_iso()
    existing = {lib.model_key(str(r["fm"].get("model", ""))): r["path"] for r in reviews}
    if lib.model_key(c["model"]) in existing:
        c["status"] = "duplicitni"
        c["duplicita"] = existing[lib.model_key(c["model"])]
        return f"už recenzováno ({c['duplicita']})"
    sources, page_imgs = research(c, variants)
    if len([s for s in sources if s["druh"] == "nezavisly"]) < MIN_SOURCES:
        c["status"] = "malo_zdroju"
        return "málo nezávislých zdrojů"
    image = find_image(c, page_imgs)
    if not image:
        c["status"] = "chybi_obrazek"
        return "chybí obrázek"

    draft = write_review(c, sources, reviews)
    for round_no in range(FIX_ROUNDS + 1):
        problems = [p for p in check_review(draft, sources, reviews, c["rubrika"]) if p["zavaznost"] == "vysoka"]
        if not problems:
            break
        log(f"   Kontrola: {len(problems)} závažných problémů.")
        for p in problems:
            log(f"     - {p['tvrzeni'][:100]}: {p['problem'][:160]}")
        if round_no < FIX_ROUNDS:
            draft = fix_review(c, draft, problems, sources, reviews)
    if problems:
        c["status"] = "neproslo_kontrolou"
        c["problemy"] = problems[:5]
        if dry_run:
            save_dry_run(c, draft, image, "NEPROSLO")
        return f"neprošlo kontrolou faktů ({len(problems)} problémů)"

    errors = validate(c, draft)
    if errors:
        c["status"] = "neplatna_data"
        c["problemy"] = errors
        if dry_run:
            save_dry_run(c, draft, image, "NEPLATNE")
        return "; ".join(errors)

    if dry_run:
        return f"hotovo (nanečisto) → {save_dry_run(c, draft, image, 'OK')}"
    path, content, url = build_post(c, draft, image)
    append_product(draft["model"].strip() or c["model"], url)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    c["status"] = "napsano"
    c["soubor"] = path
    return f"hotovo → {path}"


def save_dry_run(c: dict, draft: dict, image: str, label: str) -> str:
    """V režimu nanečisto uloží recenzi (i neúspěšnou) do _automat/nanecisto/ k posouzení."""
    _, content, _ = build_post(c, draft, image)
    if c.get("problemy"):
        content += "\n<!-- Problémy z kontroly:\n" + "\n".join(
            f"- {p['tvrzeni']}: {p['problem']}" if isinstance(p, dict) else f"- {p}" for p in c["problemy"]) + "\n-->\n"
    out_dir = os.environ.get("AUTOMAT_DRY_RUN_DIR", os.path.join(lib.AUTOMAT_DIR, "nanecisto"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{label}-{slugify(c['model'])}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def main():
    parser = argparse.ArgumentParser(description="Automatické recenze")
    parser.add_argument("--pocet", type=int, default=2, help="Kolik recenzí napsat")
    parser.add_argument("--id", help="Napsat recenzi konkrétního kandidáta")
    parser.add_argument("--rubrika", help="Jen tyto rubriky, oddělené čárkou (např. batohy,karimatky)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Recenze uloží do _automat/nanecisto/, frontu ani products.yml nemění")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    lib.VERBOSE = args.verbose

    queue = lib.load_json(lib.QUEUE_PATH, {"version": 1, "items": []})
    reviews = lib.load_reviews()
    rubriky = [r.strip() for r in args.rubrika.split(",")] if args.rubrika else None
    picked = pick_candidates(queue, args.pocet, args.id, rubriky)
    log(f"📝 Připraveno {len(picked)} kandidátů, tento týden utraceno {lib.spent_this_week():.2f} USD.")

    results = []
    written = 0
    attempts = 0
    for c in picked:
        if written >= args.pocet or attempts >= args.pocet * 4:
            break
        attempts += 1
        if lib.spent_this_week() + EST_COST_PER_REVIEW > lib.weekly_limit():
            log(f"⛔ Další recenze by překročila týdenní limit {lib.weekly_limit()} USD.")
            break
        status_before = c.get("status")
        try:
            msg = process(c, reviews, args.dry_run, variant_titles(queue, c))
        except lib.BudgetExceeded as e:
            log(f"⛔ {e}")
            break
        except Exception as e:
            c["status"] = "chyba"
            c["problemy"] = [str(e)[:300]]
            msg = f"chyba: {e}"
        if args.dry_run and c.get("status") != "chyba":
            c["status"] = status_before
        log(f"   → {msg}")
        if msg.startswith("hotovo"):
            written += 1
        results.append(f"- {c['model']} ({c['rubrika']}): {msg}")

    if not args.dry_run:
        lib.save_json(lib.QUEUE_PATH, queue)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and results:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Recenze\n" + "\n".join(results) + f"\n\nUtraceno tento týden: {lib.spent_this_week():.2f} USD\n")
    log(f"\n💰 Tento týden utraceno {lib.spent_this_week():.2f} USD.")


if __name__ == "__main__":
    main()
