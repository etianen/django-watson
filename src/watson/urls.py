"""URLs for the built-in site search functionality."""

from django.conf.urls.defaults import *


urlpatterns = patterns("watson.views",

    url("^$", "search", name="search"),
    
    url("^json/$", "search_json", name="search_json"),

)