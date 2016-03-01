"""Adapters for registering models with django-watson."""

from __future__ import unicode_literals

import sys, json
from itertools import chain, islice
from threading import local
from functools import wraps
from weakref import WeakValueDictionary

from django.conf import settings
from django.core.signals import request_finished
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.models.signals import post_save, pre_delete
from django.utils.encoding import force_text
from django.utils.html import strip_tags
from django.core.serializers.json import DjangoJSONEncoder
try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module


class SearchAdapterError(Exception):

    """Something went wrong with a search adapter."""


class SearchAdapter(object):

    """An adapter for performing a full-text search on a model."""

    # Use to specify the fields that should be included in the search.
    fields = ()

    # Use to exclude fields from the search.
    exclude = ()

    # Use to specify object properties to be stored in the search index.
    store = ()

    def __init__(self, model):
        """Initializes the search adapter."""
        self.model = model

    def _resolve_field(self, obj, name):
        """Resolves the content of the given model field."""
        name_parts = name.split("__", 1)
        prefix = name_parts[0]
        # If we're at the end of the resolve chain, return.
        if obj is None:
            return ""
        # Try to get the attribute from the object.
        try:
            value = getattr(obj, prefix)
        except ObjectDoesNotExist:
            return ""
        except AttributeError:
            # Try to get the attribute from the search adapter.
            try:
                value = getattr(self, prefix)
            except AttributeError:
                raise SearchAdapterError("Could not find a property called {name!r} on either {obj!r} or {search_adapter!r}".format(
                    name = prefix,
                    obj = obj,
                    search_adapter = self,
                ))
            else:
                # Run the attribute on the search adapter, if it's callable.
                if not isinstance(value, (QuerySet, models.Manager)):
                    if callable(value):
                        value = value(obj)
        else:
            # Run the attribute on the object, if it's callable.
            if not isinstance(value, (QuerySet, models.Manager)):
                if callable(value):
                    value = value()
        # Look up recursive fields.
        if len(name_parts) == 2:
            if isinstance(value, (QuerySet, models.Manager)):
                return " ".join(force_text(self._resolve_field(obj, name_parts[1])) for obj in value.all())
            return self._resolve_field(value, name_parts[1])
        # Resolve querysets.
        if isinstance(value, (QuerySet, models.Manager)):
            value = " ".join(force_text(related) for related in value.all())
        # Resolution complete!
        return value

    def prepare_content(self, content):
        """Sanitizes the given content string for better parsing by the search engine."""
        # Strip out HTML tags.
        content = strip_tags(content)
        return content

    def get_title(self, obj):
        """
        Returns the title of this search result. This is given high priority in search result ranking.

        You can access the title of the search entry as `entry.title` in your search results.

        The default implementation returns `force_text(obj)` truncated to 1000 characters.
        """
        return force_text(obj)[:1000]

    def get_description(self, obj):
        """
        Returns the description of this search result. This is given medium priority in search result ranking.

        You can access the description of the search entry as `entry.description` in your search results. Since
        this should contains a short description of the search entry, it's excellent for providing a summary
        in your search results.

        The default implementation returns `""`.
        """
        return ""

    def get_content(self, obj):
        """
        Returns the content of this search result. This is given low priority in search result ranking.

        You can access the content of the search entry as `entry.content` in your search results, although
        this field generally contains a big mess of search data so is less suitable for frontend display.

        The default implementation returns all the registered fields in your model joined together.
        """
        # Get the field names to look up.
        field_names = self.fields or (field.name for field in self.model._meta.fields if isinstance(field, (models.CharField, models.TextField)))
        # Exclude named fields.
        field_names = (field_name for field_name in field_names if field_name not in self.exclude)
        # Create the text.
        return self.prepare_content(" ".join(
            force_text(self._resolve_field(obj, field_name))
            for field_name in field_names
        ))

    def get_url(self, obj):
        """Return the URL of the given obj."""
        if hasattr(obj, "get_absolute_url"):
            return obj.get_absolute_url()
        return ""

    def get_meta(self, obj):
        """Returns a dictionary of meta information about the given obj."""
        return dict(
            (field_name, self._resolve_field(obj, field_name))
            for field_name in self.store
        )

    def serialize_meta(self, obj):
        """serialise meta ready to be saved in "meta_encoded"."""
        meta_obj = self.get_meta(obj)
        return json.dumps(meta_obj, cls=DjangoJSONEncoder)

    def deserialize_meta(self, meta_encoded):
        """
        deserialize the encoded meta string for use in views etc., this is
        used by SearchEntry's _deserialize_meta method to create the "meta" property
        """
        return json.loads(meta_encoded)

    def get_live_queryset(self):
        """
        Returns the queryset of objects that should be considered live.

        If this returns None, then all objects should be considered live, which is more efficient.
        """
        return None


