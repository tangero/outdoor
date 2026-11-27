module Jekyll
  class ProductLinker
    def self.link_products(content, site, current_url)
      return content if content.nil?
      
      # Načtení produktů z _data/products.yml
      products = site.data['products']
      return content if products.nil?

      # Celý dokument: doctype, <html lang> a <head> nechat beze změny, linkovat jen obsah <body>
      # (DocumentFragment by je zahodil a stránka by se vykreslovala v quirks módu)
      body_open = content.match(/<body\b[^>]*>/i)
      body_close = content.rindex(%r{</body>}i)
      if body_open && body_close && body_close > body_open.end(0)
        inner = link_products(content[body_open.end(0)...body_close], site, current_url)
        return content[0...body_open.end(0)] + inner + content[body_close..]
      end

      # Normalizace aktuální URL (odstranění index.html pokud existuje)
      normalized_current = current_url.sub(/index\.html$/, '')
      
      # Vytvoření HTML dokumentu pro lepší zpracování
      doc = Nokogiri::HTML::DocumentFragment.parse(content)
      
      # Produkty s předem sestavenými vzory (jednou za build, ne pro každý textový uzel)
      compiled = compiled_products(products)

      # Procházení textových uzlů
      doc.traverse do |node|
        next unless node.text?
        next if node.parent.name == 'a' # Přeskočit text v odkazech
        next if ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].include?(node.parent.name) # Přeskočit nadpisy
        # Nikdy neodkazovat v <head> (title, JSON-LD), skriptech, stylech ani uvnitř odkazů
        next if node.ancestors.any? { |a| %w[head title script style noscript a button textarea].include?(a.name) }

        original_text = node.text
        text = original_text.dup
        ancestor_hrefs = nil

        # Jeden průchod: názvy i varianty v jednom regexu, nejdelší shoda vyhrává, takže kratší
        # název se nechytí uvnitř delšího („Klymit Static V“ uvnitř „Klymit Static V2“)
        # a do vytvořeného odkazu se už nic nevnoří. Levný předfiltr: jen text s nějakým názvem.
        next unless compiled[:texts].any? { |t| text.include?(t) }

        text = text.gsub(compiled[:pattern]) do |match|
          product = compiled[:by_text][Regexp.last_match[:nazev]]
          # Odkaz na stránku samotnou ani do odkazu se stejnou URL nevkládáme
          if normalized_current.chomp('/') == product[:normalized_url]
            match
          else
            ancestor_hrefs ||= node.ancestors.select { |ancestor| ancestor.name == 'a' }.map { |ancestor| ancestor['href'] }
            ancestor_hrefs.include?(product[:url]) ? match : "<a href=\"#{product[:url]}\">#{match}</a>"
          end
        end

        # Pokud došlo ke změně, nahraď původní uzel novým HTML fragmentem
        if text != original_text
          replacement = Nokogiri::HTML::DocumentFragment.parse(text)
          node.replace(replacement)
        end
      end

      doc.to_html
    end
  end
  
  class ProductLinker
    # Celý název: ne uprostřed slova ani jako začátek delšího slova/čísla, volitelně v uvozovkách
    def self.compiled_products(products)
      @compiled = nil unless @compiled_for.equal?(products)
      @compiled_for = products
      @compiled ||= begin
        by_text = {}
        list = products.select { |p| p['name'] && p['url'] }.map do |product|
          { url: product['url'], normalized_url: product['url'].sub(/index\.html$/, '').chomp('/'),
            name: product['name'], variants: product['variants'] || [] }
        end
        # Nejdřív plné názvy, pak varianty; stejný text patří prvnímu produktu
        list.each { |p| by_text[p[:name]] ||= p }
        list.each { |p| p[:variants].each { |v| by_text[v] ||= p } }
        texts = by_text.keys.sort_by { |t| -t.length }
        alternace = texts.map { |t| Regexp.escape(t) }.join('|')
        {
          by_text: by_text,
          texts: texts,
          pattern: /(?:"|“|„)?(?<![\p{L}\p{N}])(?<nazev>#{alternace})(?![\p{L}\p{N}])(?:"|“|”)?/
        }
      end
    end
  end

  # Registruji hook na post_render, abych použil již vykreslený HTML
  Jekyll::Hooks.register [:posts, :pages], :post_render do |doc|
    if doc.output_ext == ".html" and doc.output
      doc.output = ProductLinker.link_products(doc.output, doc.site, doc.url)
    end
  end
end