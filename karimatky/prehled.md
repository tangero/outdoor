---
layout: default
title: "Přehled karimatek"
permalink: /karimatky/prehled/
---

<h1>Přehled karimatek</h1>

{% assign posts = site.posts | where:"categories", "karimatky" %}

{% assign letni = posts | where_exp: "post", "post['R-faktor'] <= 3" %}
{% assign trisezonni = posts | where_exp: "post", "post['R-faktor'] > 3 and post['R-faktor'] <= 5" %}
{% assign zimni = posts | where_exp: "post", "post['R-faktor'] > 5" %}

<h2>Letní karimatky (R-faktor do 3)</h2>
<table>
  <thead>
    <tr>
      <th>Model (odkaz)</th>
      <th>R-faktor</th>
      <th>Hmotnost (g)</th>
      <th>Tloušťka</th>
      <th>Typ</th>
      <th>Pro a proti</th>
      <th>Hodnocení</th>
    </tr>
  </thead>
  <tbody>
    {% for post in letni %}
    <tr>
      <td><a href="{{ post.url }}">{{ post.model }}</a></td>
      <td>{{ post["R-faktor"] }}</td>
      <td>{{ post.vaha }}</td>
      <td>{{ post.tloustka }}</td>
      <td>{{ post.typ }}</td>
      <td>{{ post.pro }}<br>{{ post.proti }}</td>
      <td>{{ post.hodnoceni }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Třísezónní karimatky (R-faktor 3–5)</h2>
<table>
  <thead>
    <tr>
      <th>Model (odkaz)</th>
      <th>R-faktor</th>
      <th>Hmotnost (g)</th>
      <th>Tloušťka</th>
      <th>Typ</th>
      <th>Pro a proti</th>
      <th>Hodnocení</th>
    </tr>
  </thead>
  <tbody>
    {% for post in trisezonni %}
    <tr>
      <td><a href="{{ post.url }}">{{ post.model }}</a></td>
      <td>{{ post["R-faktor"] }}</td>
      <td>{{ post.vaha }}</td>
      <td>{{ post.tloustka }}</td>
      <td>{{ post.typ }}</td>
      <td>{{ post.pro }}<br>{{ post.proti }}</td>
      <td>{{ post.hodnoceni }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Zimní karimatky (R-faktor nad 5)</h2>
<table>
  <thead>
    <tr>
      <th>Model (odkaz)</th>
      <th>R-faktor</th>
      <th>Hmotnost (g)</th>
      <th>Tloušťka</th>
      <th>Typ</th>
      <th>Pro a proti</th>
      <th>Hodnocení</th>
    </tr>
  </thead>
  <tbody>
    {% for post in zimni %}
    <tr>
      <td><a href="{{ post.url }}">{{ post.model }}</a></td>
      <td>{{ post["R-faktor"] }}</td>
      <td>{{ post.vaha }}</td>
      <td>{{ post.tloustka }}</td>
      <td>{{ post.typ }}</td>
      <td>{{ post.pro }}<br>{{ post.proti }}</td>
      <td>{{ post.hodnoceni }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

