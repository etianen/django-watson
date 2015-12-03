from django.contrib import admin

from watson.admin import SearchAdmin
from test_watson.models import WatsonTestModel1


class WatsonTestModel1Admin(SearchAdmin):

    search_fields = ("title", "description", "content",)

    list_display = ("title",)


admin.site.register(WatsonTestModel1, WatsonTestModel1Admin)
