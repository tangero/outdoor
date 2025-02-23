#!/usr/bin/env python3

import os
import re
import requests
import hashlib
import json


def slugify(text):
    text = text.lower()
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^\w\-]', '', text)
    return text


def download_image(url, download_dir='assets/downloaded', name_hint=None, counter=None):
    """Stáhne obrázek z dané URL a uloží jej do download_dir. Pokud jsou name_hint a counter zadány, použije je pro název souboru, jinak odvodí název z MD5 hashe URL."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Extrakce přípony souboru, pokud není nalezena, použijeme .jpg
            _, ext = os.path.splitext(url)
            if not ext:
                ext = '.jpg'

            if name_hint and counter is not None:
                file_name = f"{name_hint}_{counter}{ext}"
            else:
                file_name = hashlib.md5(url.encode()).hexdigest() + ext

            os.makedirs(download_dir, exist_ok=True)
            file_path = os.path.join(download_dir, file_name)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"Obrázek stažen: {url} -> {file_path}")
            return file_path
        else:
            print(f"Chyba při stahování {url}. Stavový kód: {response.status_code}")
    except Exception as e:
        print(f"Výjimka při stahování {url}: {e}")
    return None


def process_markdown_files(root_dir='_posts'):
    """Prochází všechny .md soubory v root_dir, najde obrázky a stáhne je, pokud nejsou z povolených zdrojů. Pokud je v YAML přítomno pole title, použije ho pro název souboru."""
    url_mapping = {}
    for current_root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(current_root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Pokus o extrakci YAML front matter a získání hodnoty model (nebo title jako fallback)
                label = None
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) > 2:
                        yaml_content = parts[1]
                        match_model = re.search(r'^model\s*:\s*(.*)$', yaml_content, re.MULTILINE)
                        if match_model:
                            label = match_model.group(1).strip().strip('"').strip("'")
                        else:
                            match_title = re.search(r'^title\s*:\s*(.*)$', yaml_content, re.MULTILINE)
                            if match_title:
                                label = match_title.group(1).strip().strip('"').strip("'")
                slug = slugify(label) if label else None
                img_counter = 1

                # Najdeme všechny markdown obrázky ve tvaru ![popisek](url)
                image_urls = re.findall(r'!\[.*?\]\((.*?)\)', content)
                for url in image_urls:
                    prefix_cloud = '@https://res.cloudinary.com/dvwv5cne3/image/fetch/w_auto,h_450,c_fill,g_auto,f_auto,q_auto/'
                    if url.startswith(prefix_cloud):
                        url = url[len(prefix_cloud):]
                    # Zpracujeme pouze absolutní URL, které nezačínají indexováním lokálních souborů
                    if url.startswith('http') and 'www.vybavenidoprirody.com' not in url:
                        if url in url_mapping:
                            continue  # již stažený obrázek
                        if slug:
                            new_path = download_image(url, name_hint=slug, counter=img_counter)
                            img_counter += 1
                        else:
                            new_path = download_image(url)
                        if new_path:
                            url_mapping[url] = new_path
    return url_mapping


def save_mapping(mapping, output_file='assets/downloaded/download_map.json'):
    """Uloží mapování původních URL a nových cest do JSON souboru."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)
    print(f"Mapa URL byla uložena do {output_file}")


if __name__ == '__main__':
    mapping = process_markdown_files('_posts')
    save_mapping(mapping) 