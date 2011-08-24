"""URLs for the built-in site search functionality."""

from django.conf.urls.defaults import *


urlpatterns = patterns("watson.views",

    url("^$", "search", name="search"),

)