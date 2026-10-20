/*
 * Blok „Naše akce“ v článku: aktuální akce nebo promo slot z vibecoding.cz
 * (správa v admin/promo na vibecoding.cz). Bez odpovědi zůstane blok skrytý.
 * Kontejner: <section id="vdp-promo" class="cl-promo" hidden></section> na začátku boční lišty;
 * na úzkém displeji (lišta je až pod článkem) se přesune do textu za úvodní odstavec.
 */
(function () {
  var box = document.getElementById('vdp-promo');
  if (!box || !window.fetch) return;
  var ZDROJ = 'https://www.vibecoding.cz';
  var mesice = ['ledna', 'února', 'března', 'dubna', 'května', 'června',
    'července', 'srpna', 'září', 'října', 'listopadu', 'prosince'];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function bezpecna(u) {
    u = String(u || '');
    return /^https:\/\//i.test(u) ? u : '';
  }
  // Banner z admin/promo: relativní cesta na vibecoding.cz (stejná pravidla jako jejich EventPromoAdZone)
  function obrazek(u) {
    u = String(u || '');
    if (u.indexOf(ZDROJ + '/') === 0) u = u.slice(ZDROJ.length);
    if (u.indexOf('..') >= 0 || u.indexOf('//') >= 0 || u.indexOf('\\') >= 0) return '';
    if (/^\/promo-media\/[A-Za-z0-9][A-Za-z0-9_-]{2,80}(\?v=\d+)?$/.test(u)) return ZDROJ + u;
    if (/^\/images\/[A-Za-z0-9._\/-]+\.(jpe?g|png|webp|gif)(\?v=\d+)?$/i.test(u)) return ZDROJ + u;
    return '';
  }
  function presunDoTextu() {
    if (!window.matchMedia || !window.matchMedia('(max-width: 991px)').matches) return;
    var text = document.querySelector('.cl-text');
    if (!text) return;
    var odstavce = [].filter.call(text.children, function (el) {
      return el.tagName === 'P' && !el.querySelector('img') && el.textContent.trim().length > 40;
    });
    var za = odstavce[0];
    if (za) za.insertAdjacentElement('afterend', box);
    else text.insertBefore(box, text.firstChild);
    box.classList.add('cl-promo--v-textu');
  }

  fetch(ZDROJ + '/api/active-promotion')
    .then(function (r) { return r.json(); })
    .then(function (e) {
      if (!e || (!e.slug && !e.isAd)) return;
      var url = '';
      if (e.clickUrl) {
        try {
          var cu = new URL(e.clickUrl);
          cu.searchParams.set('site', 'vybavenidoprirody');
          cu.searchParams.set('surface', 'article');
          url = cu.toString();
        } catch (_) { url = e.clickUrl; }
      } else if (e.slug) {
        url = ZDROJ + '/akce/' + encodeURIComponent(e.slug).replace(/%2F/gi, '/') +
          '/?utm_source=vybavenidoprirody&utm_medium=web&utm_campaign=event-promo';
      }
      url = bezpecna(url || e.externalUrl);
      if (!url) return;

      var stitek = e.isAd ? 'Reklama' : 'Naše akce';
      if (e.isAd && e.badgeLabel) stitek += ' · ' + e.badgeLabel;
      var rel = 'noopener' + (e.isAd && !e.isInternal ? ' sponsored' : '');
      var odkaz = 'href="' + esc(url) + '" target="_blank" rel="' + rel + '"';
      var banner = e.isAd ? obrazek(e.imageUrl) : '';

      if (banner) {
        box.classList.add('cl-promo--obrazek');
        box.innerHTML =
          '<p class="cl-promo__stitek">' + esc(stitek) + '</p>' +
          '<a class="cl-promo__banner" ' + odkaz + '>' +
          '<img src="' + esc(banner) + '" alt="' + esc(e.imageAlt || e.title) + '" width="1800" height="771" loading="lazy" decoding="async">' +
          '</a>';
      } else {
        var termin = '';
        if (!e.isAd && e.date) {
          var d = e.date.split('-');
          var mesto = e.city || (e.location ? e.location.split(',').slice(-1)[0].trim() : '');
          termin = parseInt(d[2], 10) + '. ' + mesice[parseInt(d[1], 10) - 1] + ' ' + d[0] + (mesto ? ' · ' + mesto : '');
        }
        box.innerHTML =
          '<p class="cl-promo__stitek">' + esc(stitek) + '</p>' +
          '<p class="cl-promo__titulek">' + esc(e.title) + '</p>' +
          (termin ? '<p class="cl-promo__termin">' + esc(termin) + '</p>' : '') +
          (e.bannerDescription ? '<p class="cl-promo__popis">' + esc(e.bannerDescription) + '</p>' : '') +
          (e.highlight ? '<p class="cl-promo__termin">' + esc(e.highlight) + '</p>' : '') +
          '<a class="cl-promo__tlacitko" ' + odkaz + '>' +
          esc(e.ctaLabel || (e.isAd ? 'Více' : 'Detaily akce')) + ' →</a>';
      }
      presunDoTextu();
      box.hidden = false;

      // Zobrazení se počítá, až je blok aspoň z poloviny vidět
      if (e.impressionUrl && navigator.sendBeacon && 'IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (zaznamy) {
          if (!zaznamy.some(function (z) { return z.intersectionRatio >= 0.5; })) return;
          io.disconnect();
          try {
            var iu = new URL(e.impressionUrl, ZDROJ);
            iu.searchParams.set('site', 'vybavenidoprirody');
            iu.searchParams.set('surface', 'article');
            navigator.sendBeacon(iu.toString());
          } catch (_) {}
        }, { threshold: [0.5] });
        io.observe(box);
      }
    })
    .catch(function () {});
})();
