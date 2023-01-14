"""Models used by django-watson."""

from __future__ import unicode_literals

import uuid

from django.db import models
from django.db.models.fields.related import RelatedField
from django.contrib.contenttypes.models import ContentType
from django.utils.encoding import force_str
from django.utils.functional import cached_property

try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey


INTEGER_FIELDS = (models.IntegerField, models.AutoField,)
BIG_INTEGER_FIELDS = (models.BigIntegerField,)

try:
    BIG_INTEGER_FIELDS += (models.BigAutoField,)
except AttributeError:  # Django < 2.0.
    pass


def get_pk_output_field(model):
    """Gets an instance of the field type for the primary key of the given model, useful for database CAST."""
    pk = model._meta.pk
    if isinstance(pk, RelatedField):
        return get_pk_output_field(pk.remote_field.model)
    field_cls = type(pk)
    field_kwargs = {}
    if isinstance(pk, models.CharField):
        # Some versions of Django produce invalid SQL for the CAST function (in some databases)
        # if CharField does not have max_length passed.
        # Therefore, it is necessary to copy over the max_length of the original field to avoid errors.
        # See: https://code.djangoproject.com/ticket/28371
        field_kwargs['max_length'] = pk.max_length
    elif isinstance(pk, models.AutoField):
        # Some versions of Django appear to also produce invalid SQL in MySQL
        # when attempting to CAST with AutoField types.
        # This covers for that by instead casting to the corresponding integer type.
        if isinstance(pk, models.BigAutoField):
            field_cls = models.BigIntegerField
        else:
            field_cls = models.IntegerField
    return field_cls(**field_kwargs)


def has_int_pk(model):
    """Tests whether the given model has an integer primary key."""
    pk = model._meta.pk
    return (
        isinstance(pk, INTEGER_FIELDS) and
        not isinstance(pk, BIG_INTEGER_FIELDS)
    ) or (
        isinstance(pk, models.ForeignKey) and has_int_pk(pk.remote_field.model)
    )


def has_uuid_pk(model):
    """Tests whether the given model has an uuid primary key."""
    pk = model._meta.pk
    return isinstance(pk, models.UUIDField)


def get_str_pk(obj, connection):
    return obj.pk.hex if isinstance(obj.pk, uuid.UUID) and connection.vendor != "postgresql" else force_str(obj.pk)


META_CACHE_KEY = "_meta_cache"


class SearchEntry(models.Model):

    """An entry in the search index."""

    engine_slug = models.CharField(
        max_length=200,
        db_index=True,
        default="default",
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
    )

    object_id = models.CharField(
        db_index=True,
        max_length=191,
    )

    object_id_int = models.IntegerField(
        blank=True,
        null=True,
        db_index=True,
    )

    object = GenericForeignKey()

    title = models.CharField(
        max_length=1000,
    )

    description = models.TextField(
        blank=True,
    )

    content = models.TextField(
        blank=True,
    )

    url = models.CharField(
        max_length=1000,
        blank=True,
    )

    meta_encoded = models.TextField()

    def _deserialize_meta(self):
        from watson.search import SearchEngine
        engine = SearchEngine._created_engines[self.engine_slug]
        model = ContentType.objects.get_for_id(self.content_type_id).model_class()
        adapter = engine.get_adapter(model)
        return adapter.deserialize_meta(self.meta_encoded)

    @cached_property
    def meta(self):
        """Returns the meta information stored with the search entry."""
        # Attempt to use the cached value.
        if hasattr(self, META_CACHE_KEY):
            return getattr(self, META_CACHE_KEY)
        # Decode the meta.
        meta_value = self._deserialize_meta()
        setattr(self, META_CACHE_KEY, meta_value)
        return meta_value

    def get_absolute_url(self):
        """Returns the URL of the referenced object."""
        return self.url

    def __str__(self):
        """Returns a string representation."""
        return self.title

    class Meta:
        verbose_name_plural = "search entries"
        app_label = 'watson'
