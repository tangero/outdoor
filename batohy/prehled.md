---
layout: default
title: "Přehled batohů"
permalink: /batohy/prehled/
---
<h1>Přehled batohů</h1>

Zde jsem přehledněji rozdělil batohy pode kategorií, čili podle objemu. A přidal jsem k nim nejpodstatnější informace. Užijte si je. 

{% assign batohy_posts = site.posts | where:"categories", "batohy" %}
{%- comment -%}
Definice filtrovaných kolekcí podle objemu a s vyplněným modelem a povinným vyplněním pole objem
{%- endcomment -%}
{% assign valid_posts = batohy_posts | where_exp:"post", "post.objem and post.model" %}

{% assign short_posts = valid_posts | where_exp:"post", "post.objem <= 22" %}
{% assign oneday_posts = valid_posts | where_exp:"post", "post.objem >= 20 and post.objem <= 35" %}
{% assign multiday_posts = valid_posts | where_exp:"post", "post.objem > 35 and post.objem <= 64" %}
{% assign expedition_posts = valid_posts | where_exp:"post", "post.objem >= 65" %}
{% if short_posts.size > 0 %}
<h2>Na krátké výlety</h2>
{% assign sorted_short_posts = short_posts | sort:"hodnoceni" | reverse %}
<table class="table table-striped table-bordered" style="font-size: 12px;">
<thead>
<tr>
<th>Model</th>
<th>Váha</th>
<th>Objem</th>
<th>Materiál</th>
<th>Sex</th>
<th>Pro</th>
<th>Proti</th>
<th>Hodnocení</th>
</tr>
</thead>
<tbody>
{% for post in sorted_short_posts %}
<tr>
<td><a style="font-size: 16px; font-weight: bold;" href="{{ site.baseurl }}{{ post.url }}">{{ post.model }}</a></td>
<td>{{ post.vaha }} g</td>
<td>{{ post.objem }} l</td>
<td>{{ post.material }}</td>
<td>{{ post.sex }}</td>
<td>{{ post.pro }}</td>
<td>{{ post.proti }}</td>
<td>{{ post.hodnoceni }}</td>
</tr>
{% endfor %}
</tbody>
</table>
{% endif %}
{% if oneday_posts.size > 0 %}
<h2>Na jednodenní tůry</h2>
{% assign sorted_oneday_posts = oneday_posts | sort:"hodnoceni" | reverse %}
<table class="table table-striped table-bordered" style="font-size: 12px;">
<thead>
<tr>
<th>Model</th>
<th>Váha</th>
<th>Objem</th>
<th>Materiál</th>
<th>Sex</th>
<th>Pro</th>
<th>Proti</th>
<th>Hodnocení</th>
</tr>
</thead>
<tbody>
{% for post in sorted_oneday_posts %}
<tr>
<td><a style="font-size: 16px; font-weight: bold;" href="{{ site.baseurl }}{{ post.url }}">{{ post.model }}</a></td>
<td>{{ post.vaha }} g</td>
<td>{{ post.objem }} l</td>
<td>{{ post.material }}</td>
<td>{{ post.sex }}</td>
<td>{{ post.pro }}</td>
<td>{{ post.proti }}</td>
<td>{{ post.hodnoceni }}</td>
</tr>
{% endfor %}
</tbody>
</table>
{% endif %}
{% if multiday_posts.size > 0 %}
<h2>Vícedenní tůry</h2>
{% assign sorted_multiday_posts = multiday_posts | sort:"hodnoceni" | reverse %}
<table class="table table-striped table-bordered" style="font-size: 12px;">
<thead>
<tr>
<th>Model</th>
<th>Váha</th>
<th>Objem</th>
<th>Materiál</th>
<th>Sex</th>
<th>Pro</th>
<th>Proti</th>
<th>Hodnocení</th>
</tr>
</thead>
<tbody>
{% for post in sorted_multiday_posts %}
<tr>
<td><a style="font-size: 16px; font-weight: bold;" href="{{ site.baseurl }}{{ post.url }}">{{ post.model }}</a></td>
<td>{{ post.vaha }} g</td>
<td>{{ post.objem }} l</td>
<td>{{ post.material }}</td>
<td>{{ post.sex }}</td>
<td>{{ post.pro }}</td>
<td>{{ post.proti }}</td>
<td>{{ post.hodnoceni }}</td>
</tr>
{% endfor %}
</tbody>
</table>
{% endif %}
{% if expedition_posts.size > 0 %}
<h2>Expediční batohy</h2>
{% assign sorted_expedition_posts = expedition_posts | sort:"hodnoceni" | reverse %}
<table class="table table-striped table-bordered" style="font-size: 12px;">
<thead>
<tr>
<th>Model</th>
<th>Váha</th>
<th>Objem</th>
<th>Materiál</th>
<th>Sex</th>
<th>Pro</th>
<th>Proti</th>
<th>Hodnocení</th>
</tr>
</thead>
<tbody>
{% for post in sorted_expedition_posts %}
<tr>
<td><a style="font-size: 16px; font-weight: bold;" href="{{ site.baseurl }}{{ post.url }}">{{ post.model }}</a></td>
<td>{{ post.vaha }} g</td>
<td>{{ post.objem }} l</td>
<td>{{ post.material }}</td>
<td>{{ post.sex }}</td>
<td>{{ post.pro }}</td>
<td>{{ post.proti }}</td>
<td>{{ post.hodnoceni }}</td>
</tr>
{% endfor %}
</tbody>
</table>
{% endif %}