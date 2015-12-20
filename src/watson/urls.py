"""URLs for the built-in site search functionality."""

from __future__ import unicode_literals

from django.conf.urls import url
from . import views

urlpatterns = [

    url("^$", views.search, name="search"),
    
    url("^json/$", views.search_json, name="search_json"),

]
