"""Search backends used by django-watson."""

import re

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
    
    def is_installed(self):
        """Checks whether django-watson is installed."""
        return True
    
    def do_install(self):
        """Executes the SQL needed to install django-watson."""
        pass
        
    def do_uninstall(self):
        """Executes the SQL needed to uninstall django-watson."""
        pass
    
    requires_installation = False
    
    supports_ranking = False
    
    def do_search(self, engine_slug, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        word_query = Q()
        for word in search_text.split():
            regex = regex_from_word(word)
            word_query &= (Q(title__iregex=regex) | Q(description__iregex=regex) | Q(content__iregex=regex))
        return queryset.filter(
            word_query
        )
        
    def do_search_ranking(self, engine_slug, queryset, search_text):
        """Ranks the given queryset according to the relevance of the given search text."""
        return queryset.extra(
            select = {
                "watson_rank": "1",
            },
        )
        
    def do_filter(self, engine_slug, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        word_query = Q(searchentry_set__engine_slug=engine_slug)
        for word in search_text.split():
            regex = regex_from_word(word)
            word_query &= (Q(searchentry_set__title__iregex=regex) | Q(searchentry_set__description__iregex=regex) | Q(searchentry_set__content__iregex=regex))
        return queryset.filter(
            word_query
        )
        
    def do_filter_ranking(self, engine_slug, queryset, search_text):
        """Ranks the given queryset according to the relevance of the given search text."""
        return queryset.extra(
            select = {
                "watson_rank": "1",
            },
        )
    
    def save_search_entry(self, search_entry, obj, adapter):
        """Saves the given search entry in the database."""
        search_entry.save()
        
        
class PostgresSearchBackend(SearchBackend):

    """A search backend that uses native PostgreSQL full text indices."""
    
    def is_installed(self):
        """Checks whether django-watson is installed."""
        cursor = connection.cursor()
        cursor.execute("""        
            SELECT attname FROM pg_attribute
            WHERE attrelid = (SELECT oid FROM pg_class WHERE relname = 'watson_searchentry') AND attname = 'search_tsv';
        """)
        return bool(cursor.fetchall())
    
    def do_install(self):
        """Executes the PostgreSQL specific SQL code to install django-watson."""
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
            CREATE TRIGGER watson_searchentry_trigger BEFORE INSERT OR UPDATE
            ON watson_searchentry FOR EACH ROW EXECUTE PROCEDURE watson_searchentry_trigger_handler();
        """)
        
    def do_uninstall(self):
        """Executes the PostgreSQL specific SQL code to uninstall django-watson."""
        connection.cursor().execute("""
            ALTER TABLE watson_searchentry DROP COLUMN search_tsv;
            
            DROP TRIGGER watson_searchentry_trigger ON watson_searchentry;
            
            DROP FUNCTION watson_searchentry_trigger_handler();
        """)
        
    requires_installation = True
    
    supports_ranking = True
        
    def do_search(self, engine_slug, queryset, search_text):
        """Performs the full text search."""
        return queryset.extra(
            where = ("search_tsv @@ plainto_tsquery(%s)",),
            params = (search_text,),
        )
        
    def do_search_ranking(self, engine_slug, queryset, search_text):
        """Performs full text ranking."""
        return queryset.extra(
            select = {
                "watson_rank": "ts_rank_cd(search_tsv, plainto_tsquery(%s))",
            },
            select_params = (search_text,),
            order_by = ("-watson_rank",),
        )
        
    def do_filter(self, engine_slug, queryset, search_text):
        """Performs the full text filter."""
        model = queryset.model
        content_type = ContentType.objects.get_for_model(model)
        pk = model._meta.pk
        if has_int_pk(model):
            ref_name = "object_id_int"
        else:
            ref_name = "object_id"
        return queryset.extra(
            tables = ("watson_searchentry",),
            where = (
                "watson_searchentry.engine_slug = %s",
                "watson_searchentry.search_tsv @@ plainto_tsquery(%s)",
                "watson_searchentry.{ref_name} = {table_name}.{pk_name}".format(
                    ref_name = ref_name,
                    table_name = connection.ops.quote_name(model._meta.db_table),
                    pk_name = connection.ops.quote_name(pk.db_column or pk.attname),
                ),
                "watson_searchentry.content_type_id = %s"
            ),
            params = (engine_slug, search_text, content_type.id),
        )
        
    def do_filter_ranking(self, engine_slug, queryset, search_text):
        """Performs the full text ranking."""
        return queryset.extra(
            select = {
                "watson_rank": "ts_rank_cd(watson_searchentry.search_tsv, plainto_tsquery(%s))",
            },
            select_params = (search_text,),
            order_by = ("-watson_rank",),
        )
        

def escape_mysql_boolean_query(search_text):
    return u" ".join(
        u'+"{word}"'.format(
            word = word.replace(u'"', u''),
        )
        for word in search_text.split()
    )
    

        
class MySQLSearchBackend(SearchBackend):

    def is_installed(self):
        """Checks whether django-watson is installed."""
        cursor = connection.cursor()
        cursor.execute("SHOW INDEX FROM watson_searchentry WHERE Key_name = 'watson_searchentry_fulltext'");
        return bool(cursor.fetchall())

    def do_install(self):
        """Executes the MySQL specific SQL code to install django-watson."""
        cursor = connection.cursor()
        # Drop all foreign keys on the watson_searchentry table.
        cursor.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'watson_searchentry' AND CONSTRAINT_TYPE = 'FOREIGN KEY'")
        for constraint_name, in cursor.fetchall():
            cursor.execute("ALTER TABLE watson_searchentry DROP FOREIGN KEY {constraint_name}".format(
                constraint_name = constraint_name,
            ))
        # Change the storage engine to MyISAM.
        cursor.execute("ALTER TABLE watson_searchentry ENGINE = MyISAM")
        # Change the collaction to a case-insensitive one.
        cursor.execute("ALTER TABLE watson_searchentry CONVERT TO CHARACTER SET utf8 COLLATE utf8_general_ci")
        # Add the full text indexes.
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_fulltext ON watson_searchentry (title, description, content)")
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_title ON watson_searchentry (title)")
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_description ON watson_searchentry (description)")
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_content ON watson_searchentry (content)")
    
    def do_uninstall(self):
        """Executes the SQL needed to uninstall django-watson."""
        cursor = connection.cursor()
        # Destroy the full text indexes.
        cursor.execute("DROP INDEX watson_searchentry_fulltext ON watson_searchentry")
        cursor.execute("DROP INDEX watson_searchentry_title ON watson_searchentry")
        cursor.execute("DROP INDEX watson_searchentry_description ON watson_searchentry")
        cursor.execute("DROP INDEX watson_searchentry_content ON watson_searchentry")
    
    requires_installation = True
    
    supports_ranking = True
    
    def do_search(self, engine_slug, queryset, search_text):
        """Performs the full text search."""
        return queryset.extra(
            where = ("MATCH (title, description, content) AGAINST (%s IN BOOLEAN MODE)",),
            params = (escape_mysql_boolean_query(search_text),),
        )
        
    def do_search_ranking(self, engine_slug, queryset, search_text):
        """Performs full text ranking."""
        search_text = escape_mysql_boolean_query(search_text)
        return queryset.extra(
            select = {
                "watson_rank": """
                    ((MATCH (title) AGAINST (%s IN BOOLEAN MODE)) * 3) +
                    ((MATCH (description) AGAINST (%s IN BOOLEAN MODE)) * 2) +
                    ((MATCH (content) AGAINST (%s IN BOOLEAN MODE)) * 1)
                """,
            },
            select_params = (search_text, search_text, search_text,),
            order_by = ("-watson_rank",),
        )
        
    def do_filter(self, engine_slug, queryset, search_text):
        """Performs the full text filter."""
        model = queryset.model
        content_type = ContentType.objects.get_for_model(model)
        pk = model._meta.pk
        if has_int_pk(model):
            ref_name = "object_id_int"
        else:
            ref_name = "object_id"
        return queryset.extra(
            tables = ("watson_searchentry",),
            where = (
                "watson_searchentry.engine_slug = %s",
                "MATCH (watson_searchentry.title, watson_searchentry.description, watson_searchentry.content) AGAINST (%s IN BOOLEAN MODE)",
                "watson_searchentry.{ref_name} = {table_name}.{pk_name}".format(
                    ref_name = ref_name,
                    table_name = connection.ops.quote_name(model._meta.db_table),
                    pk_name = connection.ops.quote_name(pk.db_column or pk.attname),
                ),
                "watson_searchentry.content_type_id = %s",
            ),
            params = (engine_slug, escape_mysql_boolean_query(search_text), content_type.id),
        )
        
    def do_filter_ranking(self, engine_slug, queryset, search_text):
        """Performs the full text ranking."""
        search_text = escape_mysql_boolean_query(search_text)
        return queryset.extra(
            select = {
                "watson_rank": """
                    ((MATCH (watson_searchentry.title) AGAINST (%s IN BOOLEAN MODE)) * 3) +
                    ((MATCH (watson_searchentry.description) AGAINST (%s IN BOOLEAN MODE)) * 2) +
                    ((MATCH (watson_searchentry.content) AGAINST (%s IN BOOLEAN MODE)) * 1)
                """,
            },
            select_params = (search_text, search_text, search_text,),
            order_by = ("-watson_rank",),
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
        if database_engine.endswith("mysql"):
            return MySQLSearchBackend()
        return SearchBackend()