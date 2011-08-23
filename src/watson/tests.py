"""Tests for django-watson."""

from django.db import models
from django.test import TestCase
from django.core.management import call_command

import watson
from watson.registration import RegistrationError
from watson.models import SearchEntry


class TestModelManager(models.Manager):

    def get_query_set(self):
        return super(TestModelManager, self).get_query_set().filter(is_published=True)


class TestModelBase(models.Model):

    objects = TestModelManager()

    title = models.CharField(
        max_length = 200,
    )
    
    content = models.TextField(
        blank = True,
    )
    
    description = models.TextField(
        blank = True,
    )
    
    is_published = models.BooleanField(
        default = True,
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
    
    
class TestModel2SearchAdapter(watson.SearchAdapter):

    exclude = ("id",)


class RegistrationTest(TestCase):
    
    def testRegistration(self):
        # Register the model and test.
        watson.register(TestModel1)
        self.assertTrue(watson.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: watson.register(TestModel1))
        self.assertEqual(watson.get_registered_models(), [TestModel1])
        self.assertTrue(isinstance(watson.get_adapter(TestModel1), watson.SearchAdapter))
        # Unregister the model and text.
        watson.unregister(TestModel1)
        self.assertFalse(watson.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: watson.unregister(TestModel1))
        self.assertEqual(watson.get_registered_models(), [])
        self.assertRaises(RegistrationError, lambda: isinstance(watson.get_adapter(TestModel1)))
        
        
class SearchTest(TestCase):
    
    search_adapter_1 = watson.SearchAdapter
    
    search_adapter_2 = TestModel2SearchAdapter
    
    @watson.update_index
    def setUp(self):
        watson.register(TestModel1, self.search_adapter_1)
        watson.register(TestModel2, self.search_adapter_2)
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
    
    def testSearchEntriesCreated(self):
        self.assertEqual(SearchEntry.objects.count(), 4)
    
    def testMultiTableSearch(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("tItle Content Description").count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("mOdel1").count(), 2)
        # Test a search that should get one model.
        exact_search = watson.search("11")
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].title, "title model1 11")
    
    def testUpdateSearchIndex(self):
        # Update a model and make sure that the search results match.
        with watson.context():
            self.test11.title = "foo"
            self.test11.save()
        # Test a search that should get one model.
        exact_search = watson.search("foo")
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].title, "foo")
        # Delete a model and make sure that the search results match.
        self.test11.delete()
        self.assertEqual(watson.search("foo").count(), 0)
    
    def testLimitedModelList(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("tItle Content Description", models=(TestModel1,)).count(), 2)
        # Test a search that should get one model.
        exact_search = watson.search("11", models=(TestModel1,))
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].title, "title model1 11")
        # Test a search that should get no models.
        self.assertEqual(watson.search("11", models=(TestModel2,)).count(), 0)
        
    def testExcludedModelList(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("tItle Content Description", exclude=(TestModel2,)).count(), 2)
        # Test a search that should get one model.
        exact_search = watson.search("11", exclude=(TestModel2,))
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].title, "title model1 11")
        # Test a search that should get no models.
        self.assertEqual(watson.search("11", exclude=(TestModel1,)).count(), 0)
            
    def testRebuildWatsonCommand(self):
        # This update won't take affect, because no search context is active.
        self.test11.title = "foo"
        self.test11.save()
        # Test that no update has happened.
        self.assertEqual(watson.search("foo").count(), 0)
        # Run the rebuild command.
        call_command("buildwatson")
        # Test that the update is now applies.
        self.assertEqual(watson.search("foo").count(), 1)
        
    def tearDown(self):
        watson.unregister(TestModel1)
        watson.unregister(TestModel2)
        # Delete the test models.
        TestModel1.objects.all().delete()
        TestModel2.objects.all().delete()
        del self.test11
        del self.test12
        del self.test21
        del self.test22
        # Delete the search index.
        SearchEntry.objects.all().delete()


class LiveFilterSearchAdapter(watson.SearchAdapter):

    live_filter = True
    
    
class LiveFilterModel2SearchAdapter(TestModel2SearchAdapter):

    live_filter = True
        
        
class LiveFilterSearchTest(SearchTest):

    search_adapter_1 = LiveFilterSearchAdapter
    
    search_adapter_2 = LiveFilterModel2SearchAdapter
    
    def testUnpublishedModelsNotFound(self):
        # Make sure that there are four to find!
        self.assertEqual(watson.search("tItle Content Description").count(), 4)
        # Unpublish two objects.
        with watson.context():
            self.test11.is_published = False
            self.test11.save()
            self.test21.is_published = False
            self.test21.save()
        # This should return 4, but two of them are unpublished.
        self.assertEqual(watson.search("tItle Content Description").count(), 2)