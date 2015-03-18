"""Exposed the watson.get_registered_models() function as management command for debugging purpose. """

from django.core.management.base import NoArgsCommand
import watson

class Command(NoArgsCommand):

    help = "List all registed models by django-watson."
    
    def handle_noargs(self, **options):
        """Runs the management command."""
        self.stdout.write("The following models are registed for the django-watson search engine:\n")
        for mdl in watson.get_registered_models():
            self.stdout.write("- %s\n" % mdl.__name__)
        
        
