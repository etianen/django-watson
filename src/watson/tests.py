"""Tests for django-watson."""

from django.db import models
from django.test import TestCase

from watson.registration import register, unregister, is_registered, get_registered_models, get_adaptor, RegistrationError, SearchAdaptor


class TestModelBase(models.Model):

    title = models.CharField(
        max_length = 200,
    )
    
    content = models.TextField(
        blank = True,
    )
    
    description = models.TextField(
        blank = True,
    )
    
    def __unicode__(self):
        return self.title

    class Meta:
        abstract = True
        app_label = "auth"  # Hack: Cannot use an app_label that is under South control, due to http://south.aeracode.org/ticket/520
        
        
class TestModel1(TestModelBase):

    pass
    
    
class TestModel2(TestModelBase):

    pass


class RegistrationText(TestCase):
    
    def testRegistration(self):
        # Register the model and test.
        register(TestModel1)
        self.assertTrue(is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: register(TestModel1))
        self.assertEqual(get_registered_models(), [TestModel1])
        self.assertTrue(isinstance(get_adaptor(TestModel1), SearchAdaptor))
        # Unregister the model and text.
        unregister(TestModel1)
        self.assertFalse(is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: unregister(TestModel1))
        self.assertEqual(get_registered_models(), [])
        self.assertRaises(RegistrationError, lambda: isinstance(get_adaptor(TestModel1)))
        
        
class SearchTest(TestCase):

    def setUp(self):
        register(TestModel1)
        register(TestModel2)
        
    def tearDown(self):
        unregister(TestModel1)
        unregister(TestModel2)