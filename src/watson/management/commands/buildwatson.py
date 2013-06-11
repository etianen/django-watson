"""Rebuilds the database indices needed by django-watson."""

from __future__ import unicode_literals, print_function

from django.core.management.base import NoArgsCommand
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from watson.registration import SearchEngine, _bulk_save_search_entries
from watson.models import SearchEntry


# Sets up registration for django-watson's admin integration.
admin.autodiscover()


class Command(NoArgsCommand):

    help = "Rebuilds the database indices needed by django-watson."
    
    @transaction.commit_on_success
    def handle_noargs(self, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))
        for engine_slug, search_engine in SearchEngine.get_created_engines():
            registered_models = search_engine.get_registered_models()
            # Rebuild the index for all registered models.
            refreshed_model_count = [0]  # HACK: Allows assignment to outer scope.
            def iter_search_entries():
                for model in registered_models:
                    local_refreshed_model_count = 0
                    for obj in model._default_manager.all().iterator():
                        for search_entry in search_engine._update_obj_index_iter(obj):
                            yield search_entry
                        local_refreshed_model_count += 1
                        if verbosity >= 3:
                            print("Refreshed search entry for {model} {obj} in {engine_slug!r} search engine.".format(
                                model = model._meta.verbose_name,
                                obj = obj,
                                engine_slug = engine_slug,
                            ))
                    refreshed_model_count[0] += local_refreshed_model_count
                    if verbosity == 2:
                        print("Refreshed {local_refreshed_model_count} {model} search entry(s) in {engine_slug!r} search engine.".format(
                            model = model._meta.verbose_name,
                            local_refreshed_model_count = local_refreshed_model_count,
                            engine_slug = engine_slug,
                        ))
            _bulk_save_search_entries(iter_search_entries())
            if verbosity == 1:
                print("Refreshed {refreshed_model_count} search entry(s) in {engine_slug!r} search engine.".format(
                    refreshed_model_count = refreshed_model_count[0],
                    engine_slug = engine_slug,
                ))
            # Clean out any search entries that exist for stale content types.
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
