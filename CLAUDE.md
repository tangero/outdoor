# CLAUDE.md

Web **„Vybavení do přírody“** (www.vybavenidoprirody.com): český recenzní web
o outdoorovém vybavení (batohy, boty, karimatky; připravené rubriky stany a
powerbanky). Statický Jekyll na šabloně Mediumish. Recenze píše **automat**
(sleduje nabídku výrobců, píše přes Claude API, otevírá PR). `README.md` je
původní README šablony, o projektu nic neříká.

## Příkazy projektu

```
bundle install                          # Ruby gemy (Jekyll 4.4, Ruby 3.x)
bundle exec jekyll serve                # dev server http://localhost:4000
bundle exec jekyll build                # build do _site/ (trvá ~2 min, viz Pozor na)
ruby scripts/generate_products.rb       # přegeneruje _data/generated_products.yml z front matter `model`

pip install -r scripts/requirements.txt # Python závislosti automatu (lokálně .venv/)
python scripts/monitor.py --dry-run --verbose [--only Keen]   # monitoring nanečisto
python scripts/trideni.py --verbose     # třídění kandidátů (Haiku), potřebuje ANTHROPIC_API_KEY
python scripts/recenze.py --pocet 1 --dry-run --verbose       # recenze do _automat/nanecisto/
python scripts/novinky.py --pocet 3 --dry-run --verbose       # novinky do _automat/nanecisto/
gh workflow run monitor.yml --ref <větev> -f rezim=test -f pocet=1   # celý automat v Actions nanečisto
                                        # (pocet=0 jen novinky; -f limit=N kolik třídit, -f novinky=N,
                                        #  -f rubrika=batohy,karimatky jen vybrané rubriky; i pro rezim=recenze)
```

- Klíče (`ANTHROPIC_API_KEY`, `EXA_API_KEY`, `TINYFISH_API_KEY`, `CLOUDINARY_URL`) jsou jen v GitHub
  secrets, lokálně nejsou. Lokálně jde bez klíčů pustit monitor (Shopify zdroje);
  zbytek testuj režimem `test` v Actions (výstup v artefaktu `automat-test`).

## Architektura a stack

- **Hosting: Cloudflare Pages**, projekt `outdoor` (`outdoor-ekv.pages.dev`,
  doména www.vybavenidoprirody.com, DNS na Cloudflare). Každý push do `main`
  se sám sestaví a nasadí (Jekyll 4 včetně `_plugins/`). Ověření: `npx wrangler pages
  deployment list --project-name outdoor`.
- **Jekyll 4 + kramdown (GFM)**, šablona Mediumish (Bootstrap, jQuery, lunr.js).
  Pluginy: paginate, sitemap, feed, seo-tag. AdSense zapnutý v `_config.yml`.
- **Obsah:** recenze v `_posts/<rubrika>/RRRR-MM-DD-slug.md`, obecné články přímo
  v `_posts/`. Permalink `/:categories/:title/` → např. `/batohy/osprey-exos-48-osprey-exos-58/`.
  Krátké **novinky** výrobců jsou samostatná kolekce `_novinky/` (`/novinky/<slug>/`,
  layout `novinka`) — nejsou v `site.posts`, přehledech, stránkování ani RSS.
- **Hlavička a patička (`_layouts/default.html`, styly `hl-*` a `pt-*` na konci `main.scss`):** rubriky
  z `_data/rubriky.yml` (jen neprázdné), `/srovnani/` (`_pages/srovnani.html`), hledání lunr (`_includes/search-lunr.html`).
  Patička: autoři, kontakt `patrick@vibecoding.cz`, odkazy na naše další weby (natvrdo v layoutu).
  Pozor: `assets/js/mediumish.js` skrývá při posunu všechny `<nav>`, v patičce proto `<nav>` nepoužívej.
