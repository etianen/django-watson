"""Tests for django-watson."""

from django.db import models
from django.test import TestCase

from watson.registration import register, unregister, is_registered, get_registered_models, get_adaptor, RegistrationError, SearchAdaptor


class TestModel(models.Model):

    class Meta:
        app_label = "auth"  # Hack: Cannot use an app_label that is under South control, due to http://south.aeracode.org/ticket/520


class RegistrationText(TestCase):
    
    def testRegistration(self):
        # Register the model and test.
        register(TestModel)
        self.assertTrue(is_registered(TestModel))
        self.assertRaises(RegistrationError, lambda: register(TestModel))
        self.assertEqual(get_registered_models(), [TestModel])
        self.assertTrue(isinstance(get_adaptor(TestModel), SearchAdaptor))
        # Unregister the model and text.
        unregister(TestModel)
        self.assertFalse(is_registered(TestModel))
        self.assertRaises(RegistrationError, lambda: unregister(TestModel))
        self.assertEqual(get_registered_models(), [])
        self.assertRaises(RegistrationError, lambda: isinstance(get_adaptor(TestModel)))