"""Rebuilds the database indices needed by django-watson."""

from __future__ import unicode_literals, print_function

from django.core.management.base import BaseCommand, CommandError
from django.db.models import get_model
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from watson.registration import SearchEngine, _bulk_save_search_entries
from watson.models import SearchEntry


# Sets up registration for django-watson's admin integration.
admin.autodiscover()


def rebuild_for_model(model_, search_engine_, engine_slug_, verbosity_):
    '''rebuilds index for a model'''

    local_refreshed_model_count = [0]  # HACK: Allows assignment to outer scope.
    def iter_search_entries():
        for obj in model_._default_manager.all().iterator():
            for search_entry in search_engine_._update_obj_index_iter(obj):
                yield search_entry
            local_refreshed_model_count[0] += 1
            if verbosity_ >= 3:
                print("Refreshed search entry for {model} {obj} in {engine_slug!r} search engine.".format(
                    model = model_._meta.verbose_name,
                    obj = obj,
                    engine_slug = engine_slug_,
                ))
        if verbosity_ == 2:
            print("Refreshed {local_refreshed_model_count} {model} search entry(s) in {engine_slug!r} search engine.".format(
                model = model_._meta.verbose_name,
                local_refreshed_model_count = local_refreshed_model_count[0],
                engine_slug = engine_slug_,
            ))
    _bulk_save_search_entries(iter_search_entries())
    return local_refreshed_model_count[0]

class Command(BaseCommand):
    args = "[<app.model|model> [search_engine]]"
    help = "Rebuilds the database indices needed by django-watson. You can (re-)build one model only by specifying its name"

    @transaction.commit_on_success
    def handle(self, *args, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))

        # see if we're asked to use specific search engine
        try:
            engine_slug = args[1]
        except IndexError:
            engine_slug = "default"
            if verbosity >= 3:
                print("Using search engine \"default\"")

        # get the engine
        try:
            search_engine = [x[1] for x in SearchEngine.get_created_engines() if x[0] == engine_slug][0]
        except IndexError:
            raise CommandError("Search Engine \"%s\" is not registered!" % engine_slug)

        # is this a partial rebuild for a single model?
        try:
            model_name = args[0]
            full_rebuild = False

            try:
                model = get_model(*model_name.split("."))  # app label, model name
            except TypeError:  # were we given only model name without app_name?
                registered_models = search_engine.get_registered_models()
                models = [x for x in registered_models if x.__name__ == model_name]
                if len(models) > 1:
                    raise CommandError("Model name \"%s\" is not unique, cannot continue!" % model_name)
                if models:
                    model = models[0]
                else:
                    model = None
            if model is None or not search_engine.is_registered(model):
                raise CommandError("Model \"%s\" is not registered with django-watson search engine \"%s\"!" % (model_name, engine_slug))

        except IndexError:  # no arguments passed to us
            full_rebuild = True
        
        refreshed_model_count = [0]  # HACK: Allows assignment to outer scope.
        if full_rebuild:
            for engine_slug, search_engine in SearchEngine.get_created_engines():
                registered_models = search_engine.get_registered_models()
                # Rebuild the index for all registered models.
                for model in registered_models:
                    refreshed_count = rebuild_for_model(model, search_engine, engine_slug, verbosity)
                    refreshed_model_count[0] += refreshed_count

            # Clean out any search entries that exist for stale content types. Only do it during full rebuild
            valid_content_types = [ContentType.objects.get_for_model(model) for model in registered_models]
            stale_entries = SearchEntry.objects.filter(
                engine_slug = engine_slug,
            ).exclude(
                content_type__in = valid_content_types
            )
            stale_entry_count = stale_entries.count()
            if stale_entry_count > 0:
                stale_entries.delete()
            if verbosity >= 1:
                print("Deleted {stale_entry_count} stale search entry(s) in {engine_slug!r} search engine.".format(
                    stale_entry_count = stale_entry_count,
                    engine_slug = engine_slug,
                ))

        else:  # partial rebuild - for one model only
            refreshed_model_count[0] = rebuild_for_model(model, search_engine, engine_slug, verbosity)

        if verbosity == 1:
            print("Refreshed {refreshed_model_count} search entry(s) in {engine_slug!r} search engine.".format(
                refreshed_model_count = refreshed_model_count[0],
                engine_slug = engine_slug,
            ))
