module Jekyll
  class ProductLinker
    def self.link_products(content, site, current_url)
      return content if content.nil?
      
      # Načtení produktů z _data/products.yml
      products = site.data['products']
      return content if products.nil?
      
      # Normalizace aktuální URL (odstranění index.html pokud existuje)
      normalized_current = current_url.sub(/index\.html$/, '')
      
      # Vytvoření HTML dokumentu pro lepší zpracování
      doc = Nokogiri::HTML::DocumentFragment.parse(content)
      
      # Procházení textových uzlů
      doc.traverse do |node|
        next unless node.text?
        next if node.parent.name == 'a' # Přeskočit text v odkazech
        next if ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].include?(node.parent.name) # Přeskočit nadpisy
        
        original_text = node.text
        text = original_text.dup
        
        # Procházení produktů a jejich variant
        products.each do |product|
          next unless product['name'] && product['url']
          
          # Normalizace URL produktu
          normalized_product_url = product['url'].sub(/index\.html$/, '')
          
          # Pokud je aktuální stránka stejná jako cílová stránka produktu, přeskoč produkt
          if normalized_current == normalized_product_url
            next
          end
          
          # Pokud některý z předků již obsahuje odkaz s touto URL, přeskoč produkt
          if node.ancestors.any? { |ancestor| ancestor.name == 'a' && ancestor['href'] == product['url'] }
            next
          end
          
          # Vytvoření pole všech možných názvů produktu
          names = [product['name']]
          names += product['variants'] if product['variants']
          
          # Seřazení podle délky (nejdelší první)
          names.sort_by! { |name| -name.length }
          
          # Nahrazení názvů odkazy; pokud nastane nahrazení, ukončím zpracování daného produktu
          names.each do |name|
            escaped_name = Regexp.escape(name)
            replacement_count = text.gsub!( /\b#{escaped_name}\b/ ) do |match|
              "<a href=\"#{product['url']}\">#{match}</a>"
            end
            if replacement_count
              break
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
  
  # Registruji hook na post_render, abych použil již vykreslený HTML
  Jekyll::Hooks.register [:posts, :pages], :post_render do |doc|
    if doc.output_ext == ".html" and doc.output
      doc.output = ProductLinker.link_products(doc.output, doc.site, doc.url)
    end
  end
end