class SearchEngineError(Exception):

    """Something went wrong with a search engine."""


class RegistrationError(SearchEngineError):

    """Something went wrong when registering a model with a search engine."""


class SearchContextError(Exception):

    """Something went wrong with the search context management."""


def _bulk_save_search_entries(search_entries, batch_size=100):
    """Creates the given search entry data in the most efficient way possible."""
    from watson.models import SearchEntry
    if search_entries:
        search_entries = iter(search_entries)
        while True:
            search_entry_batch = list(islice(search_entries, 0, batch_size))
            if not search_entry_batch:
                break
            SearchEntry.objects.bulk_create(search_entry_batch)


class SearchContextManager(local):

    """A thread-local context manager used to manage saving search data."""

    def __init__(self):
        """Initializes the search context."""
        self._stack = []
        # Connect to the signalling framework.
        request_finished.connect(self._request_finished_receiver)

    def is_active(self):
        """Checks that this search context is active."""
        return bool(self._stack)

    def _assert_active(self):
        """Ensures that the search context is active."""
        if not self.is_active():
            raise SearchContextError("The search context is not active.")

    def start(self):
        """Starts a level in the search context."""
        self._stack.append((set(), False))

    def add_to_context(self, engine, obj):
        """Adds an object to the current context, if active."""
        self._assert_active()
        objects, _ = self._stack[-1]
        objects.add((engine, obj))

    def invalidate(self):
        """Marks this search context as broken, so should not be commited."""
        self._assert_active()
        objects, _ = self._stack[-1]
        self._stack[-1] = (objects, True)

    def is_invalid(self):
        """Checks whether this search context is invalid."""
        self._assert_active()
        _, is_invalid = self._stack[-1]
        return is_invalid

    def end(self):
        """Ends a level in the search context."""
        self._assert_active()
        # Save all the models.
        tasks, is_invalid = self._stack.pop()
        if not is_invalid:
            _bulk_save_search_entries(list(chain.from_iterable(engine._update_obj_index_iter(obj) for engine, obj in tasks)))

    # Context management.

    def update_index(self):
        """
        Marks up a block of code as requiring the search indexes to be updated.

        The returned context manager can also be used as a decorator.
        """
        return SearchContext(self)

    def skip_index_update(self):
        """
        Marks up a block of code as not requiring a search index update.

        Like update_index, the returned context manager can also be used as a decorator.
        """
        return SkipSearchContext(self)

    # Signalling hooks.

    def _request_finished_receiver(self, **kwargs):
        """
        Called at the end of a request, ensuring that any open contexts
        are closed. Not closing all active contexts can cause memory leaks
        and weird behaviour.
        """
        while self.is_active():
            self.end()


class SearchContext(object):

    """An individual context for a search index update."""

    def __init__(self, context_manager):
        """Initializes the search index context."""
        self._context_manager = context_manager

    def __enter__(self):
        """Enters a block of search index management."""
        self._context_manager.start()

    def __exit__(self, exc_type, exc_value, traceback):
        """Leaves a block of search index management."""
        try:
            if exc_type is not None:
                self._context_manager.invalidate()
        finally:
            self._context_manager.end()

    def __call__(self, func):
        """Allows this search index context to be used as a decorator."""
        @wraps(func)
        def do_search_context(*args, **kwargs):
            self.__enter__()
            exception = False
            try:
                return func(*args, **kwargs)
            except:
                exception = True
                if not self.__exit__(*sys.exc_info()):
                    raise
            finally:
                if not exception:
                    self.__exit__(None, None, None)
        return do_search_context


