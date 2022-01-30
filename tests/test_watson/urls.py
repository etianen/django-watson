from django.contrib import admin
from django.urls import include, re_path

urlpatterns = [

    re_path("^simple/", include("watson.urls")),

    re_path("^custom/", include("watson.urls"), kwargs={
        "query_param": "fooo",
        "empty_query_redirect": "/simple/",
        "extra_context": {
            "foo": "bar",
            "foo2": lambda: "bar2",
        },
        "paginate_by": 10,
    }),

    re_path("^admin/", admin.site.urls),
]
