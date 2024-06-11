---
layout: archive
title: "Photo Album"
permalink: /photo/
author_profile: true
---

{% include base_path %}


{% for post in site.photo %}
  {% include archive-single.html %}
{% endfor %}

