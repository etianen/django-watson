"""Models used by django-watson."""

from __future__ import unicode_literals

import json

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property

try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey

def has_int_pk(model):
    """Tests whether the given model has an integer primary key."""
    pk = model._meta.pk
    return (
        (
            isinstance(pk, (models.IntegerField, models.AutoField)) and
            not isinstance(pk, models.BigIntegerField)
        ) or (
            isinstance(pk, models.ForeignKey) and has_int_pk(pk.rel.to)
        )
    )


META_CACHE_KEY = "_meta_cache"


class SearchEntry(models.Model):

    """An entry in the search index."""

    engine_slug = models.CharField(
        max_length = 200,
        db_index = True,
        default = "default",
    )

    content_type = models.ForeignKey(
        ContentType,
    )

    object_id = models.TextField()

    object_id_int = models.IntegerField(
        blank = True,
        null = True,
        db_index = True,
    )

    object = GenericForeignKey()

    title = models.CharField(
        max_length = 1000,
    )

    description = models.TextField(
        blank = True,
    )

    content = models.TextField(
        blank = True,
    )

    url = models.CharField(
        max_length = 1000,
        blank = True,
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

    def __unicode__(self):
        """Returns a unicode representation."""
        return self.title

    class Meta:
        verbose_name_plural = "search entries"
        app_label = 'watson'
