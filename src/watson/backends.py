"""Search backends used by django-watson."""

from abc import ABCMeta, abstractmethod

from django.conf import settings
from django.utils.importlib import import_module
from django.core.exceptions import ImproperlyConfigured


class SearchBackend(object):

    """Base class for all search backends."""

    __metaclass__ = ABCMeta
    
    @abstractmethod
    def get_install_sql(self):
        """Generates the SQL needed to install django-watson."""
        raise NotImplementedError
        
        
class PostgresSearchBackend(SearchBackend):

    """A search backend that uses native PostgreSQL full text indices."""
    
    def get_install_sql(self):
        """Generates the PostgreSQL specific SQL code to install django-watson."""
        return ""
        
        
class DumbSearchBackend(SearchBackend):

    """
    A search backend that uses a straight containment search to find results.
    
    This is fine for debugging locally, but rubbish for production.
    """
    
    def get_install_sql(self):
        """There's no installation SQL for this backend!"""
        return ""
        
        
class AdaptiveSearchBackend(SearchBackend):

    """
    A search backend that guesses the correct search backend based on the
    DATABASES["default"] settings.
    """
    
    def __new__(cls):
        """Guess the correct search backend and initialize it."""
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