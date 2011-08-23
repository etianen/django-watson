"""Adapters for registering models with django-watson."""

import operator
from threading import local
from contextlib import contextmanager
from functools import wraps
from weakref import WeakValueDictionary

from django.conf import settings
from django.core.signals import request_started, request_finished
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save, pre_delete
from django.utils.html import strip_tags
from django.utils.importlib import import_module

from watson.models import SearchEntry, has_int_pk


class SearchAdapterError(Exception):

    """Something went wrong with a search adapter."""


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
    exclude = ()
    
    # Use to specify object properties to be stored in the search index.
    store = ()
    
    def __init__(self, model):
        """Initializes the search adapter."""
        self.model = model
    
    def _resolve_field(self, obj, name):
        """Resolves the content of the given model field."""
        # Get the attribute.
        if hasattr(obj, name):
            value = getattr(obj, name)
        elif hasattr(self, name):
            value = getattr(self, name)
        else:
            raise SearchAdapterError("Could not find a property called {name!r} on either {obj!r} or {search_adapter!r}".format(
                name = name,
                obj = obj,
                search_adapter = self,
            ))
        # Check for callables.
        if callable(value):
            value = value()
        # Resolution complete!
        return value
    
    def get_title(self, obj):
        """Returns the search title for the given obj."""
        return unicode(obj)
        
    def get_description(self, obj):
        """Returns the search description for the given obj."""
        return u""
        
    def get_content(self, obj):
        """Returns the search content for the given obj."""
        # Get the field names to look up.
        if self.fields is None:
            field_names = (field.name for field in self.model._meta.fields if isinstance(field, (models.CharField, models.TextField)))
        else:
            field_names = self.fields
        # Exclude named fields.
        field_names = (field_name for field_name in field_names if field_name not in self.exclude)
        # Create the text.
        return u" ".join(
            strip_tags(self._resolve_field(obj, field_name))
            for field_name in field_names
        )        
    
    def get_url(self, obj):
        """Return the URL of the given obj."""
        if hasattr(obj, "get_absolute_url"):
            return obj.get_absolute_url()
        return u""
    
    def get_meta(self, obj):
        """Returns a dictionary of meta information about the given obj."""
        return dict(
            (field_name, self._resolve_field(field_name))
            for field_name in self.store
        )


class SearchEngineError(Exception):

    """Something went wrong with a search engine."""


class RegistrationError(SearchEngineError):

    """Something went wrong when registering a model with a search engine."""
    
    
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
    
    def add_to_context(self, engine, obj):
        """Adds an object to the current context, if active."""
        if self.is_active():
            self._stack[-1].add((engine, obj))
    
    def end(self):
        """Ends a level in the search context."""
        self._assert_active()
        # Save all the models.
        tasks = self._stack.pop()
        for engine, obj in tasks:
            engine.update_obj_index(obj)
    
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