- **Titulka (`index.html`, jen na `/`):** nejnovější recenze, pruh novinek, blok pro každou
  rubriku s články (všechny letošní, aspoň 4; nad čtyři v řadě `hp-rubrika__vice`), ručně vybrané (`featured: true`), pruh značek; pod tím stránkovaný
  výpis všech článků. Styly `hp-*` na konci `assets/css/main.scss`, karta `_includes/hp-karta.html`,
  české datum `_includes/datum.html`, pruh rubrik `_includes/rubriky-pruh.html` (prázdné rubriky skrývá).
- **Článek (`_layouts/post.html`, styly `cl-*` na konci `main.scss`):** recenze (má `model`) dostane
  rozhodovací kartu (fotka, známka, verdikt, parametry, pro/proti), řadu odkazů na oddíly z nadpisů,
  boční žebříček kategorie, blok „Naše akce“ a tři alternativy. Data karty počítá plugin
  `_plugins/srovnani.rb` do `page.srovnani`: kategorie (batohy podle objemu, karimatky podle `typ`,
  boty podle `tvar`), pořadí podle hmotnosti (u bot podle hodnocení, váhy bot nejsou jednotné),
  zdůvodnění známky z řádku `**Hodnocení:** X/10` (automat ho doplní z `zduvodneni_hodnoceni`). Pod textem hodnocení reakcemi (`mg-comments`
  z vibecoding.cz, vypnutí `rating: false`, slug je `vybavenidoprirody-<cesta>` a nesmí se měnit,
  ruční přepis `rating_slug`) a rozbalovací seznam `zdroje`. „Naše akce“ plní `assets/js/promo.js`
  z `vibecoding.cz/api/active-promotion` (správa v admin/promo); bez odpovědi zůstane skrytý.
  Obě API vyžadují doménu webu v CORS allowlistu vibecoding.cz. Google AdSense je vypnutý.
- **Značky:** `_data/znacky.yml` (název, slug, prefixy modelu); pole `znacka` ve front matter
  recenzí i novinek; stránka `/znacky/`. Automat značku doplňuje sám (`lib.brand_of`).
- **Stránka rubriky (`_layouts/category.liquid`, styly `kat-*`, skript `assets/js/katalog.js`):** katalog recenzí
  (řádky s `model`) s filtry a řazením, obecné články rubriky, dole průvodce z `_categories/<rubrika>.md`.
  Data počítá `_plugins/katalog.rb` do `page.katalog` (hranice pásem tam, shodné se `srovnani.rb` a přehledy),
  kapitoly průvodce do `page.kapitoly`. Rubrika dostane katalog, jen když má v `_data/rubriky.yml` klíč `filtry`
  (dále `rada`, `sloupce`, `razeni`; prázdné rubriky `prazdna` a `vyzva`). Bez JS se ukáže celá tabulka.
  Pozor: `mediumish.js` nastavuje odsazení obsahu podle výšky prvního `<header>` na stránce, v obsahu ho nepoužívej.
- **Rubriky:** kolekce `_categories/*.md` + `_data/rubriky.yml`. Srovnávací tabulky
  `batohy/prehled.md`, `boty/prehled.md`, `karimatky/prehled.md` (Liquid nad front matter).
- **Vlastní pluginy (`_plugins/`):** `product_linker.rb` po renderu převede zmínky
  produktů z `_data/products.yml` (`name`, pak `variants`) na odkazy na recenze;
  `fix_categories.rb` převádí `categories` ze stringu na pole.
- **Obrázky:** `thumbnail` je buď obrázek nahraný do Cloudinary (`.../image/upload/.../outdoor/<slug>`,
  automat s `CLOUDINARY_URL` v secrets), nebo externí URL servírovaná přes Cloudinary fetch
  `res.cloudinary.com/dvwv5cne3/image/fetch/...`. Šablony skládají URL přes `_includes/cld.html`
  (v Pythonu `lib.cld`). Fetch propouští jen domény z allowlistu (Settings → Security → Allowed
  fetch domains, spravuje majitel); bez nahrání automat obrázek ověří (`lib.image_ok`).
