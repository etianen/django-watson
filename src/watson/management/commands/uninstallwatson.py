"""Destroys the database indices needed by django-watson."""

from __future__ import unicode_literals

from django.core.management.base import BaseCommand

from watson.search import get_backend


class Command(BaseCommand):

    help = "Destroys the database indices needed by django-watson."

    def handle(self, *args, **options):
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
