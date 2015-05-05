from django.contrib import admin

import watson
from test_watson.models import WatsonTestModel1


class WatsonTestModel1Admin(watson.SearchAdmin):

    search_fields = ("title", "description", "content",)
    
    list_display = ("title",)
    
    
admin.site.register(WatsonTestModel1, WatsonTestModel1Admin)
