---
layout: default
title: "Přehled bot"
permalink: /boty/prehled/
---

<h1>Přehled bot</h1>

{% assign boty_posts = site.posts | where:"categories", "boty" %}
{% assign valid_posts = boty_posts | where_exp:"post", "post.tvar and post.model" %}
{% assign posts_by_tvar = valid_posts | group_by:"tvar" %}

{% for group in posts_by_tvar %}
<h2>{{ group.name | capitalize }}</h2>
<table class="table table-striped table-bordered" style="font-size: 12px;">
  <thead>
    <tr>
      <th>Model</th>
      <th>Váha</th>
      <th>Tvar</th>
      <th>Materiál</th>
      <th>Pro</th>
      <th>Proti</th>
      <th>Hodnocení</th>
    </tr>
  </thead>
  <tbody>
    {% for post in group.items %}
    <tr>
      <td><a style="font-size: 16px; font-weight: bold;" href="{{ site.baseurl }}{{ post.url }}">{{ post.model }}</a></td>
      <td>{{ post.vaha }} g</td>
      <td>{{ post.tvar }}</td>
      <td>{{ post.material }}</td>
      <td>{{ post.pro }}</td>
      <td>{{ post.proti }}</td>
      <td>{{ post.hodnoceni }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endfor %}