"""Adapters for registering models with django-watson."""

from threading import local
from contextlib import contextmanager
from functools import wraps

from django.conf import settings
from django.core.signals import request_started, request_finished
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.utils.html import strip_tags
from django.utils.importlib import import_module

from watson.models import SearchEntry, has_int_pk


class SearchAdapter(object):

    """An adapter for performing a full-text search on a model."""
    
    # If set to True, then the search engine will only return
    # models accessible from the default manager of the model. This allows
    # you to limit the results according to some custom publication of your
    # own, at the expense of some search performance.
    live_filter = False
    
    # Use to specify the fields that should be included in the seach.
    fields = None
    
    # Use to exclude fields from the search.
    exclude = None
    
    # Use to specify object properties to be stored in the search index.
    store = None
    
    def __init__(self, model):
        """Initializes the search adapter."""
        self.model = model
    
    def get_meta(self, obj):
        """Returns a dictionary of meta information about the given obj."""
        meta = {
            "title": unicode(obj),
        }
        # Add in the URL.
        if hasattr(obj, "get_absolute_url"):
            meta["url"] = obj.get_absolute_url()
        # Add in the stored fields.    
        if self.store:
            for field_name in self.store:
                value = getattr(obj, field_name)
                if callable(value):
                    value = value()
                meta[field_name] = value
        # Return the meta information.
        return meta
        
    def get_search_text(self, obj):
        """Returns the search text associated with the given obj."""
        # Get the field names to look up.
        if self.fields is None:
            field_names = [field.name for field in self.model._meta.fields if isinstance(field, (models.CharField, models.TextField))]
        else:
            field_names = self.fields
        # Exclude named fields.
        if self.exclude:
            field_names = [field_name for field_name in field_names if field_name not in self.exclude]
        # Create the text.
        text_parts = []
        for field_name in field_names:
            # Resolve the value.
            value = getattr(obj, field_name)
            if callable(value):
                value = value()
            value = unicode(value)
            value = strip_tags(value)
            # Store the value.
            text_parts.append(value)
        # Consolidate the text.
        return u" ".join(text_parts)
        
    def get_weighted_search_text(self, obj):
        """Returns the weighted search text associated with the given obj."""
        return (unicode(obj), self.get_search_text(obj),)


class RegistrationError(Exception):

    """Something went wrong with registering a model with django-watson."""
        

# The registered models.
_registered_models = {}


def is_registered(model):
    """Checks whether the given model is registered with django-watson."""
    global _registered_models
    return model in _registered_models


def register(model, adapter_cls=SearchAdapter):
    """
    Registers the given model with django-watson.
    
    If the given model is already registered with django-watson, a
    RegistrationError will be raised.
    """
    global _registered_models
    # Check for existing registration.
    if is_registered(model):
        raise RegistrationError("{model!r} is already registered with django-watson".format(
            model = model,
        ))
    # Perform the registration.
    adapter_obj = adapter_cls(model)
    _registered_models[model] = adapter_obj
    # Connect to the signalling framework.
    post_save.connect(search_context_manager.post_save_receiver, model)
    pre_delete.connect(search_context_manager.pre_delete_receiver, model)
    
    
def unregister(model):
    """
    Unregisters the given model with django-watson.
    
    If the given model is not registered with django-watson, a RegistrationError
    will be raised.
    """
    global _registered_models
    if not is_registered(model):
        raise RegistrationError("{model!r} not registered with django-watson".format(
            model = model,
        ))
    # Perform the unregistration.
    del _registered_models[model]
    # Disconnect from the signalling framework.
    post_save.disconnect(search_context_manager.post_save_receiver, model)
    pre_delete.connect(search_context_manager.pre_delete_receiver, model)
        
        
def get_registered_models():
    """Returns a sequence of models that have been registered with django-watson."""
    global _registered_models
    return _registered_models.keys()
    
    
