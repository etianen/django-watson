"""Exposed the watson.get_registered_models() function as management command for debugging purpose. """

from django.core.management.base import BaseCommand
from watson import search as watson


class Command(BaseCommand):

    help = "List all registed models by django-watson."

    def handle(self, *args, **options):
        """Runs the management command."""
        self.stdout.write("The following models are registed for the django-watson search engine:\n")
        for mdl in watson.get_registered_models():
            self.stdout.write("- %s\n" % mdl.__name__)
