"""Models used by django-watson."""

import cPickle

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic


def has_int_pk(model):
    """Tests whether the given model has an integer primary key."""
    return (
        isinstance(model._meta.pk, (models.IntegerField, models.AutoField)) and
        not isinstance(model._meta.pk, models.BigIntegerField)
    )
    
    
META_CACHE_KEY = "_meta_cache"


class SearchEntry(models.Model):

    """An entry in the search index."""

    content_type = models.ForeignKey(
        ContentType,
    )

    object_id = models.TextField()
    
    object_id_int = models.IntegerField(
        blank = True,
        null = True,
        db_index = True,
    )
    
    object = generic.GenericForeignKey()
    
    meta_encoded = models.TextField()
    
    @property
    def meta(self):
        """Returns the meta information stored with the search entry."""
        # Attempt to use the cached value.
        if hasattr(self, META_CACHE_KEY):
            return getattr(self, META_CACHE_KEY)
        # Decode the meta.
        meta_value = cPickle.loads(self.meta_encoded.encode("utf-8"))
        setattr(self, META_CACHE_KEY, meta_value)
        return meta_value
        
    @meta.setter
    def meta(self, meta_value):
        """Sets the meta information stored with the search entry."""
        # Remove any cached value.
        if hasattr(self, META_CACHE_KEY):
            delattr(self, META_CACHE_KEY)
        # Set the meta.
        self.meta_encoded = cPickle.dumps(meta_value).decode("utf-8")