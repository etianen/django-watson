"""Tests for django-watson."""

from django.db import models
from django.test import TestCase

from watson.backends import get_backend
from watson.registration import register, unregister, is_registered, get_registered_models, get_adaptor, RegistrationError, SearchAdaptor, search_context_manager


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

    @search_context_manager.update_index
    def setUp(self):
        register(TestModel1)
        register(TestModel2)
        # Create some test models.
        self.test11 = TestModel1.objects.create(
            title = "title model1 11",
            content = "content model1 11",
            description = "description model1 11",
        )
        self.test12 = TestModel1.objects.create(
            title = "title model1 12",
            content = "content model1 12",
            description = "description model1 12",
        )
        self.test21 = TestModel2.objects.create(
            title = "title model2 21",
            content = "content model2 21",
            description = "description model2 21",
        )
        self.test22 = TestModel2.objects.create(
            title = "title model2 22",
            content = "content model2 22",
            description = "description model2 22",
        )
        
    def testMultiTableSearch(self):
        backend = get_backend()
        # Test a search that should get all models.
        self.assertEqual(backend.search("title content description").count(), 4)
        # Test a search that should get two models.
        self.assertEqual(backend.search("model1").count(), 2)
        # Test a search that should get one model.
        exact_search = backend.search("11")
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].meta["title"], "title model1 11")
        
    def tearDown(self):
        unregister(TestModel1)
        unregister(TestModel2)
        # Delete the test models.
        TestModel1.objects.all().delete()
        TestModel2.objects.all().delete()
        del self.test11
        del self.test12
        del self.test21
        del self.test22