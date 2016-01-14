"""URLs for the built-in site search functionality."""

from __future__ import unicode_literals

from django.conf.urls import url, patterns

from watson.views import search, search_json

urlpatterns = [

    url("^$", search, name="search"),
    
    url("^json/$", search_json, name="search_json"),

]
