"""Models used by django-watson."""

import cPickle, base64

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
    
    object = generic.GenericForeignKey()
    
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
    
    @property
    def meta(self):
        """Returns the meta information stored with the search entry."""
        # Attempt to use the cached value.
        if hasattr(self, META_CACHE_KEY):
            return getattr(self, META_CACHE_KEY)
        # Decode the meta.
        meta_value = cPickle.loads(base64.decodestring(self.meta_encoded.decode("latin1")))
        setattr(self, META_CACHE_KEY, meta_value)
        return meta_value
        
    @meta.setter
    def meta(self, meta_value):
        """Sets the meta information stored with the search entry."""
        # Remove any cached value.
        if hasattr(self, META_CACHE_KEY):
            delattr(self, META_CACHE_KEY)
        # Set the meta.
        self.meta_encoded = base64.encodestring(cPickle.dumps(meta_value)).encode("latin1")
        
    def get_absolute_url(self):
        """Returns the URL of the referenced object."""
        return self.url
        
    def __unicode__(self):
        """Returns a unicode representation."""
        return self.title
        
    class Meta:
        verbose_name_plural = "search entries"