"""Destroys the database indices needed by django-watson."""

from __future__ import unicode_literals

from django.core.management.base import NoArgsCommand
from django.db import transaction

from watson.registration import get_backend


class Command(NoArgsCommand):

    help = "Destroys the database indices needed by django-watson."
    
    @transaction.commit_on_success
    def handle_noargs(self, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))
        backend = get_backend()
        if not backend.requires_installation:
            if verbosity >= 2:
                self.stdout.write("Your search backend does not require installation.\n")
        elif backend.is_installed():
            backend.do_uninstall()
            if verbosity >= 2:
                self.stdout.write("django-watson has been successfully uninstalled.\n")
        else:
            if verbosity >= 2:
                self.stdout.write("django-watson is not installed.\n")
