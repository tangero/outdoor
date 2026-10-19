#!/usr/bin/env python3
"""
Krátké novinky o nových produktech výrobců (kolekce _novinky/).

Bere čerstvé kandidáty z fronty (stav `vhodny`, ne převzaté staré drafty), kteří ještě
nemají novinku ani recenzi. Podkladem je jen stránka výrobce a data z katalogu, proto
jde o krátké představení novinky, ne o recenzi. Stav kandidáta se nemění (recenze může
přijít později), jen se zapíše `novinka` a `novinka_at`.

Použití:
    python scripts/novinky.py --pocet 3 [--dry-run] [--verbose]
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import automat_lib as lib  # noqa: E402
from automat_lib import log  # noqa: E402
from recenze import find_image, page_images, slugify, CLOUDINARY  # noqa: E402

NOVINKY_DIR = "_novinky"
WEEKLY_LIMIT_USD = float(os.environ.get("NOVINKY_TYDENNI_LIMIT_USD", "0.5"))
EST_COST = 0.03
PAGE_CHARS = 10000
MAX_AGE_DAYS = 60   # starší produkt už není novinka
MAX_ATTEMPTS = 3    # dočasné chyby (API, síť) se zkoušejí znovu v dalších bězích

SYSTEM = """Píšeš krátké novinky pro český web o outdoorovém vybavení (batohy, boty, karimatky).
Novinka představuje nový produkt výrobce čtenářům, kteří ho ještě neznají.

Pravidla:
- Vycházej výhradně z podkladů (stránka výrobce, data z katalogu). Nic si nedomýšlej:
  žádné vlastní zkušenosti, testy, dojmy z nošení ani srovnání s produkty, které v podkladech nejsou.
- Jde o představení, ne o recenzi: nehodnoť, nepiš klady a zápory, nedávej známku.
  Tvrzení výrobce uváděj jako tvrzení výrobce („podle výrobce“, „výrobce uvádí“).
- Nezmiňuj, jak text vznikl, ani podklady jako takové.
- Délka těla 120–220 slov, česky, věcně, bez reklamních superlativů a vykřičníků.
- Tělo: krátký úvodní odstavec (co to je a pro koho), pak odrážky „Hlavní parametry“
  (jen to, co v podkladech je: hmotnost, objem, materiály, membrána, podešev, varianty,
  cena) a jedna až dvě věty na závěr, čím se produkt liší nebo kam míří.
- Hmotnost uváděj tak, jak ji uvádí výrobce, včetně toho, k čemu se vztahuje (pár, jedna bota, velikost).
- Cenu uveď jen tehdy, když je v podkladech, s měnou.
- Titulek: „Model: krátký podtitulek“ v sentence case (velké jen první písmeno a vlastní jména).
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "model": {"type": "string", "description": "Značka a model bez barvy a pohlaví"},
        "perex": {"type": "string", "description": "Jedna věta do výpisu na titulce"},
        "telo": {"type": "string", "description": "Markdown, bez nadpisu článku"},
        "cena": {"type": "string", "description": "Cena s měnou z podkladů, jinak prázdné"},
        "dost_podkladu": {"type": "boolean",
                          "description": "False, pokud podklady nestačí ani na základní představení"},
    },
    "required": ["title", "model", "perex", "telo", "cena", "dost_podkladu"],
    "additionalProperties": False,
}


def spent_on_news() -> float:
    week = lib.load_json(lib.COSTS_PATH, {"tydny": {}})["tydny"].get(lib.iso_week(), {})
    return sum(v for k, v in week.get("polozky", {}).items() if k.startswith("novinka"))


def existing_news() -> set[str]:
    keys = set()
    if not os.path.isdir(NOVINKY_DIR):
        return keys
    for name in os.listdir(NOVINKY_DIR):
        with open(os.path.join(NOVINKY_DIR, name), encoding="utf-8") as f:
            m = re.search(r"^model:\s*['\"]?(.+?)['\"]?\s*$", f.read(), flags=re.M)
        if m:
            keys.add(lib.model_key(m.group(1)))
    return keys