class SearchEngine(object):

    """A search engine capable of performing multi-table searches."""
    
    _created_engines = WeakValueDictionary()
    
    @classmethod
    def get_created_engines(cls):
        """Returns all created search engines."""
        return list(cls._created_engines.items())
    
    def __init__(self, engine_slug, search_context_manager=search_context_manager):
        """Initializes the search engine."""
        # Check the slug is unique for this project.
        if engine_slug in SearchEngine._created_engines:
            raise SearchEngineError("A search engine has already been created with the slug {engine_slug!r}".format(
                engine_slug = engine_slug,
            ))
        # Initialize thie engine.
        self._registered_models = {}
        self._engine_slug = engine_slug
        # Store the search context.
        self._search_context_manager = search_context_manager
        self.context = search_context_manager.context
        self.update_index = search_context_manager.update_index
        # Store a reference to this engine.
        self.__class__._created_engines[engine_slug] = self

    def is_registered(self, model):
        """Checks whether the given model is registered with this search engine."""
        return model in self._registered_models

    def register(self, model, adapter_cls=SearchAdapter, live_filter=None, fields=None, exclude=None, store=None):
        """
        Registers the given model with this search engine.
        
        If the given model is already registered with this search engine, a
        RegistrationError will be raised.
        """
        # Check for existing registration.
        if self.is_registered(model):
            raise RegistrationError("{model!r} is already registered with this search engine".format(
                model = model,
            ))
        # Perform any customization.
        field_overrides = dict(
            (field_name, field_value)
            for field_name, field_value
            in (
                ("live_filter", live_filter),
                ("fields", fields),
                ("exclude", exclude),
                ("store", store),
            )
            if field_value is not None
        )
        if field_overrides:
            adapter_cls = type(adapter_cls.__name__ + "Custom", (adapter_cls,), field_overrides)
        # Perform the registration.
        adapter_obj = adapter_cls(model)
        self._registered_models[model] = adapter_obj
        # Add in a generic relation, if not exists.
        if not hasattr(model, "searchentry_set"):
            if has_int_pk(model):
                object_id_field = "object_id_int"
            else:
                object_id_field = "object_id"
            generic_relation = generic.GenericRelation(
                SearchEntry,
                object_id_field = object_id_field,
            )
            model.searchentry_set = generic_relation
            generic_relation.contribute_to_class(model, "searchentry_set")
        # Connect to the signalling framework.
        post_save.connect(self.post_save_receiver, model)
        pre_delete.connect(self.pre_delete_receiver, model)
    
    def unregister(self, model):
        """
        Unregisters the given model with this search engine.
        
        If the given model is not registered with this search engine, a RegistrationError
        will be raised.
        """
        if not self.is_registered(model):
            raise RegistrationError("{model!r} is not registered with this search engine".format(
                model = model,
            ))
        # Perform the unregistration.
        del self._registered_models[model]
        # Disconnect from the signalling framework.
        post_save.disconnect(self.post_save_receiver, model)
        pre_delete.connect(self.pre_delete_receiver, model)
        
    def get_registered_models(self):
        """Returns a sequence of models that have been registered with this search engine."""
        return self._registered_models.keys()
    
    def get_adapter(self, model):
        """Returns the adapter associated with the given model."""
        if self.is_registered(model):
            return self._registered_models[model]
        raise RegistrationError("{model!r} is not registered with this search engine".format(
            model = model,
        ))
    
    def _get_entries_for_obj(self, obj):
        """Returns a queryset of entries associate with the given obj."""
        model = obj.__class__
        content_type = ContentType.objects.get_for_model(model)
        object_id = unicode(obj.pk)
        # Get the basic list of search entries.
        search_entries = SearchEntry.objects.filter(
            content_type = content_type,
            engine_slug = self._engine_slug,
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
        adapter = self.get_adapter(model)
        content_type = ContentType.objects.get_for_model(model)
        object_id = unicode(obj.pk)
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
        # Store data.
        search_entry.engine_slug = self._engine_slug
        search_entry.title = adapter.get_title(obj)
        search_entry.description = adapter.get_description(obj)
        search_entry.content = adapter.get_content(obj)
        search_entry.url = adapter.get_url(obj)
        search_entry.meta = adapter.get_meta(obj)
        # Pass on the entry for final processing to the search backend.
        get_backend().save_search_entry(search_entry, obj, adapter)
        
    # Signalling hooks.
            
    def post_save_receiver(self, instance, **kwargs):
        """Signal handler for when a registered model has been saved."""
        if self._search_context_manager.is_active():
            self._search_context_manager.add_to_context(self, instance)
            
    def pre_delete_receiver(self, instance, **kwargs):
        """Signal handler for when a registered model has been deleted."""
        _, search_entries = self._get_entries_for_obj(instance)
        search_entries.delete()
        
    # Searching.
    
    def search(self, search_text, models=None, exclude=None):
        """Performs a search using the given text, returning a queryset of SearchEntry."""
        queryset = SearchEntry.objects.filter(
            engine_slug = self._engine_slug,
        )
        # Add in a model limiter.
        allowed_models = models or self.get_registered_models()
        if exclude:
            allowed_models = [model for model in allowed_models if not model in exclude]
        # Perform any live filters.
        live_subqueries = []
        for model in allowed_models:
            content_type = ContentType.objects.get_for_model(model)
            adapter = self.get_adapter(model)
            if adapter.live_filter:
                needs_live_subquery = True
                live_pks = model._default_manager.all().values_list("pk", flat=True)
                if has_int_pk(model):
                    # We can do this as an in-database join.
                    live_subquery = Q(
                        content_type = content_type,
                        object_id_int__in = live_pks,
                    )
                else:
                    # We have to do this as two separate queries. Oh well.
                    live_subquery = Q(
                        content_type = content_type,
                        object_id__in = [unicode(pk) for pk in live_pks],
                    )
            else:
                live_subquery = Q(
                    content_type = content_type,
                )
            live_subqueries.append(live_subquery)
        live_subquery = reduce(operator.or_, live_subqueries)
        queryset = queryset.filter(live_subquery)
        # Perform the backend-specific full text match.
        queryset = get_backend().do_search(queryset, search_text)
        return queryset
        
    def filter(self, queryset, search_text):
        """
        Filters the given model or queryset using the given text, returning the
        modified queryset.
        """
        # If the queryset is a model, get all of them.
        if issubclass(queryset, models.Model):
            queryset = queryset._default_manager.all()
        # Do the filter.
        queryset = get_backend().do_filter(queryset, search_text)
        return queryset


# The default search engine.
default_search_engine = SearchEngine("default")


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