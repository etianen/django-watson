"""Tests for django-watson."""

from django.db import models
from django.test import TestCase

from watson.registration import register, unregister, is_registered, get_registered_models, get_adaptor, RegistrationError, SearchAdaptor, search_context_manager, get_backend


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


str_pk_gen = 0;

def get_str_pk():
    global str_pk_gen
    str_pk_gen += 1;
    return str(str_pk_gen)
    
    
class TestModel2(TestModelBase):

    id = models.CharField(
        primary_key = True,
        max_length = 100,
        default = get_str_pk
    )


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
        self.assertEqual(backend.search("tItle Content Description").count(), 4)
        # Test a search that should get two models.
        self.assertEqual(backend.search("mOdel1").count(), 2)
        # Test a search that should get one model.
        exact_search = backend.search("11")
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].meta["title"], "title model1 11")
    
    def testUpdateSearchIndex(self):
        backend = get_backend()
        # Update a model and make sure that the search results match.
        with search_context_manager.context():
            self.test11.title = "foo"
            self.test11.save()
        # Test a search that should get one model.
        exact_search = backend.search("foo")
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].meta["title"], "foo")
    
    def testLimitedModelList(self):
        backend = get_backend()
        # Test a search that should get all models.
        self.assertEqual(backend.search("tItle Content Description", models=(TestModel1,)).count(), 2)
        # Test a search that should get one model.
        exact_search = backend.search("11", models=(TestModel1,))
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].meta["title"], "title model1 11")
        # Test a search that should get no models.
        self.assertEqual(backend.search("11", models=(TestModel2,)).count(), 0)
        
    def testExcludedModelList(self):
        backend = get_backend()
        # Test a search that should get all models.
        self.assertEqual(backend.search("tItle Content Description", exclude=(TestModel2,)).count(), 2)
        # Test a search that should get one model.
        exact_search = backend.search("11", exclude=(TestModel2,))
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].meta["title"], "title model1 11")
        # Test a search that should get no models.
        self.assertEqual(backend.search("11", exclude=(TestModel1,)).count(), 0)
        
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