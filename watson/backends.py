"""Search backends used by django-watson."""

from __future__ import unicode_literals

import abc
import re

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction, connections, router
from django.db.models import Q, FloatField
from django.db.models.expressions import RawSQL, Value
from django.utils.encoding import force_str

from watson.models import SearchEntry, has_int_pk, has_uuid_pk


def regex_from_word(word):
    """Generates a regex from the given search word."""
    return r"(\s{word})|(^{word})".format(
        word=re.escape(word),
    )


# PostgreSQL to_tsquery operators: ! & : ( ) |
RE_POSTGRES_ESCAPE_CHARS = re.compile(r'[&:(|)!><]', re.UNICODE)
# MySQL boolean full-text search operators: > < ( ) " ~ * + -
RE_MYSQL_ESCAPE_CHARS = re.compile(r'["()><~*+-]', re.UNICODE)

RE_SPACE = re.compile(r"[\s]+", re.UNICODE)


def escape_query(text, re_escape_chars):
    """
    normalizes the query text to a format that can be consumed
    by the backend database
    """
    text = force_str(text)
    text = RE_SPACE.sub(" ", text)  # Standardize spacing.
    text = re_escape_chars.sub(" ", text)  # Replace harmful characters with space.
    text = text.strip()
    return text


class SearchBackend(metaclass=abc.ABCMeta):
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

    supports_prefix_matching = False

    def do_search_ranking(self, engine_slug, queryset, search_text):
        """Ranks the given queryset according to the relevance of the given search text."""
        return queryset.annotate(watson_rank=Value(1.0, output_field=FloatField()))

    @abc.abstractmethod
    def do_search(self, engine_slug, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        raise NotImplementedError

    def do_filter_ranking(self, engine_slug, queryset, search_text):
        """Ranks the given queryset according to the relevance of the given search text."""
        return queryset.annotate(watson_rank=Value(1.0, output_field=FloatField()))

    @abc.abstractmethod
    def do_filter(self, engine_slug, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        raise NotImplementedError

    def do_string_cast(self, connection, column_name):
        """Casts the given column name to string."""
        return connection.ops.quote_name(column_name)


class RegexSearchMixin(metaclass=abc.ABCMeta):

    """Mixin to adding regex search to a search backend."""

    supports_prefix_matching = True

    def do_search(self, engine_slug, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        word_query = Q()
        for word in search_text.split():
            regex = regex_from_word(word)
            word_query &= (Q(title__iregex=regex) | Q(description__iregex=regex) | Q(content__iregex=regex))
        return queryset.filter(
            word_query
        )

    def do_filter(self, engine_slug, queryset, search_text):
        """Filters the given queryset according the the search logic for this backend."""
        model = queryset.model
        connection = connections[queryset.db]

        db_table = connection.ops.quote_name(SearchEntry._meta.db_table)
        model_db_table = connection.ops.quote_name(model._meta.db_table)
        pk = model._meta.pk
        id = connection.ops.quote_name(pk.db_column or pk.attname)
        # Add in basic filters.
        word_query = ["""
            ({db_table}.{engine_slug} = %s)
        """, """
            ({db_table}.{content_type_id} = %s)
        """]
        word_kwargs = {
            "db_table": db_table,
            "model_db_table": model_db_table,
            "engine_slug": connection.ops.quote_name("engine_slug"),
            "title": connection.ops.quote_name("title"),
            "description": connection.ops.quote_name("description"),
            "content": connection.ops.quote_name("content"),
            "content_type_id": connection.ops.quote_name("content_type_id"),
            "object_id": connection.ops.quote_name("object_id"),
            "object_id_int": connection.ops.quote_name("object_id_int"),
            "id": id,
            "iregex_operator": connection.operators["iregex"],
        }
        word_args = [
            engine_slug,
            ContentType.objects.get_for_model(model).id,
        ]
        # Add in join.
        if has_int_pk(model):
            word_query.append("""
                ({db_table}.{object_id_int} = {model_db_table}.{id})
            """)
        else:
            word_query.append("""
                ({db_table}.{object_id} = {model_db_table}.{id})
            """)
        # Add in all words.
        for word in search_text.split():
            regex = regex_from_word(word)
            word_query.append(
                """
                ({db_table}.{title} {iregex_operator}
                OR {db_table}.{description} {iregex_operator}
                OR {db_table}.{content} {iregex_operator})
                """
            )
            word_args.extend((regex, regex, regex))
        # Compile the query.
        full_word_query = " AND ".join(word_query).format(**word_kwargs)
        return queryset.extra(
            tables=(db_table,),
            where=(full_word_query,),
            params=word_args,
        )


class RegexSearchBackend(RegexSearchMixin, SearchBackend):

    """A search backend that works with SQLite3."""


class PostgresSearchBackend(SearchBackend):

    """A search backend that uses native PostgreSQL full text indices."""

    search_config = getattr(settings, "WATSON_POSTGRES_SEARCH_CONFIG", "pg_catalog.english")
    """Text search configuration to use in `to_tsvector` and `to_tsquery` functions"""

    def escape_postgres_query(self, text):
        """Escapes the given text to become a valid ts_query."""
        return " & ".join(
            "$${0}$$:*".format(word)
            for word
            in escape_query(text, RE_POSTGRES_ESCAPE_CHARS).split()
        )

    def is_installed(self):
        """Checks whether django-watson is installed."""
        connection = connections[router.db_for_read(SearchEntry)]

        cursor = connection.cursor()
        cursor.execute("""
            SELECT attname FROM pg_attribute
            WHERE attrelid = (SELECT oid FROM pg_class WHERE relname = 'watson_searchentry') AND attname = 'search_tsv';
        """)
        return bool(cursor.fetchall())

    @transaction.atomic()
    def do_install(self):
        """Executes the PostgreSQL specific SQL code to install django-watson."""
        connection = connections[router.db_for_write(SearchEntry)]

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
            CREATE OR REPLACE FUNCTION watson_searchentry_trigger_handler() RETURNS trigger AS $$
            begin
                new.search_tsv :=
                    setweight(to_tsvector('{search_config}', coalesce(new.title, '')), 'A') ||
                    setweight(to_tsvector('{search_config}', coalesce(new.description, '')), 'C') ||
                    setweight(to_tsvector('{search_config}', coalesce(new.content, '')), 'D');
                return new;
            end
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER watson_searchentry_trigger BEFORE INSERT OR UPDATE
            ON watson_searchentry FOR EACH ROW EXECUTE PROCEDURE watson_searchentry_trigger_handler();
        """.format(
            search_config=self.search_config
        ))

    @transaction.atomic()
    def do_uninstall(self):
        """Executes the PostgreSQL specific SQL code to uninstall django-watson."""
        connection = connections[router.db_for_write(SearchEntry)]

        connection.cursor().execute("""
            ALTER TABLE watson_searchentry DROP COLUMN search_tsv;

            DROP TRIGGER watson_searchentry_trigger ON watson_searchentry;

            DROP FUNCTION watson_searchentry_trigger_handler();
        """)

    requires_installation = True

    supports_ranking = True

    supports_prefix_matching = True

    def do_search(self, engine_slug, queryset, search_text):
        """Performs the full text search."""
        return queryset.extra(
            where=("search_tsv @@ to_tsquery('{search_config}', %s)".format(
                search_config=self.search_config
            ),),
            params=(self.escape_postgres_query(search_text),),
        )

    def do_search_ranking(self, engine_slug, queryset, search_text):
        """Performs full text ranking."""
        return queryset.annotate(
                watson_rank=RawSQL("ts_rank_cd(watson_searchentry.search_tsv, to_tsquery('{config}', %s))".format(
                    config=self.search_config,
                ), (self.escape_postgres_query(search_text),))
        ).order_by("-watson_rank")

    def do_filter(self, engine_slug, queryset, search_text):
        """Performs the full text filter."""
        model = queryset.model
        content_type = ContentType.objects.get_for_model(model)
        connection = connections[queryset.db]

        pk = model._meta.pk
        if has_int_pk(model):
            ref_name = "object_id_int"
            ref_name_typecast = ""
            watson_id_typecast = ""
        elif has_uuid_pk(model):
            ref_name = "object_id"
            # Moving the type cast happens on the watson_searchentry table.
            # This ensures the primary key will be properly used.
            ref_name_typecast = ""
            watson_id_typecast = "::uuid"
        else:
            ref_name = "object_id"
            # Cast to text to make join work with other column types
            ref_name_typecast = "::text"
            watson_id_typecast = ""

        return queryset.extra(
            tables=("watson_searchentry",),
            where=(
                "watson_searchentry.engine_slug = %s",
                "watson_searchentry.search_tsv @@ to_tsquery('{search_config}', %s)".format(
                    search_config=self.search_config
                ),
                "watson_searchentry.{ref_name}{watson_id_typecast} = {table_name}.{pk_name}{ref_name_typecast}".format(

                    ref_name=ref_name,
                    table_name=connection.ops.quote_name(model._meta.db_table),
                    pk_name=connection.ops.quote_name(pk.db_column or pk.attname),
                    ref_name_typecast=ref_name_typecast,
                    watson_id_typecast=watson_id_typecast
                ),
                "watson_searchentry.content_type_id = %s"
            ),
            params=(engine_slug, self.escape_postgres_query(search_text), content_type.id),
        )

    def do_filter_ranking(self, engine_slug, queryset, search_text):
        """Performs the full text ranking."""
        return queryset.annotate(
                watson_rank=RawSQL("ts_rank_cd(watson_searchentry.search_tsv, to_tsquery('{config}', %s))".format(
                    config=self.search_config,
                ), (self.escape_postgres_query(search_text),))
        ).order_by("-watson_rank")

    def do_string_cast(self, connection, column_name):
        return "{column_name}::text".format(
            column_name=connection.ops.quote_name(column_name),
        )


def escape_mysql_boolean_query(search_text):
    return " ".join(
        '+{word}*'.format(
            word=word,
        )
        for word in escape_query(search_text, RE_MYSQL_ESCAPE_CHARS).split()
    )


class MySQLSearchBackend(SearchBackend):

    def is_installed(self):
        """Checks whether django-watson is installed."""
        connection = connections[router.db_for_read(SearchEntry)]

        cursor = connection.cursor()
        cursor.execute("SHOW INDEX FROM watson_searchentry WHERE Key_name = 'watson_searchentry_fulltext'")
        return bool(cursor.fetchall())

    def do_install(self):
        """Executes the MySQL specific SQL code to install django-watson."""
        connection = connections[router.db_for_write(SearchEntry)]
        cursor = connection.cursor()
        # Drop all foreign keys on the watson_searchentry table.
        cursor.execute(
            "SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'watson_searchentry' "
            "AND CONSTRAINT_TYPE = 'FOREIGN KEY'"
        )
        for constraint_name, in cursor.fetchall():
            cursor.execute(
                "ALTER TABLE watson_searchentry DROP FOREIGN KEY {constraint_name}".format(
                    constraint_name=constraint_name,
                )
            )
        # Change the storage engine to MyISAM.
        cursor.execute("ALTER TABLE watson_searchentry ENGINE = MyISAM")
        # Add the full text indexes.
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_fulltext "
                       "ON watson_searchentry (title, description, content)")
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_title "
                       "ON watson_searchentry (title)")
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_description "
                       "ON watson_searchentry (description)")
        cursor.execute("CREATE FULLTEXT INDEX watson_searchentry_content "
                       "ON watson_searchentry (content)")

    def do_uninstall(self):
        """Executes the SQL needed to uninstall django-watson."""
        connection = connections[router.db_for_write(SearchEntry)]
        cursor = connection.cursor()
        # Destroy the full text indexes.
        cursor.execute("DROP INDEX watson_searchentry_fulltext ON watson_searchentry")
        cursor.execute("DROP INDEX watson_searchentry_title ON watson_searchentry")
        cursor.execute("DROP INDEX watson_searchentry_description ON watson_searchentry")
        cursor.execute("DROP INDEX watson_searchentry_content ON watson_searchentry")

    supports_prefix_matching = True

    requires_installation = True

    supports_ranking = True

    def _format_query(self, search_text):
        return escape_mysql_boolean_query(search_text)

    def do_search(self, engine_slug, queryset, search_text):
        """Performs the full text search."""
        return queryset.extra(
            where=("MATCH (title, description, content) AGAINST (%s IN BOOLEAN MODE)",),
            params=(self._format_query(search_text),),
        )

    def do_search_ranking(self, engine_slug, queryset, search_text):
        """Performs full text ranking."""
        search_text = self._format_query(search_text)
        return queryset.annotate(
                watson_rank=RawSQL("""
                    ((MATCH (title) AGAINST (%s IN BOOLEAN MODE)) * 3) +
                    ((MATCH (description) AGAINST (%s IN BOOLEAN MODE)) * 2) +
                    ((MATCH (content) AGAINST (%s IN BOOLEAN MODE)) * 1)
                """, (search_text, search_text, search_text,))
        ).order_by("-watson_rank")

    def do_filter(self, engine_slug, queryset, search_text):
        """Performs the full text filter."""
        model = queryset.model
        content_type = ContentType.objects.get_for_model(model)
        connection = connections[queryset.db]
        pk = model._meta.pk
        if has_int_pk(model):
            ref_name = "object_id_int"
        else:
            ref_name = "object_id"
        return queryset.extra(
            tables=("watson_searchentry",),
            where=(
                "watson_searchentry.engine_slug = %s",
                "MATCH (watson_searchentry.title, watson_searchentry.description, watson_searchentry.content) "
                "AGAINST (%s IN BOOLEAN MODE)",
                "watson_searchentry.{ref_name} = {table_name}.{pk_name}".format(
                    ref_name=ref_name,
                    table_name=connection.ops.quote_name(model._meta.db_table),
                    pk_name=connection.ops.quote_name(pk.db_column or pk.attname),
                ),
                "watson_searchentry.content_type_id = %s",
            ),
            params=(engine_slug, self._format_query(search_text), content_type.id),
        )

    def do_filter_ranking(self, engine_slug, queryset, search_text):
        """Performs the full text ranking."""
        search_text = self._format_query(search_text)
        return queryset.annotate(
                watson_rank=RawSQL("""
                    ((MATCH (watson_searchentry.title) AGAINST (%s IN BOOLEAN MODE)) * 3) +
                    ((MATCH (watson_searchentry.description) AGAINST (%s IN BOOLEAN MODE)) * 2) +
                    ((MATCH (watson_searchentry.content) AGAINST (%s IN BOOLEAN MODE)) * 1)
                """, (search_text, search_text, search_text,))
        ).order_by("-watson_rank")


class AdaptiveSearchBackend(SearchBackend):

    """
    A search backend that guesses the correct search backend based on the
    DATABASES["default"] settings.
    """

    def __new__(cls):
        """Guess the correct search backend and initialize it."""
        connection = connections[router.db_for_read(SearchEntry)]
        if connection.vendor == "postgresql":
            return PostgresSearchBackend()
        if connection.vendor == "mysql":
            return MySQLSearchBackend()
        return RegexSearchBackend()
