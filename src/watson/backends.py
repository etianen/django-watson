"""Search backends used by django-watson."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.contenttypes.models import ContentType
from django.db import models, connection
from django.db.models import Q

from watson.models import SearchEntry, has_int_pk


class SearchBackend(object):

    """Base class for all search backends."""
    
    def do_install(self):
        """Generates the SQL needed to install django-watson."""
        pass
        
    def do_search(self, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        words = search_text.split()
        regex = u"|".join(
            u"(\s{word}\s)|(^{word}\s)|(\s{word}$)|(^{word}$)".format(
                word = word,
            )
            for word in words
        )
        return queryset.filter(
            Q(title__iregex=regex) | Q(content__iregex=regex) | Q(content__iregex=regex),
        )
    
    def save_search_entry(self, search_entry, obj, adapter):
        """Saves the given search entry in the database."""
        search_entry.save()
        
        
class PostgresSearchBackend(SearchBackend):

    """A search backend that uses native PostgreSQL full text indices."""
    
    def do_install(self):
        """Generates the PostgreSQL specific SQL code to install django-watson."""
        connection.cursor().execute("""
            ALTER TABLE "watson_searchentry" ADD COLUMN "search_tsv" tsvector NOT NULL;

            CREATE INDEX "watson_searchentry_search_tsv" ON "watson_searchentry" USING gin("search_tsv");
        """)
        
    def do_search(self, queryset, search_text):
        """Performs the full text search."""
        return queryset.extra(
            select = {
                "rank": 'ts_rank_cd("search_tsv", plainto_tsquery(%s))',
            },
            select_params = (search_text,),
            where = ('"search_tsv" @@ plainto_tsquery(%s)',),
            params = (search_text,),
            order_by = ("-rank",),
        )
        
        
class AdaptiveSearchBackend(SearchBackend):

    """
    A search backend that guesses the correct search backend based on the
    DATABASES["default"] settings.
    """
    
    def __new__(cls):
        """Guess the correct search backend and initialize it."""
        return SearchBackend()
        database_engine = settings.DATABASES["default"]["ENGINE"]
        if database_engine.endswith("postgresql_psycopg2") or database_engine.endswith("postgresql"):
            return PostgresSearchBackend()
        else:
            return SearchBackend()