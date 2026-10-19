/*
 * Blok „Naše akce“ v článku: aktuální akce nebo promo slot z vibecoding.cz
 * (správa v admin/promo na vibecoding.cz). Bez odpovědi zůstane blok skrytý.
 * Kontejner: <section id="vdp-promo" class="cl-promo" hidden></section>
 */
(function () {
  var box = document.getElementById('vdp-promo');
  if (!box || !window.fetch) return;
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

  fetch('https://www.vibecoding.cz/api/active-promotion')
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
        url = 'https://www.vibecoding.cz/akce/' + encodeURIComponent(e.slug).replace(/%2F/gi, '/') +
          '/?utm_source=vybavenidoprirody&utm_medium=web&utm_campaign=event-promo';
      }
      url = bezpecna(url || e.externalUrl);
      if (!url) return;

      var stitek = e.isAd ? 'Reklama' : 'Naše akce';
      if (e.isAd && e.badgeLabel) stitek += ' · ' + e.badgeLabel;
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
        '<a class="cl-promo__tlacitko" href="' + esc(url) + '" target="_blank" rel="noopener' + (e.isAd ? ' sponsored' : '') + '">' +
        esc(e.ctaLabel || (e.isAd ? 'Více' : 'Detaily akce')) + ' →</a>';
      box.hidden = false;

      // Zobrazení se počítá, až je blok aspoň z poloviny vidět
      if (e.impressionUrl && navigator.sendBeacon && 'IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (zaznamy) {
          if (!zaznamy.some(function (z) { return z.intersectionRatio >= 0.5; })) return;
          io.disconnect();
          try {
            var iu = new URL(e.impressionUrl);
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
