"""Rebuilds the database indices needed by django-watson."""

from django.core.management.base import NoArgsCommand
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from watson.registration import get_registered_models, search_context_manager
from watson.models import SearchEntry


class Command(NoArgsCommand):

    help = "Rebuilds the database indices needed by django-watson."
    
    @transaction.commit_on_success
    def handle_noargs(self, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))
        registered_models = get_registered_models()
        # Rebuild the index for all registered models.
        refreshed_model_count = 0
        for model in registered_models:
            for obj in model._default_manager.all().iterator():
                search_context_manager.update_obj_index(obj)
                refreshed_model_count += 1
        if verbosity >= 2:
            print u"Refreshed {refreshed_model_count} current search entry(s).".format(
                refreshed_model_count = refreshed_model_count,
            )
        # Clean out any search entries that exist for stale content types.
        valid_content_types = [ContentType.objects.get_for_model(model) for model in registered_models]
        stale_entries = SearchEntry.objects.exclude(content_type__in=valid_content_types)
        stale_entry_count = stale_entries.count()
        stale_entries.delete()
        if verbosity >= 2:
            print u"Deleted {stale_entry_count} stale search entry(s).".format(
                stale_entry_count = stale_entry_count,
            )