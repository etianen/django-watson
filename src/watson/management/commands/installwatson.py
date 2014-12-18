"""Creates the database indices needed by django-watson."""

from __future__ import unicode_literals

from django.core.management.base import NoArgsCommand

from watson.registration import get_backend


class Command(NoArgsCommand):

    help = "Creates the database indices needed by django-watson."
    
    def handle_noargs(self, **options):
        """Runs the management command."""
        verbosity = int(options.get("verbosity", 1))
        backend = get_backend()
        if not backend.requires_installation:
            if verbosity >= 2:
                self.stdout.write("Your search backend does not require installation.\n")
        elif backend.is_installed():
            if verbosity >= 2:
                self.stdout.write("django-watson is already installed.\n")
        else:
            backend.do_install()
            if verbosity >= 2:
                self.stdout.write("django-watson has been successfully installed.\n")
