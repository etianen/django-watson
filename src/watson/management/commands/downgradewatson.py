"""Rolls back the database trigger to old fashion."""

from __future__ import unicode_literals

from django.core.management.base import NoArgsCommand
from django.db import transaction

from watson.registration import get_backend


class Command(NoArgsCommand):

    help = "Rolls back the database trigger to old fashion."
    
    @transaction.commit_on_success
    def handle_noargs(self, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))
        backend = get_backend()
        if not backend.requires_installation:
            if verbosity >= 2:
                self.stdout.write("Your search backend does not require installation.\n")
        elif backend.is_upgraded():
            backend.do_downgrade()
            if verbosity >= 2:
                self.stdout.write("django-watson has been successfully downgraded.\n")
        else:
            if verbosity >= 2:
                self.stdout.write("django-watson is not upgraded.\n")