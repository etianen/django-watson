"""Admin integration for django-watson."""

from __future__ import unicode_literals

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList

from watson.search import SearchEngine, SearchAdapter


admin_search_engine = SearchEngine("admin")


class WatsonSearchChangeList(ChangeList):

    """A change list that takes advantage of django-watson full text search."""

    def get_queryset(self, *args, **kwargs):
        """Creates the query set."""
        # Do the basic searching.
        search_fields = self.search_fields
        self.search_fields = ()
        try:
            qs = super(WatsonSearchChangeList, self).get_queryset(*args, **kwargs)
        finally:
            self.search_fields = search_fields
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

    search_adapter_cls = SearchAdapter

    @property
    def search_context_manager(self):
        """The search context manager used by this SearchAdmin."""
        return self.search_engine._search_context_manager

    def __init__(self, *args, **kwargs):
        """Initializes the search admin."""
        super(SearchAdmin, self).__init__(*args, **kwargs)
        # Check that the search fields are valid.
        for search_field in self.search_fields or ():
            if search_field[0] in ("^", "@", "="):
                raise ValueError("SearchAdmin does not support search fields prefixed with '^', '=' or '@'")
        # Register with the search engine.
        self.register_model_with_watson()
        # Set up revision contexts on key methods, just in case.
        self.add_view = self.search_context_manager.update_index()(self.add_view)
        self.change_view = self.search_context_manager.update_index()(self.change_view)
        self.delete_view = self.search_context_manager.update_index()(self.delete_view)
        self.changelist_view = self.search_context_manager.update_index()(self.changelist_view)

    def register_model_with_watson(self):
        """Registers this admin class' model with django-watson."""
        if not self.search_engine.is_registered(self.model) and self.search_fields:
            self.search_engine.register(
                self.model,
                fields = self.search_fields,
                adapter_cls = self.search_adapter_cls,
                get_live_queryset = lambda self_: None,  # Ensure complete queryset is used in admin.
            )

    def get_changelist(self, request, **kwargs):
        """Returns the ChangeList class for use on the changelist page."""
        return WatsonSearchChangeList
