"""Search backends used by django-watson."""

import re, operator

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.contenttypes.models import ContentType
from django.db import models, connection
from django.db.models import Q

from watson.models import SearchEntry, has_int_pk


def regex_from_word(word):
    """Generates a regext from the given search word."""
    return u"(\s{word}\s)|(^{word}\s)|(\s{word}$)|(^{word}$)".format(
        word = re.escape(word),
    )


class SearchBackend(object):

    """Base class for all search backends."""
    
    def do_install(self):
        """Generates the SQL needed to install django-watson."""
        pass
        
    def do_search(self, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        word_queries = []
        for word in search_text.split():
            regex = regex_from_word(word)
            word_queries.append(Q(title__iregex=regex) | Q(content__iregex=regex) | Q(content__iregex=regex))
        word_query = reduce(operator.and_, word_queries)
        return queryset.filter(
            word_query
        )
        
    def do_filter(self, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        word_queries = []
        for word in search_text.split():
            regex = regex_from_word(word)
            word_queries.append(Q(searchentry_set__title__iregex=regex) | Q(searchentry_set__content__iregex=regex) | Q(searchentry_set__content__iregex=regex))
        word_query = reduce(operator.and_, word_queries)
        return queryset.filter(
            word_query
        )
    
    def save_search_entry(self, search_entry, obj, adapter):
        """Saves the given search entry in the database."""
        search_entry.save()
        
        
class PostgresSearchBackend(SearchBackend):

    """A search backend that uses native PostgreSQL full text indices."""
    
    def do_install(self):
        """Generates the PostgreSQL specific SQL code to install django-watson."""
        connection.cursor().execute("""
            -- Ensure that plpgsql is installed.
            CREATE OR REPLACE FUNCTION make_plpgsql() RETURNS VOID LANGUAGE SQL AS
            $$
                CREATE LANGUAGE plpgsql;
            $$;
            SELECT
                CASE
                WHEN EXISTS(
                    SELECT 1
                    FROM pg_catalog.pg_language
                    WHERE lanname='plpgsql'
                )
                THEN NULL
                ELSE make_plpgsql() END;
            DROP FUNCTION make_plpgsql();

            -- Create the search index.
            ALTER TABLE watson_searchentry ADD COLUMN search_tsv tsvector NOT NULL;
            CREATE INDEX watson_searchentry_search_tsv ON watson_searchentry USING gin(search_tsv);
            
            -- Create the trigger function.
            CREATE FUNCTION watson_searchentry_trigger_handler() RETURNS trigger AS $$
            begin
                new.search_tsv :=
                    setweight(to_tsvector('pg_catalog.english', coalesce(new.title, '')), 'A') ||
                    setweight(to_tsvector('pg_catalog.english', coalesce(new.description, '')), 'C') ||
                    setweight(to_tsvector('pg_catalog.english', coalesce(new.content, '')), 'D');
                return new;
            end
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER watson_searchitem_trigger BEFORE INSERT OR UPDATE
            ON watson_searchentry FOR EACH ROW EXECUTE PROCEDURE watson_searchentry_trigger_handler();
        """)
        
    def do_search(self, queryset, search_text):
        """Performs the full text search."""
        return queryset.extra(
            select = {
                "watson_relevance": "ts_rank_cd(search_tsv, plainto_tsquery(%s))",
            },
            select_params = (search_text,),
            where = ("search_tsv @@ plainto_tsquery(%s)",),
            params = (search_text,),
            order_by = ("-watson_relevance",),
        )
        
    def do_filter(self, queryset, search_text):
        """Performs the full text filter."""
        model = queryset.model
        content_type = ContentType.objects.get_for_model(model)
        if has_int_pk(model):
            ref_name = "object_id_int"
        else:
            ref_name = "object_id"
        return queryset.extra(
            select = {
                "watson_relevance": "ts_rank_cd(watson_searchentry.search_tsv, plainto_tsquery(%s))",
            },
            select_params = (search_text,),
            tables = ("watson_searchentry",),
            where = (
                "watson_searchentry.search_tsv @@ plainto_tsquery(%s)",
                "watson_searchentry.{ref_name} = {table_name}.{pk_name}".format(
                    ref_name = ref_name,
                    table_name = connection.ops.quote_name(model._meta.db_table),
                    pk_name = connection.ops.quote_name(model._meta.pk.name),
                ),
                "watson_searchentry.content_type_id = %s"
            ),
            params = (search_text, content_type.id),
            order_by = ("-watson_relevance",),
        )
        
        
class AdaptiveSearchBackend(SearchBackend):

    """
    A search backend that guesses the correct search backend based on the
    DATABASES["default"] settings.
    """
    
    def __new__(cls):
        """Guess the correct search backend and initialize it."""
        database_engine = settings.DATABASES["default"]["ENGINE"]
        if database_engine.endswith("postgresql_psycopg2") or database_engine.endswith("postgresql"):
            return PostgresSearchBackend()
        else:
            return SearchBackend()