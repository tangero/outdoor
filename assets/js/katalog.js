/* Katalog na stránce rubriky (_layouts/category.liquid): filtry, řazení, štítky aktivních
   filtrů a „Načíst další“. Vybrané filtry a řazení se propisují do adresy (?objem=36-64). */
(function () {
    var kat = document.querySelector('[data-kat]');
    if (!kat) return;
    var form = kat.querySelector('[data-kat-filtry]');
    var tbody = kat.querySelector('[data-kat-radky]');
    var radky = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var vyber = kat.querySelector('[data-kat-razeni]');
    var vysledek = kat.querySelector('[data-kat-vysledek]');
    var stitky = kat.querySelector('[data-kat-stitky]');
    var prazdno = kat.querySelector('[data-kat-prazdno]');
    var dalsi = kat.querySelector('[data-kat-dalsi]');
    var otevrit = kat.querySelector('[data-kat-otevrit]');
    var pocetFiltru = kat.querySelector('[data-kat-pocet-filtru]');
    var zobrazit = kat.querySelector('[data-kat-zobrazit]');
    var panel = document.getElementById('kat-filtry');
    var NA_STRANKU = 20;
    var limit = NA_STRANKU;
    var celkem = radky.length;

    kat.classList.add('kat--js');

    function recenze(n) {
        return n + (n === 1 ? ' recenze' : n >= 2 && n <= 4 ? ' recenze' : ' recenzí');
    }

    function aktivni() {
        var vybrane = {};
        Array.prototype.forEach.call(form.querySelectorAll('input:checked'), function (i) {
            (vybrane[i.name] = vybrane[i.name] || []).push(i.value);
        });
        return vybrane;
    }

    function odpovida(tr, vybrane) {
        return Object.keys(vybrane).every(function (klic) {
            return vybrane[klic].indexOf(tr.getAttribute('data-f-' + klic)) !== -1;
        });
    }

    function seradit() {
        var klic = vyber ? vyber.value : 'datum';
        var smer = klic === 'hodnoceni' || klic === 'r' ? -1 : 1;
        radky.sort(function (a, b) {
            var x = a.getAttribute('data-t-' + klic), y = b.getAttribute('data-t-' + klic);
            // Řádky bez hodnoty (např. chybí hmotnost) jdou na konec
            if (x === null || y === null) return (x === null) - (y === null);
            var rozdil = (parseFloat(x) - parseFloat(y)) * smer;
            return rozdil || a.getAttribute('data-t-datum') - b.getAttribute('data-t-datum');
        });
        radky.forEach(function (tr) { tbody.appendChild(tr); });
    }

    function adresa(vybrane) {
        var q = [];
        Object.keys(vybrane).forEach(function (klic) {
            q.push(encodeURIComponent(klic) + '=' + vybrane[klic].map(encodeURIComponent).join(','));
        });
        if (vyber && vyber.value !== 'datum') q.push('razeni=' + encodeURIComponent(vyber.value));
        var url = location.pathname + (q.length ? '?' + q.join('&') : '') + location.hash;
        try { history.replaceState(null, '', url); } catch (e) { /* bez history API */ }
    }

    function vykreslit() {
        var vybrane = aktivni();
        var shoda = 0;
        radky.forEach(function (tr) {
            var ok = odpovida(tr, vybrane);
            if (ok) shoda++;
            tr.hidden = !ok || shoda > limit;
        });
        var filtrovano = Object.keys(vybrane).length > 0;
        vysledek.textContent = filtrovano ? 'Vyhovuje ' + shoda + ' z ' + celkem : recenze(celkem);
        prazdno.hidden = shoda > 0;
        dalsi.hidden = shoda <= limit;
        dalsi.textContent = 'Načíst dalších ' + Math.min(NA_STRANKU, shoda - limit);
        if (zobrazit) zobrazit.textContent = shoda ? 'Zobrazit ' + recenze(shoda) : 'Nic neodpovídá';

        stitky.textContent = '';
        var pocet = 0;
        Array.prototype.forEach.call(form.querySelectorAll('input:checked'), function (i) {
            pocet++;
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'kat-stitek';
            b.setAttribute('aria-label', 'Zrušit filtr ' + i.getAttribute('data-nazev'));
            b.innerHTML = '<span></span><span aria-hidden="true">×</span>';
            b.firstChild.textContent = i.getAttribute('data-nazev');
            b.addEventListener('click', function () { i.checked = false; zmena(); });
            stitky.appendChild(b);
        });
        pocetFiltru.textContent = pocet ? '(' + pocet + ')' : '';
        adresa(vybrane);
    }

    function zmena() {
        limit = NA_STRANKU;
        vykreslit();
    }

    // Výchozí stav z adresy
    var parametry = {};
    location.search.replace(/^\?/, '').split('&').forEach(function (cast) {
        if (!cast) return;
        var kv = cast.split('=');
        parametry[decodeURIComponent(kv[0])] = (kv[1] || '').split(',').map(decodeURIComponent);
    });
    Array.prototype.forEach.call(form.querySelectorAll('input'), function (i) {
        if (parametry[i.name] && parametry[i.name].indexOf(i.value) !== -1) i.checked = true;
    });
    if (vyber && parametry.razeni && vyber.querySelector('option[value="' + parametry.razeni[0] + '"]')) {
        vyber.value = parametry.razeni[0];
    }

    form.addEventListener('change', zmena);
    if (vyber) vyber.addEventListener('change', function () { seradit(); zmena(); });
    dalsi.addEventListener('click', function () { limit += NA_STRANKU; vykreslit(); });
    Array.prototype.forEach.call(kat.querySelectorAll('[data-kat-zrusit]'), function (b) {
        b.addEventListener('click', function () { form.reset(); zmena(); });
    });

    // Panel filtrů na mobilu
    function panelOtevreny(stav) {
        panel.classList.toggle('kat-panel--otevreny', stav);
        document.documentElement.classList.toggle('kat-zamceno', stav);
        otevrit.setAttribute('aria-expanded', stav ? 'true' : 'false');
        if (stav) { var prvni = panel.querySelector('input'); if (prvni) prvni.focus(); }
        else otevrit.focus();
    }
    otevrit.addEventListener('click', function () { panelOtevreny(true); });
    Array.prototype.forEach.call(kat.querySelectorAll('[data-kat-zavrit]'), function (b) {
        b.addEventListener('click', function () { panelOtevreny(false); });
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && panel.classList.contains('kat-panel--otevreny')) panelOtevreny(false);
    });

    seradit();
    vykreslit();
})();
