# Mediumish Jekyll Theme - Change Log

## 2026-10-20 (Vybavení do přírody)
- Nová hlavička: rubriky, Srovnání, Novinky a Značky v jedné liště, české hledání, odkaz na přeskočení na obsah. Pruh ikon rubrik zůstal jen na titulce, v rubrikách a na stránkách značek a srovnání.
- Nová patička: o webu, autoři (Martin Plachta, Patrick Zandl), kontakt, rubriky s počty recenzí a naše další weby. Pás „Prozkoumejte“ s fotkou zrušen.
- Rozcestník srovnávacích tabulek `/srovnani/`.
- Starý článek o Lowe Alpine AirZone Trek 45:55 a samostatné články o Osprey Talon 22 a Gregory Paragon 58 přesměrované na novější recenze.

## 2026-10-19 (Vybavení do přírody)
- Nová podoba článku: rozhodovací karta recenze, navigace po oddílech, žebříček kategorie, alternativy, seznam zdrojů (plugin `_plugins/srovnani.rb`, styly `cl-*`).
- Blok „Naše akce“ z vibecoding.cz (`assets/js/promo.js`) místo Google AdSense; AdSense vypnutý.
- Pod každým článkem hodnocení šesti reakcemi (widget `mg-comments` z vibecoding.cz, bez diskuse). Slug `vybavenidoprirody-<cesta-článku>`; vypnutí v článku přes `rating: false`, ruční slug přes `rating_slug` (starý článek o Lowe Alpine AirZone Trek 45:55 by jinak kolidoval s novým).

## 2019-05-16, v1.0.36
- docker-composer.yml
- better responsiveness for 1920x1080 resolution

## 2019-04-02, v1.0.35
- Fixed Github pages issue with ratings under 1
- Added support for local avatars

## 2019-03-22, v1.0.34
- Deferred font awesome and google fonts

## 2019-03-22, v1.0.33
- Added image lazy load (config.yml - lazyimages: "enabled/disabled")
- Added object cover images instead of background images for home featured cards
- Removed disqus count from homepage for better performance

## 2019-03-20, v1.0.32
- Centered avatar image on smaller devices
- Removed .html endings in cats/tags
- Added Linkedin share 
- Added Table of Contents (toc:true)
- Added Paragraph before TOC (beforetoc: "My short description here")


## 2019-03-20, v1.0.31
- Added adsense support (activate via _config.yml)
- Fixed share for large headers

## 2019-03-20, v1.0.30
- Added Tags support
- Removed Google + sharing, no longer needed

## 2019-03-01, v1.0.29
- Fixed Jumbotron categories link

## 2019-03-01, v1.0.28
- Added blurred text on spoilers
- Added half stars for ratings

## 2019-03-01, v1.0.27
- Reveal hidden spoilers on click
- Syntax line numbers
- Post rating stars
- Fixed category links with more than 1 word

## 2019-02-14
- Fixed Feed site title not showing
- Added 404 page

## 2019-02-10
- Fixed CSS Jumbotron categories

## 2019-02-09
- Fixed Category links are now compatible with Github pages. Archive still available for non Github pages.
- Added Search
- Added SEO

## 2018-11-08
- Fixed reponsive footer jumbotron for tags

## 2018-11-07
- Added external image support

## 2018-09-12
- Added option to disable comments in a specific post with `comments: false` in YAML front matter
