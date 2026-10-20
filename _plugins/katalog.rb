# Katalog recenzí na stránce rubriky (/batohy/, /boty/, /karimatky/): řádky tabulky,
# filtry s počty a obecné články rubriky. Nastavení rubrik je v _data/rubriky.yml,
# hranice pásem tady. Objem a typy jsou stejné jako v srovnani.rb, R-faktor jako
# v karimatky/prehled.md. Výsledek je v page.katalog dokumentu z kolekce _categories.
require_relative "srovnani"

module Jekyll
  class Katalog < Srovnani
    priority :lowest

    NAZVY_FILTRU = {
      "objem" => "Objem", "hmotnost" => "Hmotnost", "strih" => "Střih", "znacka" => "Značka",
      "tvar" => "Výška boty", "typ" => "Typ", "izolace" => "Izolace (R-faktor)",
    }.freeze

    NAZVY_SLOUPCU = {
      "objem" => "Objem", "vaha" => "Hmotnost", "strih" => "Střih", "tvar" => "Výška",
      "urceni" => "Určení", "typ" => "Typ", "r" => "R-faktor",
    }.freeze

    NAZVY_RAZENI = {
      "datum" => "od nejnovějších", "vaha" => "od nejlehčích", "objem" => "podle objemu",
      "r" => "od nejteplejších", "hodnoceni" => "podle známky",
    }.freeze

    # Pásma filtrů: [id, popisek, podmínka]
    PASMA = {
      "objem" => [["do-35", "do 35 l", ->(v) { v <= 35 }], ["36-64", "36–64 l", ->(v) { v < 65 }],
                  ["od-65", "od 65 l", ->(_) { true }]],
      "hmotnost-batohy" => [["do-1", "do 1 kg", ->(v) { v < 1000 }], ["1-1.5", "1–1,5 kg", ->(v) { v < 1500 }],
                            ["1.5-2", "1,5–2 kg", ->(v) { v < 2000 }], ["nad-2", "nad 2 kg", ->(_) { true }]],
      "hmotnost-karimatky" => [["do-500", "do 500 g", ->(v) { v < 500 }], ["500-800", "500–800 g", ->(v) { v <= 800 }],
                               ["nad-800", "nad 800 g", ->(_) { true }]],
      "izolace" => [["leto", "léto, do 3", ->(v) { v <= 3 }], ["3-5", "tři sezóny, 3–5", ->(v) { v <= 5 }],
                    ["zima", "zima, nad 5", ->(_) { true }]],
    }.freeze

    VYCTY = {
      "strih" => [%w[unisex Unisex], %w[damsky Dámský], %w[pansky Pánský]],
      "tvar" => [%w[nizke Nízké], ["stredni", "Středně vysoké"], %w[vysoke Vysoké]],
      "typ" => [%w[nafukovaci Nafukovací], %w[samonafukovaci Samonafukovací], %w[penova Pěnová]],
    }.freeze

    def generate(site)
      nastaveni = Array(site.data["rubriky"]).to_h { |r| [r["name"], r] }
      site.collections["categories"]&.docs&.each do |doc|
        jmeno = doc.data["name"].to_s
        rub = nastaveni[jmeno] || {}
        clanky = site.posts.docs.select { |p| Array(p.data["categories"]).map(&:to_s).include?(jmeno) }
                     .sort_by { |p| -p.date.to_i }
        recenze = rub["filtry"] ? clanky.select { |p| p.data["model"] } : []
        doc.data["katalog"] = katalog(jmeno, rub, recenze, clanky - recenze)
      end
    end

    private

    def katalog(jmeno, rub, recenze, ostatni)
      radky = recenze.each_with_index.map { |p, i| radek(jmeno, p, i) }
      filtry = Array(rub["filtry"]).map { |f| filtr(f, radky, jmeno) }.reject { |f| f["moznosti"].size < 2 }
      {
        "pocet" => radky.size,
        "pocet_text" => "#{radky.size} #{tvar_slova(radky.size, 'recenze', 'recenze', 'recenzí')}",
        "radky" => radky,
        "filtry" => filtry,
        "sloupce" => Array(rub["sloupce"]).map { |s| { "klic" => s, "nazev" => NAZVY_SLOUPCU.fetch(s, s) } },
        "razeni" => Array(rub["razeni"]).map { |s| { "klic" => s, "nazev" => NAZVY_RAZENI.fetch(s, s) } },
        "clanky" => ostatni,
      }
    end

    def tvar_slova(n, jeden, dva_az_ctyri, pet)
      return jeden if n == 1
      (2..4).cover?(n) ? dva_az_ctyri : pet
    end

    def bez_diakritiky(s)
      s.to_s.downcase.unicode_normalize(:nfd).gsub(/\p{Mn}/, "")
    end

    # Název do tabulky: z titulku, když ho upřesňuje („Gregory Optic 48 a 58“) nebo když
    # `model` vyjmenovává varianty („Gregory Katmai 55, Gregory Katmai 65“); jinak `model`.
    # Oddělovač podtitulku je „: “ nebo pomlčka s mezerami („AirZone Trek 45:55“ se nedělí).
    def nazev_a_podtitulek(p)
      model = p.data["model"].to_s
      titulek = p.data["title"].to_s.strip
      m = titulek.match(/:\s+|\s+[–—-]\s+/)
      return [model, nil] unless m
      pred = m.pre_match.strip
      po = m.post_match.strip
      po = po[0].upcase + po[1..] unless po.empty?
      nazev = if pred.downcase.start_with?(model.downcase) || (model.include?(",") && pred.size <= 60) then pred
              else model
              end
      [nazev, po.empty? ? nil : po]
    end

    def radek(jmeno, p, poradi)
      d = p.data
      nazev, podtitulek = nazev_a_podtitulek(p)
      objem = cislo(d["objem"])
      vaha = cislo(d["vaha"]) # „1550 (55L), 1650 (65L)“: bere se první číslo, jako na kartě recenze
      r = cislo(d["R-faktor"])
      hodn = cislo(d["hodnoceni"])
      strih = { "unisex" => "unisex", "ženy" => "damsky", "muži" => "pansky" }[d["sex"].to_s.downcase]
      hodnoty = {
        "objem" => objem && "#{desetinne(d['objem'])} l",
        "vaha" => gramy(d["vaha"]),
        "strih" => { "unisex" => "unisex", "damsky" => "dámský", "pansky" => "pánský" }[strih],
        "tvar" => { "nízké" => "nízké", "střední" => "středně vysoké", "vysoké" => "vysoké" }[d["tvar"].to_s.downcase],
        "urceni" => urceni(d["urceni"]),
        "typ" => d["typ"].to_s.downcase.then { |t| t.empty? ? nil : t },
        "r" => r && "R #{desetinne(d['R-faktor'])}",
      }
      hmotnost_pasma = PASMA["hmotnost-#{jmeno}"]
      pasma = {
        "objem" => objem && pasmo(PASMA["objem"], objem),
        "hmotnost" => vaha && hmotnost_pasma && pasmo(hmotnost_pasma, vaha),
        "izolace" => r && pasmo(PASMA["izolace"], r),
        "strih" => strih,
        "tvar" => bez_diakritiky(d["tvar"]).then { |t| t.empty? ? nil : t },
        "typ" => bez_diakritiky(d["typ"]).then { |t| t.empty? ? nil : t },
        "znacka" => d["znacka"].to_s.empty? ? nil : Utils.slugify(d["znacka"].to_s),
      }
      {
        "nazev" => nazev, "podtitulek" => podtitulek, "url" => p.url, "thumbnail" => d["thumbnail"].to_s,
        "znacka" => d["znacka"].to_s, "hodnoceni" => hodn && desetinne(d["hodnoceni"]),
        "hodnoty" => hodnoty, "pasma" => pasma.compact,
        "trideni" => { "datum" => poradi, "vaha" => vaha, "objem" => objem, "r" => r, "hodnoceni" => hodn }.compact,
      }
    end

    def pasmo(seznam, v)
      seznam.find { |_, _, podminka| podminka.(v) }&.first
    end

    # „Dlouhé výlety, krátké výlety, lehčí treking“ → „Dlouhé výlety, krátké výlety“
    def urceni(v)
      casti = v.to_s.split(",").map(&:strip).reject(&:empty?).first(2)
      return nil if casti.empty?
      s = casti.join(", ")
      s[0].upcase + s[1..]
    end

    def filtr(klic, radky, jmeno)
      pocty = Hash.new(0)
      radky.each { |r| pocty[r["pasma"][klic]] += 1 if r["pasma"][klic] }
      moznosti =
        if klic == "znacka"
          # Značky s jedinou recenzí by filtr natahovaly; slučují se do „Další“.
          jmena = radky.to_h { |r| [r["pasma"]["znacka"], r["znacka"]] }
          hlavni = pocty.select { |_, n| n >= 2 }.sort_by { |id, n| [-n, jmena[id]] }
          male = pocty.reject { |id, _| hlavni.to_h.key?(id) }
          vystup = hlavni.map { |id, n| [id, jmena[id], n] }
          unless male.empty?
            radky.each { |r| r["pasma"]["znacka"] = "dalsi" if male.key?(r["pasma"]["znacka"]) }
            vystup << ["dalsi", "Další", male.values.sum]
          end
          vystup
        elsif (seznam = klic == "hmotnost" ? PASMA["hmotnost-#{jmeno}"] : PASMA[klic])
          seznam.map { |id, popisek, _| [id, popisek, pocty[id]] }
        else
          VYCTY.fetch(klic, []).map { |id, popisek| [id, popisek, pocty[id]] }
        end
      moznosti = moznosti.reject { |_, _, n| n.zero? }
      { "klic" => klic, "nazev" => NAZVY_FILTRU.fetch(klic, klic),
        "moznosti" => moznosti.map { |id, popisek, n| { "id" => id, "nazev" => popisek, "pocet" => n } } }
    end
  end

  # Kapitoly průvodce (nadpisy druhé úrovně, u bot třetí) pro odkazy pod katalogem.
  Hooks.register :documents, :post_convert do |doc|
    next unless doc.collection.label == "categories"
    nadpisy = %w[h2 h3].lazy.map { |h| doc.content.scan(%r{<#{h} id="([^"]+)"[^>]*>(.*?)</#{h}>}m) }.find(&:any?) || []
    doc.data["kapitoly"] = nadpisy.map { |id, text| { "id" => id, "nazev" => text.gsub(/<[^>]+>/, "").strip } }
  end
end
