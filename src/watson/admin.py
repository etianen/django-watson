"""Admin integration for django-watson."""

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList

from watson.registration import SearchEngine


admin_search_engine = SearchEngine("admin")


class WatsonSearchChangeList(ChangeList):

    """A change list that takes advantage of django-watson full text search."""
    
    def __init__(self, request, model, list_display, list_display_links, list_filter, date_hierarchy, search_fields, list_select_related, list_per_page, list_editable, model_admin):
        """Initializes the search engine."""
        # Clear the search fields.
        search_fields = ()
        # Initialize the change list.
        super(WatsonSearchChangeList, self).__init__(request, model, list_display, list_display_links, list_filter, date_hierarchy, search_fields, list_select_related, list_per_page, list_editable, model_admin)
        
    def get_query_set(self):
        """Creates the query set."""
        # Do the basic searching.
        qs = super(WatsonSearchChangeList, self).get_query_set()
        # Do the full text searching.
        if self.query.strip():
            qs = self.model_admin.search_engine.filter(qs, self.query, ranking=False)
        return qs


class SearchAdmin(admin.ModelAdmin):

    """
    A ModelAdmin subclass that provides full-text search integration.
    
    Subclass this admin class and specify a tuple of search_fields for instant
    integration!
    """
    
    search_engine = admin_search_engine
    
    def __init__(self, *args, **kwargs):
        """Initializes the search admin."""
        super(SearchAdmin, self).__init__(*args, **kwargs)
        # Check that the search fields are valid.
        for search_field in self.search_fields or ():
            if search_field[0] in ("^", "@", "="):
                raise ValueError("SearchAdmin does not support search fields prefixed with '^', '=' or '@'")
        # Register with the search engine.
        self.register_model_with_watson()
    
    def register_model_with_watson(self):
        """Registers this admin class' model with django-watson."""
        if not self.search_engine.is_registered(self.model):
            self.search_engine.register(self.model, fields=self.search_fields)
    
    def get_changelist(self, request, **kwargs):
        """Returns the ChangeList class for use on the changelist page."""
        return WatsonSearchChangeList