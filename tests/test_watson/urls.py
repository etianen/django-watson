from django.conf.urls import url, include
from django.contrib import admin


urlpatterns = [

    url("^simple/", include("watson.urls")),

    url("^custom/", include("watson.urls"), kwargs={
        "query_param": "fooo",
        "empty_query_redirect": "/simple/",
        "extra_context": {
            "foo": "bar",
            "foo2": lambda: "bar2",
        },
        "paginate_by": 10,
    }),

    url("^admin/", admin.site.urls),
]