- **Automat (`scripts/`, stav v `_automat/`, workflow `.github/workflows/monitor.yml`):**
  1. `monitor.py` (denně 9:00 UTC) projde `_automat/zdroje.yml` — strategie `shopify`
     (veřejné `/products.json`, nové = `published_at` za 45 dní), `exa` (jen od
     posledního běhu), `tinyfish`, `rss`, `sitemap`, `scrape` — a nové položky přidá do
     fronty `_automat/kandidati.json` (barevné varianty se slučují podle názvu).
  2. `trideni.py` (Haiku) určí rubriku, jednotný `model` a prioritu; stavy
     `novy → vhodny | zamitnuty | duplicitni` (duplicita proti `_posts` i frontě).
  3. `recenze.py` (út a pá 6:00 UTC, 2 kusy) vezme `vhodny` podle priority a střídá
     rubriky (první je ta s nejstarším posledním článkem, v rubrice se střídají značky;
     `--rubrika` omezí výběr): rešerše (stránka výrobce + nezávislé testy a srovnání přes
     TinyFish Search/Fetch, záložně Exa) → text s redakčním verdiktem (Sonnet, strukturovaný
     výstup) → kontrola faktů a redakční kvality (Haiku, až 2 kola oprav) →
     `_posts/<rubrika>/` + záznam do `_data/products.yml`. Workflow commitne články i stav
     fronty rovnou do `main` (majitel je prochází a opravuje dodatečně). Značky z posledních
     14 dní dostávají přednost až po ostatních.
  4. `novinky.py` (denně po třídění, 3 kusy, ~0,012 USD/ks, vlastní strop 0,5 USD/týden)
     napíše krátké představení čerstvých kandidátů (ne starých draftů) podle stránky výrobce,
     katalogu a existujících recenzí; závěrečný „Náš pohled“ doporučí použití a případnou
     alternativu, ale bez známky → `_novinky/`, commit do `main`. Stav kandidáta nemění
     (recenze může přijít později), zapíše jen `novinka`.
  - Společné funkce (stahování stránek TinyFish → Exa → requests, volání Claude,
    náklady) v `scripts/automat_lib.py`. Náklady po ISO týdnech v `_automat/naklady.json`,
    strop `AUTOMAT_TYDENNI_LIMIT_USD` (výchozí 2 USD); mimořádný limit pro konkrétní
    týden (jen se souhlasem majitele) v `_automat/rozpocet.yml`.

## Konvence

- **Front matter recenze:** `layout: post`, `title` („Model: podtitulek“), `categories`
  (rubrika), `model` (slouží linkeru i přehledům), `thumbnail`, `pro`, `proti`,
  `hodnoceni` (0–10, krok 0,5) + parametry podle rubriky:
  - batohy: `vaha` (g), `objem` (l, číslo — přehled podle něj třídí), `material`, `sex`
  - boty: `vaha`, `tvar` (`nízké`/`střední`/`vysoké`, přehled podle něj seskupuje), `pohlavi`, `material`, `urceni`
  - karimatky: `vaha`, `R-faktor`, `tloustka` (cm), `typ` (`nafukovací`/`samonafukovací`/`pěnová`)
  Automatické recenze mají navíc `automat: true` a `zdroje` (seznam URL, na webu se nezobrazuje).
- **Recenze jsou rešeršní a názorové:** fakta jen z podkladů, o alternativách jen z tabulky
  už recenzovaných a nezávislých zdrojů, žádné vymyšlené osobní zážitky. Redakční hodnocení
  („za nás“, „podle nás“) je naopak povinné: konkrétní použití, kompromis, volba mezi produktem
  a alternativou a jednoznačný verdikt v závěru. Stejnou cenovou kategorii lze tvrdit jen s oběma
  ověřenými cenami ve srovnatelné podobě; nepřepočítáváme měny vlastním kurzem.
- **Novinky nemají známku, ale mají „Náš pohled“:** krátké doporučení použití a hlavního
  kompromisu z dostupných parametrů; alternativa jen z existujících recenzí, bez domnělých cen
  a vlastních zkušeností. Povinný blok hlídá validace v `novinky.py`.