def fresh(c: dict) -> bool:
    try:
        published = datetime.fromisoformat(c["published_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return False  # bez data nevíme, jestli jde o novinku
    return datetime.now(timezone.utc) - published <= timedelta(days=MAX_AGE_DAYS)


def pick(queue: dict) -> list[dict]:
    reviewed = {lib.model_key(str(r["fm"].get("model", ""))) for r in lib.load_reviews()}
    done = existing_news()
    ready = [c for c in queue["items"]
             if c.get("status") == "vhodny" and c.get("strategy") != "drafts-import"
             and not c.get("novinka") and c.get("novinka_pokusy", 0) < MAX_ATTEMPTS
             and fresh(c) and c.get("rubrika") in lib.RUBRIKY
             and lib.model_key(c.get("model", "")) not in reviewed | done]
    ready.sort(key=lambda c: (c.get("published_at") or "", c.get("priorita", 0)), reverse=True)
    # Střídat rubriky i značky: v každém kole jedna novinka z rubriky, značky se neopakují.
    out, by_rubric, by_brand = [], {}, {}
    for c in ready:
        brand = lib.brand_of(c.get("model", ""), c.get("brand", ""))
        by_rubric[c["rubrika"]] = by_rubric.get(c["rubrika"], 0) + 1
        by_brand[brand] = by_brand.get(brand, 0) + 1
        out.append((max(by_rubric[c["rubrika"]], by_brand[brand]), by_rubric[c["rubrika"]], c))
    out.sort(key=lambda x: x[:2])
    return [c for *_, c in out]


def describe(c: dict) -> str:
    data = c.get("data") or {}
    lines = [f"Značka: {c.get('brand')}", f"Název v katalogu: {c.get('title')}",
             f"Sjednocený model: {c.get('model')}", f"Rubrika: {c.get('rubrika')}", f"URL: {c['url']}"]
    if data.get("product_type"):
        lines.append(f"Typ: {data['product_type']}")
    if data.get("price_range"):
        lines.append(f"Cena v katalogu výrobce bez měny (uveď jen, když měnu potvrzuje stránka): "
                     f"{data['price_range']}")
    if data.get("grams"):
        lines.append(f"Hmotnost v katalogu (gramy, bez upřesnění): {data['grams']}")
    if data.get("tags"):
        lines.append("Tagy: " + ", ".join(data["tags"][:15]))
    return "\n".join(lines)


def validate(draft: dict) -> list[str]:
    errors = []
    words = len(draft["telo"].split())
    if not 90 <= words <= 320:
        errors.append(f"délka {words} slov")
    if re.search(r"\bAI\b|umělá inteligence|automaticky vygener|jazykový model|podklad", draft["telo"]):
        errors.append("zmiňuje vznik textu nebo podklady")
    if not draft["dost_podkladu"]:
        errors.append("málo podkladů")
    return errors


def build(c: dict, draft: dict, image: str) -> tuple[str, str]:
    model = draft["model"].strip() or c["model"]
    date = datetime.now(timezone.utc)
    path = os.path.join(NOVINKY_DIR, f"{date:%Y-%m-%d}-{slugify(model)}.md")
    fm = {"layout": "novinka", "title": draft["title"].strip(), "date": f"{date:%Y-%m-%d %H:%M:%S} +0000",
          "model": model, "znacka": lib.brand_of(model, c.get("brand", "")), "rubrika": c["rubrika"],
          "thumbnail": image, "perex": draft["perex"].strip(), "odkaz_vyrobce": c["url"]}
    if draft["cena"].strip():
        fm["cena"] = draft["cena"].strip()
    fm.update({"automat": True, "zdroje": [c["url"]]})
    body = draft["telo"].strip()
    parts = body.split("\n\n", 1)
    body = parts[0] + f"\n\n![{model}]({CLOUDINARY}{image})" + ("\n\n" + parts[1] if len(parts) > 1 else "")
    content = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n\n" + body + "\n"
    return path, content


def process(c: dict, dry_run: bool) -> str:
    log(f"\n📰 {c['model']} ({c['rubrika']}, {c['brand']})")
    page = lib.fetch_pages([c["url"]], PAGE_CHARS).get(c["url"], {})
    text = page.get("text", "")
    if len(text) < 300 and not c.get("data"):
        c["novinka"] = "malo_podkladu"
        return "stránka výrobce bez obsahu"
    image = find_image(c, page_images(text))
    if not image:
        c["novinka"] = "chybi_obrazek"
        return "chybí obrázek"
    user = (f"Katalogová data:\n{describe(c)}\n\n"
            f"Stránka výrobce:\n<stranka>\n{text[:PAGE_CHARS]}\n</stranka>\n\nNapiš novinku.")
    draft = lib.claude_json(lib.MODEL_WRITER, SYSTEM, user, SCHEMA, "novinka", effort="low", max_tokens=4000)
    errors = validate(draft)
    path, content = build(c, draft, image)
    if errors:
        c["novinka"] = "neplatna"
        c["novinka_problemy"] = errors
        if dry_run:
            save_dry(path, content, "NEPLATNE")
        return "; ".join(errors)
    if dry_run:
        return f"hotovo (nanečisto) → {save_dry(path, content, 'OK')}"
    os.makedirs(NOVINKY_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    c["novinka"] = path
    c["novinka_at"] = lib.now_iso()
    return f"hotovo → {path}"


def save_dry(path: str, content: str, label: str) -> str:
    out_dir = os.path.join(lib.AUTOMAT_DIR, "nanecisto")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"NOVINKA-{label}-{os.path.basename(path)}")
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    return out


def main():
    parser = argparse.ArgumentParser(description="Krátké novinky výrobců")
    parser.add_argument("--pocet", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    lib.VERBOSE = args.verbose

    queue = lib.load_json(lib.QUEUE_PATH, {"version": 1, "items": []})
    picked = pick(queue)
    log(f"📰 Kandidátů na novinku: {len(picked)}, na novinky tento týden {spent_on_news():.2f} USD.")
    results, written = [], 0
    for c in picked[: args.pocet * 3]:
        if written >= args.pocet:
            break
        if spent_on_news() + EST_COST > WEEKLY_LIMIT_USD:
            log(f"⛔ Týdenní limit na novinky {WEEKLY_LIMIT_USD} USD.")
            break
        before = c.get("novinka"), c.get("novinka_pokusy")
        try:
            msg = process(c, args.dry_run)
        except lib.BudgetExceeded as e:
            log(f"⛔ {e}")
            break
        except Exception as e:
            c["novinka_pokusy"] = c.get("novinka_pokusy", 0) + 1
            msg = f"chyba (pokus {c['novinka_pokusy']}/{MAX_ATTEMPTS}): {e}"
        if args.dry_run:
            c["novinka"], c["novinka_pokusy"] = before
        log(f"   → {msg}")
        written += msg.startswith("hotovo")
        results.append(f"- {c['model']}: {msg}")

    if not args.dry_run:
        lib.save_json(lib.QUEUE_PATH, queue)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and results:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Novinky\n" + "\n".join(results) + "\n")


if __name__ == "__main__":
    main()
