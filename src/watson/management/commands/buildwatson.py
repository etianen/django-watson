"""Rebuilds the database indices needed by django-watson."""

from __future__ import unicode_literals, print_function

from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.encoding import force_text
from django.utils.translation import activate
from django.conf import settings


from watson.search import SearchEngine, _bulk_save_search_entries
from watson.models import SearchEntry


# Sets up registration for django-watson's admin integration.
admin.autodiscover()

def get_engine(engine_slug_):
    '''returns search engine with a given name'''
    try:
        return [x[1] for x in SearchEngine.get_created_engines() if x[0] == engine_slug_][0]
    except IndexError:
        raise CommandError("Search Engine \"%s\" is not registered!" % force_text(engine_slug_))

def rebuild_index_for_model(model_, engine_slug_, verbosity_):
    '''rebuilds index for a model'''

    search_engine_ = get_engine(engine_slug_)

    local_refreshed_model_count = [0]  # HACK: Allows assignment to outer scope.
    def iter_search_entries():
        for obj in model_._default_manager.all().iterator():
            for search_entry in search_engine_._update_obj_index_iter(obj):
                yield search_entry
            local_refreshed_model_count[0] += 1
            if verbosity_ >= 3:
                print("Refreshed search entry for {model} {obj} in {engine_slug!r} search engine.".format(
                    model = force_text(model_._meta.verbose_name),
                    obj = force_text(obj),
                    engine_slug = force_text(engine_slug_),
                ))
        if verbosity_ == 2:
            print("Refreshed {local_refreshed_model_count} {model} search entry(s) in {engine_slug!r} search engine.".format(
                model = force_text(model_._meta.verbose_name),
                local_refreshed_model_count = local_refreshed_model_count[0],
                engine_slug = force_text(engine_slug_),
            ))
    _bulk_save_search_entries(iter_search_entries())
    return local_refreshed_model_count[0]

class Command(BaseCommand):
    args = "[[--engine=search_engine] <app.model|model> <app.model|model> ... ]"
    help = "Rebuilds the database indices needed by django-watson. You can (re-)build index for selected models by specifying them"

    option_list = BaseCommand.option_list + (
        make_option("--engine",
            help="Search engine models are registered with"),
        )

    @transaction.atomic()
    def handle(self, *args, **options):
        """Runs the management command."""
        activate(settings.LANGUAGE_CODE)
        verbosity = int(options.get("verbosity", 1))

        # see if we're asked to use a specific search engine
        if options['engine']:
            engine_slug = options['engine']
            engine_selected = True
        else:
            engine_slug = "default"
            engine_selected = False

        # get the search engine we'll be checking registered models for, may be "default"
        search_engine = get_engine(engine_slug)

        models = []
        for model_name in args:
            try:
                model = apps.get_model(*model_name.split("."))  # app label, model name
            except TypeError:  # were we given only model name without app_name?
                registered_models = search_engine.get_registered_models()
                matching_models = [x for x in registered_models if x.__name__ == model_name]
                if len(matching_models) > 1:
                    raise CommandError("Model name \"%s\" is not unique, cannot continue!" % model_name)
                if matching_models:
                    model = matching_models[0]
                else:
                    model = None
            if model is None or not search_engine.is_registered(model):
                raise CommandError("Model \"%s\" is not registered with django-watson search engine \"%s\"!" % (force_text(model_name), force_text(engine_slug)))
            models.append(model)

        refreshed_model_count = 0

        if models:  # request for (re-)building index for a subset of registered models
            if verbosity >= 3:
                print("Using search engine \"%s\"" % engine_slug)
            for model in models:
                refreshed_model_count += rebuild_index_for_model(model, engine_slug, verbosity)

        else:  # full rebuild (for one or all search engines)
            if engine_selected:
                engine_slugs = [engine_slug]
                if verbosity >= 2:
                    # let user know the search engine if they selected one
                    print("Rebuilding models registered with search engine \"%s\"" % force_text(engine_slug))
            else:  # loop through all engines
                engine_slugs = [x[0] for x in SearchEngine.get_created_engines()]

            for engine_slug in engine_slugs:
                search_engine = get_engine(engine_slug)
                registered_models = search_engine.get_registered_models()
                # Rebuild the index for all registered models.
                for model in registered_models:
                    refreshed_model_count += rebuild_index_for_model(model, engine_slug, verbosity)

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
                        engine_slug = force_text(engine_slug),
                    ))

        if verbosity == 1:
            print("Refreshed {refreshed_model_count} search entry(s) in {engine_slug!r} search engine.".format(
                refreshed_model_count = refreshed_model_count,
                engine_slug = force_text(engine_slug),
            ))
