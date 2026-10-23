# SEO úpravy před vykreslením:
#  - stránkování /pageN/ ven ze sitemapy (noindex,follow přidává default.html),
#  - meta description do 155 znaků (z front matter, perexu nebo úryvku),
#  - reálné lastmod pro sitemapu (rubriky a přehledy = datum nejnovější recenze).
module SeoQuickwins
  MAX = 155

  def self.clean(text)
    t = text.to_s.dup
    t.gsub!(/\{%.*?%\}|\{\{.*?\}\}/m, ' ')        # Liquid
    t.gsub!(/<[^>]+>/, ' ')                         # HTML
    t.gsub!(/!\[[^\]]*\]\([^)]*\)/, ' ')           # obrázky
    t.gsub!(/\[([^\]]*)\]\([^)]*\)/, '\1')         # odkazy -> text
    t.gsub!(/^\s*#+\s*/, '')                        # nadpisy
    t.gsub!(/[*_`>|]/, '')
    t.gsub(/\s+/, ' ').strip
  end

  def self.shorten(text)
    t = clean(text)
    return t if t.length <= MAX
    cut = t[0, MAX - 1]
    cut = cut[0, cut.rindex(' ')] if cut.rindex(' ') && cut.rindex(' ') > 80
    cut.sub(/[\s,;:.\-–]+\z/, '') + '…'
  end

  def self.describe(item)
    d = item.data
    src = d['description']
    src = d['perex'] if src.to_s.strip.empty?
    if src.to_s.strip.empty? && d['excerpt']
      src = d['excerpt'].respond_to?(:content) ? d['excerpt'].content : d['excerpt'].to_s
    end
    src = item.content if clean(src).empty? && item.respond_to?(:content)
    return if clean(src).empty?
    d['description'] = shorten(src)
  end
end

Jekyll::Hooks.register :site, :pre_render do |site|
  posts = site.posts.docs
  newest = (posts + (site.collections['novinky']&.docs || [])).map { |p| p.date }.max
  by_cat = Hash.new { |h, k| h[k] = posts.select { |p| p.data['categories'].to_a.include?(k) }.map(&:date).max }

  site.pages.each do |pg|
    if pg.respond_to?(:pager) && pg.pager && pg.pager.page.to_i > 1
      pg.data['sitemap'] = false
    end
    if pg.url =~ %r{\A/([a-z0-9-]+)/prehled/\z}
      pg.data['last_modified_at'] ||= by_cat[$1]
    elsif pg.url == '/' && newest
      pg.data['last_modified_at'] ||= newest
    end
    SeoQuickwins.describe(pg) if pg.output_ext == '.html'
  end

  site.documents.each do |doc|
    if doc.collection.label == 'categories'
      lm = by_cat[doc.data['name'] || doc.basename_without_ext]
      doc.data['last_modified_at'] ||= (lm || newest)
    end
    SeoQuickwins.describe(doc)
  end
end
