# frozen_string_literal: true

# SEO údaje článků, které nejdou čistě spočítat v Liquidu:
# - `image` pro jekyll-seo-tag (og:image, twitter:image) z pole `thumbnail` přes Cloudinary,
# - u recenzí (mají `model`) titulek pro <title> se slovem „recenze“ (`seo_titulek`)
#   a strukturovaná data Product + Review s hodnocením a plusy/minusy (`recenze_ld`).
# Nadpis H1 a og:title zůstávají podle `title`.
module SeoRecenze
  CLD_UPLOAD = "https://res.cloudinary.com/dvwv5cne3/image/upload/"
  CLD_FETCH = "https://res.cloudinary.com/dvwv5cne3/image/fetch/"
  OG = "w_1200,h_630,c_pad,b_white,f_jpg,q_auto"
  MAX_TITULEK = 65

  module_function

  # Stejná logika jako _includes/cld.html.
  def cld(url, transformace)
    if url.start_with?(CLD_UPLOAD)
      CLD_UPLOAD + transformace + "/" + url.delete_prefix(CLD_UPLOAD)
    else
      CLD_FETCH + transformace + "/" + url
    end
  end

  def og_obrazek(thumbnail)
    return nil if thumbnail.nil? || thumbnail.to_s.strip.empty?

    url = thumbnail.to_s.strip
    return { "path" => url } unless url.include?("://") # lokální soubor, seo-tag ho doplní na absolutní URL

    { "path" => cld(url, OG), "width" => 1200, "height" => 630 }
  end

  # „Osprey Exos 48: Lehký batoh…“ (i „Model – podtitulek“) → „Osprey Exos 48 recenze: lehký batoh…“
  def titulek(title, site_title)
    hlava, ocas = title.to_s.split(/:\s+|\s+[–-]\s+/, 2)
    return nil if ocas.nil? || hlava.downcase.include?("recenze")

    ocas = ocas[0].downcase + ocas[1..] if ocas =~ /\A\p{Lu}\p{Ll}/
    zaklad = "#{hlava} recenze: #{ocas}"
    s_webem = "#{zaklad} | #{site_title}"
    s_webem.length <= MAX_TITULEK ? s_webem : zaklad
  end

  # „Nízká hmotnost, membrána Gore-Tex, …“ → seznam bodů
  def body(text)
    text.to_s.sub(/\.\s*\z/, "").split(/,\s+/).map(&:strip).reject(&:empty?)
  end

  def seznam(polozky)
    {
      "@type" => "ItemList",
      "itemListElement" => polozky.each_with_index.map do |p, i|
        { "@type" => "ListItem", "position" => i + 1, "name" => p }
      end,
    }
  end

  def recenze_ld(doc, site)
    d = doc.data
    return nil if d["hodnoceni"].nil?

    web = site.config["url"].to_s + site.config["baseurl"].to_s
    autor = { "@type" => "Organization", "name" => site.config["title"], "url" => "#{web}/about" }
    review = {
      "@type" => "Review",
      "name" => d["title"],
      "url" => web + doc.url,
      "datePublished" => doc.date.strftime("%Y-%m-%d"),
      "author" => autor,
      "publisher" => { "@type" => "Organization", "name" => site.config["title"], "url" => "#{web}/" },
      "reviewRating" => {
        "@type" => "Rating",
        "ratingValue" => d["hodnoceni"],
        "bestRating" => 10,
        "worstRating" => 0,
      },
    }
    plusy = body(d["pro"])
    minusy = body(d["proti"])
    review["positiveNotes"] = seznam(plusy) if plusy.any?
    review["negativeNotes"] = seznam(minusy) if minusy.any?

    produkt = { "@context" => "https://schema.org", "@type" => "Product", "name" => d["model"].to_s }
    produkt["brand"] = { "@type" => "Brand", "name" => d["znacka"] } if d["znacka"].to_s != ""
    obr = d["image"].is_a?(Hash) ? d["image"]["path"] : d["image"]
    produkt["image"] = obr if obr.to_s.include?("://")
    produkt["review"] = review
    produkt
  end
end

Jekyll::Hooks.register :documents, :pre_render do |doc|
  next unless %w[posts novinky].include?(doc.collection.label)

  d = doc.data
  if d["image"].nil? && (obr = SeoRecenze.og_obrazek(d["thumbnail"]))
    d["image"] = obr
    d["image_auto"] = true # jen pro og:image, šablony ho v textu nezobrazují
  end
  # Novinky nemají známku ani recenzi, titulek i schéma jen pro recenze.
  next unless doc.collection.label == "posts" && d["model"]

  d["seo_titulek"] ||= SeoRecenze.titulek(d["title"], doc.site.config["title"])
  d["recenze_ld"] = SeoRecenze.recenze_ld(doc, doc.site)
end