class SkipSearchContext(SearchContext):

    """A context that skips over index updating"""

    def __exit__(self, exc_type, exc_value, traceback):
        """Mark it as invalid and exit"""
        try:
            self._context_manager.invalidate()
        finally:
            self._context_manager.end()


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
        # Store a reference to this engine.
        self.__class__._created_engines[engine_slug] = self

    def is_registered(self, model):
        """Checks whether the given model is registered with this search engine."""
        return model in self._registered_models

    def register(self, model, adapter_cls=SearchAdapter, **field_overrides):
        """
        Registers the given model with this search engine.

        If the given model is already registered with this search engine, a
        RegistrationError will be raised.
        """
        # Add in custom live filters.
        if isinstance(model, QuerySet):
            live_queryset = model
            model = model.model
            field_overrides["get_live_queryset"] = lambda self_: live_queryset.all()
        # Check for existing registration.
        if self.is_registered(model):
            raise RegistrationError("{model!r} is already registered with this search engine".format(
                model = model,
            ))
        # Perform any customization.
        if field_overrides:
            # Conversion to str is needed because Python 2 doesn't accept unicode for class name
            adapter_cls = type(str("Custom") + adapter_cls.__name__, (adapter_cls,), field_overrides)
        # Perform the registration.
        adapter_obj = adapter_cls(model)
        self._registered_models[model] = adapter_obj
        # Connect to the signalling framework.
        post_save.connect(self._post_save_receiver, model)
        pre_delete.connect(self._pre_delete_receiver, model)

    def unregister(self, model):
        """
        Unregisters the given model with this search engine.

        If the given model is not registered with this search engine, a RegistrationError
        will be raised.
        """
        # Add in custom live filters.
        if isinstance(model, QuerySet):
            model = model.model
        # Check for registration.
        if not self.is_registered(model):
            raise RegistrationError("{model!r} is not registered with this search engine".format(
                model = model,
            ))
        # Perform the unregistration.
        del self._registered_models[model]
        # Disconnect from the signalling framework.
        post_save.disconnect(self._post_save_receiver, model)
        pre_delete.disconnect(self._pre_delete_receiver, model)

    def get_registered_models(self):
        """Returns a sequence of models that have been registered with this search engine."""
        return list(self._registered_models.keys())

    def get_adapter(self, model):
        """Returns the adapter associated with the given model."""
        if self.is_registered(model):
            return self._registered_models[model]
        raise RegistrationError("{model!r} is not registered with this search engine".format(
            model = model,
        ))

    def _get_entries_for_obj(self, obj):
        """Returns a queryset of entries associate with the given obj."""
        from django.contrib.contenttypes.models import ContentType
        from watson.models import SearchEntry, has_int_pk
        model = obj.__class__
        content_type = ContentType.objects.get_for_model(model)
        object_id = force_text(obj.pk)
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

    def _update_obj_index_iter(self, obj):
        """Either updates the given object index, or yields an unsaved search entry."""
        from django.contrib.contenttypes.models import ContentType
        from watson.models import SearchEntry
        model = obj.__class__
        adapter = self.get_adapter(model)
        content_type = ContentType.objects.get_for_model(model)
        object_id = force_text(obj.pk)
        # Create the search entry data.
        search_entry_data = {
            "engine_slug": self._engine_slug,
            "title": adapter.get_title(obj),
            "description": adapter.get_description(obj),
            "content": adapter.get_content(obj),
            "url": adapter.get_url(obj),
            "meta_encoded": adapter.serialize_meta(obj),
        }
        # Try to get the existing search entry.
        object_id_int, search_entries = self._get_entries_for_obj(obj)
        # Attempt to update the search entries.
        update_count = search_entries.update(**search_entry_data)
        if update_count == 0:
            # This is the first time the entry was created.
            search_entry_data.update((
                ("content_type", content_type),
                ("object_id", object_id),
                ("object_id_int", object_id_int),
            ))
            yield SearchEntry(**search_entry_data)
        elif update_count > 1:
            # Oh no! Somehow we've got duplicated search entries!
            search_entries.exclude(id=search_entries[0].id).delete()

    def update_obj_index(self, obj):
        """Updates the search index for the given obj."""
        _bulk_save_search_entries(list(self._update_obj_index_iter(obj)))

    # Signalling hooks.

    def _post_save_receiver(self, instance, **kwargs):
        """Signal handler for when a registered model has been saved."""
        if self._search_context_manager.is_active():
            self._search_context_manager.add_to_context(self, instance)
        else:
            self.update_obj_index(instance)

    def _pre_delete_receiver(self, instance, **kwargs):
        """Signal handler for when a registered model has been deleted."""
        _, search_entries = self._get_entries_for_obj(instance)
        search_entries.delete()

    # Searching.

    def _create_model_filter(self, models):
        """Creates a filter for the given model/queryset list."""
        from django.contrib.contenttypes.models import ContentType
        from watson.models import has_int_pk
        filters = Q()
        for model in models:
            filter = Q()
            # Process querysets.
            if isinstance(model, QuerySet):
                sub_queryset = model
                model = model.model
                queryset = sub_queryset.values_list("pk", flat=True)
                if has_int_pk(model):
                    filter &= Q(
                        object_id_int__in = queryset,
                    )
                else:
                    live_ids = list(queryset)
                    if live_ids:
                        filter &= Q(
                            object_id__in = live_ids,
                        )
                    else:
                        # HACK: There is a bug in Django (https://code.djangoproject.com/ticket/15145) that messes up __in queries when the iterable is empty.
                        # This bit of nonsense ensures that this aspect of the query will be impossible to fulfill.
                        filter &= Q(
                            content_type = ContentType.objects.get_for_model(model).id + 1,
                        )
            # Add the model to the filter.
            content_type = ContentType.objects.get_for_model(model)
            filter &= Q(
                content_type = content_type,
            )
            # Combine with the other filters.
            filters |= filter
        return filters

    def _get_included_models(self, models):
        """Returns an iterable of models and querysets that should be included in the search query."""
        for model in models or self.get_registered_models():
            if isinstance(model, QuerySet):
                yield model
            else:
                adaptor = self.get_adapter(model)
                queryset = adaptor.get_live_queryset()
                if queryset is None:
                    yield model
                else:
                    yield queryset.all()

    def search(self, search_text, models=(), exclude=(), ranking=True, backend_name=None):
        """Performs a search using the given text, returning a queryset of SearchEntry."""
        from watson.models import SearchEntry
        # Check for blank search text.
        search_text = search_text.strip()
        if not search_text:
            return SearchEntry.objects.none()
        # Get the initial queryset.
        queryset = SearchEntry.objects.filter(
            engine_slug = self._engine_slug,
        )
        # Process the allowed models.
        queryset = queryset.filter(
            self._create_model_filter(self._get_included_models(models))
        ).exclude(
            self._create_model_filter(exclude)
        )
        # Perform the backend-specific full text match.
        backend = get_backend(backend_name=backend_name)
        queryset = backend.do_search(self._engine_slug, queryset, search_text)
        # Perform the backend-specific full-text ranking.
        if ranking:
            queryset = backend.do_search_ranking(self._engine_slug, queryset, search_text)
        # Return the complete queryset.
        return queryset

    def filter(self, queryset, search_text, ranking=True, backend_name=None):
        """
        Filters the given model or queryset using the given text, returning the
        modified queryset.
        """
        # If the queryset is a model, get all of them.
        if isinstance(queryset, type) and issubclass(queryset, models.Model):
            queryset = queryset._default_manager.all()
        # Check for blank search text.
        search_text = search_text.strip()
        if not search_text:
            return queryset
        # Perform the backend-specific full text match.
        backend = get_backend(backend_name=backend_name)
        queryset = backend.do_filter(self._engine_slug, queryset, search_text)
        # Perform the backend-specific full-text ranking.
        if ranking:
            queryset = backend.do_filter_ranking(self._engine_slug, queryset, search_text)
        # Return the complete queryset.
        return queryset


# The default search engine.
default_search_engine = SearchEngine("default")


# The cache for the initialized backend.
_backends_cache = {}


def get_backend(backend_name=None):
    """Initializes and returns the search backend."""
    global _backends_cache
    # Try to use the cached backend.
    if backend_name in _backends_cache:
        return _backends_cache[backend_name]
    # Load the backend class.
    if not backend_name:
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
    _backends_cache[backend_name] = backend
    return backend


# The main search methods.
search = default_search_engine.search
filter = default_search_engine.filter


# Easy registration.
register = default_search_engine.register
unregister = default_search_engine.unregister
is_registered = default_search_engine.is_registered
get_registered_models = default_search_engine.get_registered_models
get_adapter = default_search_engine.get_adapter


# Easy context management.
update_index = search_context_manager.update_index
skip_index_update = search_context_manager.skip_index_update