def get_adapter(model):
    """Returns the adapter associated with the given model."""
    global _registered_models
    if is_registered(model):
        return _registered_models[model]
    raise RegistrationError("{model!r} not registered with django-watson".format(
        model = model,
    ))
    
    
class SearchContextError(Exception):
    
    """Something went wrong with the search context management."""


class SearchContextManager(local):

    """A thread-local context manager used to manage saving search data."""
    
    def __init__(self):
        """Initializes the search context."""
        self._stack = []
        # Connect to the signalling framework.
        request_started.connect(self.request_started_receiver)
        request_finished.connect(self.request_finished_receiver)
    
    def is_active(self):
        """Checks that this search context is active."""
        return bool(self._stack)
    
    def _assert_active(self):
        """Ensures that the search context is active."""
        if not self.is_active():
            raise SearchContextError("The search context is not active.")
        
    def begin(self):
        """Starts a level in the search context."""
        self._stack.append(set())
    
    def _get_entries_for_obj(self, obj):
        """Returns a queryset of entries associate with the given obj."""
        model = obj.__class__
        content_type = ContentType.objects.get_for_model(model)
        object_id = unicode(obj.pk)
        # Get the basic list of search entries.
        search_entries = SearchEntry.objects.filter(
            content_type = content_type,
        )
        if has_int_pk(model):
            # Do a fast indexed lookup.
            object_id_int = int(obj.pk)
            search_entries = search_entries.filter(
                object_id_int = object_id_int,
            )
        else:
            # Alas, have to do a slow unindexed lookup.
            object_id_int = None
            search_entries = search_entries.filter(
                object_id = object_id,
            )
        return object_id_int, search_entries
    
    def update_obj_index(self, obj):
        """Updates the search index for the given obj."""
        model = obj.__class__
        adapter = get_adapter(model)
        content_type = ContentType.objects.get_for_model(model)
        object_id = unicode(obj.pk)
        # Create the search data.
        meta = adapter.get_meta(obj)
        weighted_search_text = adapter.get_weighted_search_text(obj)
        # Try to get the existing search entry.
        object_id_int, search_entries = self._get_entries_for_obj(obj)
        try:
            search_entry = search_entries.get()
        except SearchEntry.DoesNotExist:
            search_entry = SearchEntry(
                content_type = content_type,
                object_id = object_id,
                object_id_int = object_id_int,
            )
        # Store search meta.
        search_entry.meta = meta
        # Pass on the entry for final processing to the search backend.
        get_backend().save_search_entry(obj, search_entry, weighted_search_text)
    
    def end(self):
        """Ends a level in the search context."""
        self._assert_active()
        # Save all the models.
        objs = self._stack.pop()
        for obj in objs:
            self.update_obj_index(obj)
    
    # Context management.
    
    @contextmanager
    def context(self):
        """Defines a search context for updating registered models."""
        self.begin()
        try:
            yield
        finally:
            self.end()
            
    def update_index(self, func):
        """Marks up a function that should be run in a search context."""
        @wraps(func)
        def do_update_index(*args, **kwargs):
            with self.context():
                return func(*args, **kwargs)
        return do_update_index
    
    # Signalling hooks.
            
    def post_save_receiver(self, instance, **kwargs):
        """Signal handler for when a registered model has been saved."""
        if self.is_active():
            self._stack[-1].add(instance)
            
    def pre_delete_receiver(self, instance, **kwargs):
        """Signal handler for when a registered model has been deleted."""
        _, search_entries = self._get_entries_for_obj(instance)
        search_entries.delete()
        
    def request_started_receiver(self, **kwargs):
        """Signal handler for when the request starts."""
        self.begin()
        
    def request_finished_receiver(self, **kwargs):
        """Signal handler for when the request ends."""
        self.end()
        # Check for any hanging search contexts.
        if self.is_active():
            raise SearchContextError(
                "Request finished with an open search context. All calls to search_context_manager.begin() "
                "should be balanced by a call to search_context_manager.end()."
            )
        
            
# The shared, thread-safe search context manager.
search_context_manager = SearchContextManager()


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