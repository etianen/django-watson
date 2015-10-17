"""URLs for the built-in site search functionality."""

from __future__ import unicode_literals

from django.conf.urls import url, patterns


urlpatterns = patterns("watson.views",

    url("^$", "search", name="search", kwargs={"paginate_by": 10}), # paginate_by is used to paginate the results.
    
    url("^json/$", "search_json", name="search_json"),

)