- **AI se na webu zatím nezmiňuje** (rozhodnutí majitele, označení se dořeší s právníkem) —
  validace v `recenze.py` a `novinky.py` to hlídá.
- **Ruční recenze → aktualizuj linker:** `ruby scripts/generate_products.rb` a nové
  položky přenes do `_data/products.yml` (plugin čte jen ten). Automat zapisuje sám.
- **Nový sledovaný výrobce:** záznam do `_automat/zdroje.yml`. Nejdřív zkus, jestli
  má `/products.json` (Shopify, zdarma; výprodeje a „seconds“ vyřaď přes `exclude_title`); jinak `exa` s doménou výrobce, nebo `tinyfish`
  se stránkou novinek a `product_url_pattern`. Ověř `--dry-run --only <name>`.
- **Commity:** krátce česky; automatické commity bota mají prefix `Auto:`, PR s
  recenzemi jsou z větví `recenze/<datum>`.

## Pozor na

- **Bot commituje do `main` denně** (`_automat/`). Lokální klon bývá pozadu —
  začínej `git pull --rebase`. `_automat/stav.json` a `kandidati.json` ručně
  neupravuj, pokud nevíš proč; stav zdroje se resetuje `--init-state`.
- **Jekyll publikuje všechno bez podtržítka**, co není v `exclude` v `_config.yml`.
  Interní soubory (skripty, data automatu) patří do `_automat/` nebo do `exclude`.
- **`workflow_dispatch` jde jen pro workflow, který už je na `main`** — proto je
  celý automat v jednom `monitor.yml` (dá se pustit `--ref <větev>`).
- **PR z Actions:** vyžaduje v Settings → Actions → General zapnuté „Allow GitHub
  Actions to create and approve pull requests". Bez toho workflow jen pushne větev
  `recenze/…` a vypíše varování.
- **Build je pomalý kvůli `product_linker.rb`** (prochází celé HTML každé stránky);
  bez něj ~5 s. Na ladění šablon stačí build bez linkeru: dočasný config
  `plugins_dir: <složka jen s fix_categories.rb>` a `-d` mimo `_site`.
- **`site.categories` v Liquidu nefunguje** — překrývá ho kolekce `_categories`.
  Články rubriky ber jako `site.posts | where_exp: "p", "p.categories contains rubrika.name"`.
- **GitHub Pages** (`tangero.github.io/outdoor`, legacy build) není produkce a jeho
  build padá na `boty/prehled.md` (Jekyll 3.10). Produkce je Cloudflare Pages.
- **Shopify katalogy obsahují i oblečení, lezecké a lyžařské vybavení** — filtruje
  až `trideni.py`. U Sea to Summit funguje jen `https://seatosummit.com` bez `www.`
- **Zbytky šablony, ne funkční součást projektu:** workflowy `publish-build.yml`,
  `gem-build.yml`, `docker-build.yml`, `build.yml`, `gem-github-page.yml`,
  `.github/hooks/`, `.gitpod.yml`, `site/`, autoři `sal` v `_config.yml`,
  `assets/img/portfolio/`, `_posts/soubory z designu.zip`, soubor `Terminal`.
  Mazat jen na pokyn.

## Pracovní dohoda

**Než začneš.** U netriviálního úkolu (3+ kroků nebo zásah do buildu/deploye)
napiš stručný plán a počkej na souhlas. Předpoklady vyslov nahlas.

**Minimální zásah.** Měň jen to, co souvisí se zadáním, drž styl okolního kódu
a šablon. Zbytky šablony neuklízej bez pokynu.

**Ověř, než řekneš hotovo.** Po změně šablon, pluginů nebo přehledů spusť
`bundle exec jekyll build` a zkontroluj HTML v `_site/`. Změny automatu ověř
během `rezim=test` v Actions a přečti výstupní recenze, ne jen exit kód.

**Souhlas si vyžádej u:** mazání obsahu, force push, změn deploye a nastavení
repozitáře, zvýšení rozpočtu automatu.

Commit/push dělej jen na výslovný pokyn.
