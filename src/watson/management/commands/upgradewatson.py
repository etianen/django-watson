"""Upgrades the database trigger needed by django-watson for multilanguage tables."""

from __future__ import unicode_literals

from django.core.management.base import NoArgsCommand
from django.db import transaction

from watson.registration import get_backend


class Command(NoArgsCommand):

    help = "Upgrades the database trigger needed by django-watson for multilanguage tables."
    
    @transaction.commit_on_success
    def handle_noargs(self, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))
        backend = get_backend()
        if not backend.requires_upgrade:
            if verbosity >= 2:
                self.stdout.write("Your search backend does not require upgrade.\n")
        elif backend.is_upgraded():
            if verbosity >= 2:
                self.stdout.write("django-watson is already upgraded.\n")
        else:
            backend.do_upgrade()
            if verbosity >= 2:
                self.stdout.write("django-watson has been successfully upgraded.\n")