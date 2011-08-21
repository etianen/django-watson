"""Search backends used by django-watson."""

from abc import ABCMeta, abstractmethod

from django.conf import settings
from django.utils.importlib import import_module
from django.core.exceptions import ImproperlyConfigured
from django.db import models, connection

from watson.models import SearchEntry


class SearchBackend(object):

    """Base class for all search backends."""

    __metaclass__ = ABCMeta
    
    @abstractmethod
    def do_install(self):
        """Generates the SQL needed to install django-watson."""
        raise NotImplementedError
        
    @abstractmethod
    def do_search(self, queryset, text):
        """Filters the given queryset according the the search logic for this backend."""
        raise NotImplementedError
    
    @abstractmethod
    def save_search_entry(self, obj, search_entry, weighted_search_text):
        """Saves the given search entry in the database."""
        raise NotImplementedError
        
    def search(self, text):
        """Performs a search using the given text, returning a queryset of SearchEntry."""
        queryset = SearchEntry.objects.all()
        queryset = self.do_search(queryset, text)
        return queryset
        
        
class PostgresSearchBackend(SearchBackend):

    """A search backend that uses native PostgreSQL full text indices."""
    
    def do_install(self):
        """Generates the PostgreSQL specific SQL code to install django-watson."""
        
        
        
class DumbSearchBackend(SearchBackend):

    """
    A search backend that uses a straight containment search to find results.
    
    This is fine for debugging locally, but rubbish for production.
    """
    
    def do_install(self):
        """Just create a dumb text column."""
        from south.db import db
        db.add_column(SearchEntry._meta.db_table, "search_text", models.TextField(default=""), keep_default=False)
        
    def do_search(self, queryset, text):
        """Performs the dumb search."""
        return queryset.filter(search_text__icontains=text)
        
    def save_search_entry(self, obj, search_entry, weighted_search_text):
        """Saves the search entry."""
        # Consolidate the search entry data.
        search_text = u" ".join(weighted_search_text)
        data = {
            "object_id": search_entry.object_id,
            "object_id_int": search_entry.object_id_int,
            "content_type_id": search_entry.content_type_id,
            "meta_encoded": search_entry.meta_encoded,
            "search_text": search_text,
        }
        # Hijack the save with raw SQL!
        if search_entry.pk is None:
            # Perform a raw insert.
            sql_str = "INSERT INTO %s (%s, %s, %s, %s, %s) VALUES (%s, %s, %s, %s, %s);"
            sql_params = list(data.keys()) + list(data.values())
        else:
            # Perform a raw update.
            sql_str = "UPDATE %s SET %s = %s, %s = %s, %s = %s, %s = %s, %s = %s WHERE %s = %s"
            sql_params = list(data.items()) + [("id", search_entry.id)]
        # Perform the query.
        connection.cursor().execute(sql_str, sql_params)
        
        
class AdaptiveSearchBackend(SearchBackend):

    """
    A search backend that guesses the correct search backend based on the
    DATABASES["default"] settings.
    """
    
    def __new__(cls):
        """Guess the correct search backend and initialize it."""
        return DumbSearchBackend()  # TODO: remove
        database_engine = settings.DATABASES["default"]["ENGINE"]
        if database_engine.endswith("postgresql_psycopg2") or database_engine.endswith("postgresql"):
            return PostgresSearchBackend()
        else:
            return DumbSearchBackend()
            

# The cache for the initialized backend.
_backend_cache = None


def get_backend():
    """Initializes and returns the search backend."""
    global _backend_cache
    # Try to use the cached backend.
    if _backend_cache is not None:
        return _backend_cache
    # Load the backend class.
    backend_name = getattr(settings, "WATSON_BACKEND", "watson.backends.AdaptiveSearchBackend")
    backend_module_name, backend_cls_name = backend_name.rsplit(".", 1)
    backend_module = import_module(backend_module_name)
    try:
        backend_cls = getattr(backend_module, backend_cls_name)
    except AttributeError:
        raise ImproperlyConfigured("Could not find a class named {backend_module_name!r} in {backend_cls_name!r}".format(
            backend_module_name = backend_module_name,
            backend_cls_name = backend_cls_name,
        ))
    # Initialize the backend.
    backend = backend_cls()
    _backend_cache = backend
    return backend