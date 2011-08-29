"""Admin integration for django-watson."""

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList

from watson.registration import SearchEngine


admin_search_engine = SearchEngine("admin")


class WatsonSearchChangelist(ChangeList):

    """A change list that takes advantage of django-watson full text search."""
    
    def __init__(self, request, model, list_display, list_display_links, list_filter, date_hierarchy, search_fields, list_select_related, list_per_page, list_editable, model_admin):
        """Initializes the search engine."""
        # Parse the search fields.
        search_fields = model_admin._get_legacy_search_fields()
        # Initialize the change list.
        super(WatsonSearchChangeList, self).__init__(request, model, list_display, list_display_links, list_filter, date_hierarchy, search_fields, list_select_related, list_per_page, list_editable, model_admin)
        
    def get_query_set(self):
        """Creates the query set."""
        qs = super(WatsonSearchChangeList, self).get_query_set()
        return self.model_admin.search_engine.filter(qs, self.query, ranking=False)


class WatsonSearchAdmin(admin.ModelAdmin):

    """
    A ModelAdmin subclass that provides full-text search integration.
    
    Subclass this admin class and specify a tuple of search_fields for instant
    integration!
    """
    
    search_engine = admin_search_engine
    
    live_filter = False
    
    def __init__(self, *args, **kwargs):
        """Initializes the search admin."""
        super(WatsonSearchAdmin, self).__init__(*args, **kwargs)
        # Register with the search engine.
        self.register_model_with_watson()
        
    def _get_fulltext_search_fields(self):
        """Returns the fields to be indexed using a full text index."""
        return [search_field for search_field in self.search_fields if search_field[0:1] not in ("^", "=", "@")]
    
    def _get_legacy_search_fields(self):
        """Returns the fields to be searched using the standard search method."""
        return [search_field for search_field in self.search_fields if search_field[0:1] in ("^", "=", "@")]
    
    def register_model_with_watson(self):
        """Registers this admin class' model with django-watson."""
        self.search_engine.register(self.model, fields=self._get_fulltext_search_fields(), live_filter=self.live_filter)
    
    def get_changelist(self, request, **kwargs):
        """Returns the ChangeList class for use on the changelist page."""
        return WatsonSearchChangelist