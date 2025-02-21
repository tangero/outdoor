#!/usr/bin/env ruby
require 'yaml'
require 'set'
require 'time'

# Inicializace množiny pro unikátní modely
product_set = Set.new

# Funkce pro vytvoření varianty názvu (text před prvním číslem)
def create_variant(name)
  # Najde pozici prvního čísla v textu
  match = name.match(/\d/)
  if match
    # Vezme text před číslem a odstraní mezery na konci
    variant = name[0...match.begin(0)].strip
    # Vrátí variantu pouze pokud je dostatečně dlouhá a liší se od původního názvu
    return variant if variant.length > 3 && variant != name
  end
  nil
end

# Procházení všech souborů v _posts
Dir.glob("_posts/**/*.md") do |file|
  content = File.read(file)
  if content =~ /\A---\s*\n(.*?)\n---\s*\n/m
    front_matter = $1
    begin
      # Bezpečnější způsob načítání YAML s povolenými aliasy
      data = YAML.safe_load(front_matter, permitted_classes: [Time, Date], aliases: true)
      if data && data['model']
        # Získáme URL z názvu souboru bez datové části
        category = file.split('/')[1] # Získáme kategorii z cesty (např. "batohy")
        filename = File.basename(file, '.md').sub(/^\d{4}-\d{2}-\d{2}-/, '') # Odstraníme datovou část
        url = "/#{category}/#{filename}/"
        product_set << [data['model'], url]
      end
    rescue => e
      puts "Chyba při zpracování souboru #{file}: #{e.message}"
      next
    end
  end
end

# Vytvoříme pole produktů, seřazené podle abecedy
products = product_set.to_a.sort_by { |model, _| model }.map do |model, url|
  variants = []
  # Vytvoříme variantu názvu
  variant = create_variant(model)
  variants << variant if variant
  
  {
    'name' => model,
    'url' => url,
    'variants' => variants
  }
end

# Zapíšeme výsledky do souboru _data/generated_products.yml
File.open("_data/generated_products.yml", "w") do |f|
  f.write("# Automaticky generovaný seznam produktů\n")
  f.write("# Pro každý produkt jsou automaticky generovány variants (text před prvním číslem)\n")
  f.write("# Můžete ručně upravit nebo doplnit další variants\n\n")
  f.write("# ===== Začátek automaticky generovaných položek (#{Time.now.strftime('%Y-%m-%d %H:%M:%S')}) =====\n")
  f.write(products.to_yaml)
  f.write("\n# ===== Konec automaticky generovaných položek =====\n")
end

puts "Seznam produktů byl uložen do _data/generated_products.yml" 