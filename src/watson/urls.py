"""URLs for the built-in site search functionality."""

try:
    from django.conf.urls import *
except ImportError:  # Django<1.4
    from django.conf.urls.defaults import *


urlpatterns = patterns("watson.views",

    url("^$", "search", name="search"),
    
    url("^json/$", "search_json", name="search_json"),

)