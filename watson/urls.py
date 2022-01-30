"""URLs for the built-in site search functionality."""

from __future__ import unicode_literals

from django.urls import re_path

from watson.views import search, search_json

app_name = 'watson'
urlpatterns = [

    re_path("^$", search, name="search"),
    re_path("^json/$", search_json, name="search_json"),

]
