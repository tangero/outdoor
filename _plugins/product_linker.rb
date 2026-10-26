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

        # Procházení produktů a jejich variant
        compiled.each do |product|
          # Levný předfiltr: vzor se shoduje jen tehdy, když text obsahuje název nebo variantu
          next unless text.include?(product[:name]) || product[:variants].any? { |v| text.include?(v[:text]) }

          # Pokud je aktuální stránka stejná jako cílová stránka produktu (bez ohledu na koncové lomítko), přeskoč produkt
          next if normalized_current.chomp('/') == product[:normalized_url]

          # Pokud některý z předků již obsahuje odkaz s touto URL, přeskoč produkt
          ancestor_hrefs ||= node.ancestors.select { |ancestor| ancestor.name == 'a' }.map { |ancestor| ancestor['href'] }
          next if ancestor_hrefs.include?(product[:url])

          # Nejprve celé jméno produktu s různými typy uvozovek, pak nejdelší shodná varianta
          if text.match(product[:pattern])
            text.gsub!(product[:pattern], product[:replacement])
          else
            product[:variants].each do |variant|
              if text.match(variant[:pattern])
                text.gsub!(variant[:pattern], product[:replacement])
                break
              end
            end
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
    # Pattern pro hledání textu s různými typy uvozovek nebo bez nich
    def self.quoted_pattern(text)
      /\b(?:"|"|„)?#{Regexp.escape(text)}(?:"|")?/
    end

    def self.compiled_products(products)
      @compiled = nil unless @compiled_for.equal?(products)
      @compiled_for = products
      @compiled ||= products.select { |p| p['name'] && p['url'] }.map do |product|
        {
          name: product['name'],
          url: product['url'],
          normalized_url: product['url'].sub(/index\.html$/, '').chomp('/'),
          pattern: quoted_pattern(product['name']),
          replacement: "<a href=\"#{product['url']}\">\\0</a>",
          variants: (product['variants'] || []).sort_by { |n| -n.length }.map { |v| { text: v, pattern: quoted_pattern(v) } }
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