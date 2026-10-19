# Pro každou recenzi spočítá data rozhodovací karty a bočního panelu:
# kategorii uvnitř rubriky (např. batohy 20–35 l), pořadí podle hmotnosti,
# krátký žebříček a tři alternativy. Výsledek je v page.srovnani.
module Jekyll
  class Srovnani < Generator
    priority :low

    PREHLEDY = {
      "batohy" => "/batohy/prehled/",
      "boty" => "/boty/prehled/",
      "karimatky" => "/karimatky/prehled/",
    }.freeze

    # U bot hmotnost neporovnáváme: starší recenze uvádějí někdy pár, někdy jednu botu.
    PODLE_HMOTNOSTI = %w[batohy karimatky].freeze

    def generate(site)
      recenze = site.posts.docs.select { |p| p.data["model"] && rubrika(p) }
      recenze.group_by { |p| [rubrika(p), segment(p)] }.each do |(rub, seg), skupina|
        skupina.each { |p| p.data["srovnani"] = srovnani(p, rub, seg, skupina, recenze) }
      end
    end

    private

    def rubrika(p)
      Array(p.data["categories"]).map(&:to_s).find { |c| PREHLEDY.key?(c) }
    end

    def cislo(v)
      return v.to_f if v.is_a?(Numeric)
      m = v.to_s.match(/\d+(?:[.,]\d+)?/)
      m && m[0].tr(",", ".").to_f
    end

    def segment(p)
      d = p.data
      case rubrika(p)
      when "batohy"
        o = cislo(d["objem"])
        return "Batohy" unless o
        if o < 20 then "Batohy do 20 l"
        elsif o <= 35 then "Batohy 20–35 l"
        elsif o < 65 then "Batohy 36–64 l"
        else "Batohy od 65 l"
        end
      when "karimatky"
        { "nafukovací" => "Nafukovací karimatky", "samonafukovací" => "Samonafukovací karimatky",
          "pěnová" => "Pěnové karimatky" }.fetch(d["typ"].to_s.downcase, "Karimatky")
      when "boty"
        { "nízké" => "Nízké boty", "střední" => "Středně vysoké boty",
          "vysoké" => "Vysoké boty" }.fetch(d["tvar"].to_s.downcase, "Boty")
      end
    end

    # „ze 17“, „ze 3“, ale „z 5“: podle výslovnosti číslovky
    def z_ze(n)
      [2, 3, 4, 7, 17].include?(n) || n.to_s.start_with?("7") || (100..199).cover?(n) ? "ze" : "z"
    end

    # Druhý pád množného čísla do věty „Nejlehčí ze 17 …“
    GENITIV = {
      "Batohy do 20 l" => "batohů do 20 l", "Batohy 20–35 l" => "batohů 20–35 l",
      "Batohy 36–64 l" => "batohů 36–64 l", "Batohy od 65 l" => "batohů od 65 l", "Batohy" => "batohů",
      "Nafukovací karimatky" => "nafukovacích karimatek", "Samonafukovací karimatky" => "samonafukovacích karimatek",
      "Pěnové karimatky" => "pěnových karimatek", "Karimatky" => "karimatek",
    }.freeze

    def gramy(v)
      g = cislo(v)
      return nil unless g
      g.round.to_s.reverse.scan(/\d{1,3}/).join(" ").reverse + " g"
    end

    def desetinne(v)
      v.to_s.sub(/\.0\z/, "").tr(".", ",")
    end

    def popis(p, rub)
      d = p.data
      casti = case rub
              when "batohy" then [gramy(d["vaha"]), (d["objem"] && "#{desetinne(d['objem'])} l")]
              when "karimatky" then [gramy(d["vaha"]), (d["R-faktor"] && "R #{desetinne(d['R-faktor'])}")]
              else [d["tvar"], d["urceni"]]
              end
      casti << "#{desetinne(d['hodnoceni'])}/10" if d["hodnoceni"]
      casti.compact.map(&:to_s).reject(&:empty?).join(" · ")
    end

    def karta(p, rub, duvod)
      { "model" => p.data["model"], "url" => p.url, "thumbnail" => p.data["thumbnail"].to_s,
        "popis" => popis(p, rub), "duvod" => duvod }
    end

    def srovnani(p, rub, seg, skupina, recenze)
      model = p.data["model"]
      ostatni = skupina.reject { |q| q.data["model"] == model }.uniq { |q| q.data["model"] }
      hodn = ->(q) { cislo(q.data["hodnoceni"]) || 0 }
      vaha = ->(q) { cislo(q.data["vaha"]) }
      vysledek = { "segment" => seg, "prehled" => PREHLEDY[rub], "pocet" => ostatni.size + 1 }
      # Věta pod „**Hodnocení:** 8/10“ na konci recenze vysvětluje známku
      zduvodneni = p.content[/\*\*Hodnocení:\*\*[^\n]*\n+[ \t]*([^\n#|*][^\n]+)/, 1]
      vysledek["zduvodneni"] = zduvodneni.strip if zduvodneni

      if PODLE_HMOTNOSTI.include?(rub) && vaha.(p)
        poradi = ([p] + ostatni).select { |q| vaha.(q) }.sort_by { |q| [vaha.(q), q.data["model"]] }
        i = poradi.index(p)
        vysledek["metrika"] = "hmotnosti"
        vysledek["poradi"] = i + 1
        vysledek["pocet_s_vahou"] = poradi.size
        n = poradi.size
        kolik = "#{z_ze(n)} #{n} #{GENITIV.fetch(seg, seg.downcase)} v našem přehledu"
        vysledek["veta"] =
          if n < 3 then nil
          elsif i.zero? then "Nejlehčí #{kolik}."
          elsif i == n - 1 then "Nejtěžší #{kolik}."
          else "#{i + 1}. nejlehčí #{kolik}."
          end
      else
        poradi = ([p] + ostatni).sort_by { |q| [-hodn.(q), q.data["model"].to_s] }
        vysledek["metrika"] = "hodnocení"
      end

      i = poradi.index(p) || 0
      vyber = poradi.first(5)
      vyber = poradi.first(4) + [p] if i >= 5
      vysledek["zebricek"] = vyber.map do |q|
        hodnota = vysledek["metrika"] == "hmotnosti" ? gramy(q.data["vaha"]) : "#{desetinne(q.data['hodnoceni'])}/10"
        { "poradi" => poradi.index(q) + 1, "model" => q.data["model"], "url" => q.url,
          "hodnota" => hodnota, "aktualni" => q.equal?(p) }
      end

      vysledek["alternativy"] = alternativy(p, rub, ostatni, recenze, hodn, vaha)
      vysledek
    end

    def alternativy(p, rub, ostatni, recenze, hodn, vaha)
      # Karty bez fotky vypadají prázdně: když je z čeho vybírat, bereme jen recenze s fotkou
      s_fotkou = ->(q) { !q.data["thumbnail"].to_s.strip.empty? }
      ostatni = ostatni.select(&s_fotkou) if ostatni.count(&s_fotkou) >= 3
      vybrane = []
      pridej = lambda do |q, duvod|
        next if q.nil? || vybrane.any? { |k| k["model"] == q.data["model"] }
        vybrane << karta(q, rub, duvod)
      end

      lepsi = ostatni.select { |q| hodn.(q) > hodn.(p) }.max_by { |q| [hodn.(q), -(vaha.(q) || 9999)] }
      pridej.(lepsi, "Lépe hodnocený")

      if PODLE_HMOTNOSTI.include?(rub) && vaha.(p)
        lehci = ostatni.select { |q| vaha.(q) && vaha.(q) < vaha.(p) }.min_by { |q| vaha.(q) }
        if lehci
          pridej.(lehci, "Lehčí")
        else
          pridej.(ostatni.select { |q| vaha.(q) }.min_by { |q| vaha.(q) - vaha.(p) }, "Nejbližší hmotností")
        end
      end

      znacka = p.data["znacka"]
      if znacka
        stejna = recenze.find do |q|
          rubrika(q) == rub && q.data["znacka"] == znacka && q.data["model"] != p.data["model"] && s_fotkou.(q) &&
            vybrane.none? { |k| k["model"] == q.data["model"] }
        end
        pridej.(stejna, "Od stejné značky")
      end

      ostatni.sort_by { |q| -hodn.(q) }.each do |q|
        break if vybrane.size >= 3
        pridej.(q, "Ze stejné kategorie")
      end
      # Malá kategorie (např. jediný batoh do 20 l): doplníme z celé rubriky
      recenze.select { |q| rubrika(q) == rub && q.data["model"] != p.data["model"] && s_fotkou.(q) }
             .sort_by { |q| [((cislo(q.data["objem"]) || 999) - (cislo(p.data["objem"]) || 0)).abs, -hodn.(q)] }.each do |q|
        break if vybrane.size >= 3
        pridej.(q, "Další z rubriky")
      end
      vybrane.first(3)
    end
  end
end
