#!/usr/bin/env python3
"""
Třídění kandidátů z _automat/kandidati.json (model Haiku).

Pro každého nového kandidáta rozhodne, jestli jde o konkrétní produkt do některé
z rubrik webu, sjednotí název modelu (bez barvy a pohlaví) a označí duplicity
proti už napsaným recenzím i proti jiným kandidátům.

Stavy kandidáta: novy → vhodny | zamitnuty | duplicitni | (recenze.py) napsano, malo_zdroju

Použití:
    python scripts/trideni.py [--limit 200] [--dry-run] [--verbose]
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import automat_lib as lib  # noqa: E402
from automat_lib import log  # noqa: E402

BATCH_SIZE = 25

SYSTEM = """Třídíš kandidáty na recenze pro český web o outdoorovém vybavení.
Web má rubriky:
- batohy: turistické, trekové, běžecké a horolezecké batohy (ne tašky přes rameno, ledvinky, cestovní kufry, obaly).
- boty: turistické, trekové, trailové běžecké a horské boty a sandály do terénu (ne městské tenisky, lyžařské a skialpové boty, lezečky).
- karimatky: nafukovací, samonafukovací a pěnové karimatky (ne spacáky, polštáře, deky).

Pro každého kandidáta urči:
- relevantni: true jen pokud jde o jeden konkrétní produkt, který patří do některé rubriky.
  False pro homepage, kategorie, tiskové zprávy, články, výsledky firmy, oblečení, doplňky,
  lezecké vybavení, lyžařské boty a vše mimo rubriky.
- rubrika: batohy | boty | karimatky | zadna.
- model: jednotný název produktu ve tvaru „Značka Model“ bez barvy, velikosti a pohlaví
  (např. „Scarpa Ribelle Run 2 GTX“, „Osprey Exos 58“). Dámské a pánské verze téhož modelu
  mají stejný model. Když produkt nemá jasný název, nech prázdné a relevantni=false.
- priorita 1–5: 5 = nový nebo významný model, o který budou mít čtenáři zájem,
  1 = okrajový produkt. Městské a lifestyle produkty max. 2.
- duvod: krátce česky, proč.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "kandidati": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "relevantni": {"type": "boolean"},
                    "rubrika": {"type": "string", "enum": ["batohy", "boty", "karimatky", "zadna"]},
                    "model": {"type": "string"},
                    "priorita": {"type": "integer"},
                    "duvod": {"type": "string"},
                },
                "required": ["id", "relevantni", "rubrika", "model", "priorita", "duvod"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["kandidati"],
    "additionalProperties": False,
}


def norm(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", model.lower()).strip()


def describe(c: dict) -> str:
    data = c.get("data") or {}
    parts = [f"id: {c['id']}", f"značka: {c['brand']}", f"název: {c['title']}", f"url: {c['url']}"]
    if data.get("product_type"):
        parts.append(f"typ: {data['product_type']}")
    if data.get("tags"):
        parts.append("tagy: " + ", ".join(data["tags"][:12]))
    if c.get("snippet"):
        parts.append("popis: " + c["snippet"][:400].replace("\n", " "))
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Třídění kandidátů na recenze")
    parser.add_argument("--limit", type=int, default=200, help="Max. kandidátů na jeden běh")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    lib.VERBOSE = args.verbose

    queue = lib.load_json(lib.QUEUE_PATH, {"version": 1, "items": []})
    pending = [c for c in queue["items"] if c.get("status") == "novy"][: args.limit]
    log(f"🧹 Ke třídění: {len(pending)} kandidátů.")
    if not pending:
        return

    existing = {norm(str(r["fm"].get("model", ""))): r["path"] for r in lib.load_reviews() if r["fm"].get("model")}
    claimed = {norm(c["model"]) for c in queue["items"]
               if c.get("model") and c.get("status") in ("vhodny", "napsano")}
    by_id = {c["id"]: c for c in pending}

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        user = "Roztřiď tyto kandidáty:\n\n" + "\n\n".join(describe(c) for c in batch)
        try:
            result = lib.claude_json(lib.MODEL_TRIAGE, SYSTEM, user, SCHEMA, "trideni", effort="low")
        except lib.BudgetExceeded as e:
            log(f"⛔ {e}")
            break
        for r in result.get("kandidati", []):
            c = by_id.get(r["id"])
            if not c:
                continue
            model = r["model"].strip()
            c.update({"model": model, "rubrika": r["rubrika"], "priorita": r["priorita"],
                      "duvod": r["duvod"], "trideno_at": lib.now_iso()})
            key = norm(model)
            if not r["relevantni"] or r["rubrika"] == "zadna" or not model:
                c["status"] = "zamitnuty"
            elif key in existing:
                c["status"] = "duplicitni"
                c["duplicita"] = existing[key]
            elif key in claimed:
                c["status"] = "duplicitni"
            else:
                c["status"] = "vhodny"
                claimed.add(key)
            log(f"   {c['status']:<10} {model or c['title'][:50]} ({r['rubrika']}, p{r['priorita']})",
                verbose_only=True)

    from collections import Counter
    log("📊 " + ", ".join(f"{k}: {v}" for k, v in Counter(c.get("status") for c in pending).items()))
    if not args.dry_run:
        lib.save_json(lib.QUEUE_PATH, queue)


if __name__ == "__main__":
    main()
