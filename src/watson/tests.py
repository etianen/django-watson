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


class RegistrationTest(TestCase):
    
    def testRegistration(self):
        # Register the model and test.
        watson.register(TestModel1)
        self.assertTrue(watson.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: watson.register(TestModel1))
        self.assertTrue(TestModel1 in watson.get_registered_models())
        self.assertTrue(isinstance(watson.get_adapter(TestModel1), watson.SearchAdapter))
        # Unregister the model and text.
        watson.unregister(TestModel1)
        self.assertFalse(watson.is_registered(TestModel1))
        self.assertRaises(RegistrationError, lambda: watson.unregister(TestModel1))
        self.assertTrue(TestModel1 not in watson.get_registered_models())
        self.assertRaises(RegistrationError, lambda: isinstance(watson.get_adapter(TestModel1)))


class SearchTestBase(TestCase):

    live_filter = False

    @watson.update_index
    def setUp(self):
        # Remove all the current registered models.
        self.registered_models = watson.get_registered_models()
        for model in self.registered_models:
            watson.unregister(model)
        # Register the test models.
        watson.register(TestModel1, live_filter=self.live_filter)
        watson.register(TestModel2, exclude=("id",), live_filter=self.live_filter)
        # Create some test models.
        self.test11 = TestModel1.objects.create(
            title = "title model1 instance11",
            content = "content model1 instance11",
            description = "description model1 instance11",
        )
        self.test12 = TestModel1.objects.create(
            title = "title model1 instance12",
            content = "content model1 instance12",
            description = "description model1 instance12",
        )
        self.test21 = TestModel2.objects.create(
            title = "title model2 instance21",
            content = "content model2 instance21",
            description = "description model2 instance21",
        )
        self.test22 = TestModel2.objects.create(
            title = "title model2 instance22",
            content = "content model2 instance22",
            description = "description model2 instance22",
        )

    def tearDown(self):
        # Re-register the old registered models.
        for model in self.registered_models:
            watson.register(model)
        # Unregister the test models.
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


class InternalsTest(SearchTestBase):

    def testSearchEntriesCreated(self):
        self.assertEqual(SearchEntry.objects.count(), 4)
        
    def testBuildWatsonCommand(self):
        # This update won't take affect, because no search context is active.
        self.test11.title = "foo"
        self.test11.save()
        # Test that no update has happened.
        self.assertEqual(watson.search("foo").count(), 0)
        # Run the rebuild command.
        call_command("buildwatson", verbosity=0)
        # Test that the update is now applies.
        self.assertEqual(watson.search("foo").count(), 1)
        
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
        
    def testFixesDuplicateSearchEntries(self):
        # Duplicate a couple of search entries.
        for search_entry in SearchEntry.objects.all()[:2]:
            search_entry.id = None
            search_entry.save()
        # Make sure that we have six (including duplicates).
        self.assertEqual(SearchEntry.objects.count(), 6)
        # Run the rebuild command.
        call_command("buildwatson", verbosity=0)
        # Make sure that we have four again (including duplicates).
        self.assertEqual(SearchEntry.objects.count(), 4)
    
    def testSearchEmailParts(self):
        with watson.context():
            self.test11.content = "foo@bar.com"
            self.test11.save()
        self.assertEqual(watson.search("foo").count(), 1)
        self.assertEqual(watson.search("bar.com").count(), 1)
        self.assertEqual(watson.search("foo@bar.com").count(), 1)
        
    def testFilter(self):
        for model in (TestModel1, TestModel2):
            # Test can find all.
            self.assertEqual(watson.filter(model, "TITLE").count(), 2)
        # Test can find a specific one.
        obj = watson.filter(TestModel1, "INSTANCE12").get()
        self.assertTrue(isinstance(obj, TestModel1))
        self.assertEqual(obj.title, "title model1 instance12")
        # Test can do filter on a queryset.
        obj = watson.filter(TestModel1.objects.filter(title__icontains="TITLE"), "INSTANCE12").get()
        self.assertTrue(isinstance(obj, TestModel1))
        self.assertEqual(obj.title, "title model1 instance12")
        
        
class SearchTest(SearchTestBase):
    
    def testMultiTableSearch(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE").count(), 4)
        self.assertEqual(watson.search("CONTENT").count(), 4)
        self.assertEqual(watson.search("DESCRIPTION").count(), 4)
        self.assertEqual(watson.search("TITLE CONTENT_DESCRIPTION").count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1").count(), 2)
        self.assertEqual(watson.search("MODEL2").count(), 2)
        self.assertEqual(watson.search("TITLE MODEL1").count(), 2)
        self.assertEqual(watson.search("TITLE MODEL2").count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11").count(), 1)
        self.assertEqual(watson.search("INSTANCE21").count(), 1)
        self.assertEqual(watson.search("TITLE INSTANCE11").count(), 1)
        self.assertEqual(watson.search("TITLE INSTANCE21").count(), 1)
        # Test a search that should get zero models.
        self.assertEqual(watson.search("FOO").count(), 0)
        self.assertEqual(watson.search("FOO INSTANCE11").count(), 0)
        self.assertEqual(watson.search("MODEL2 INSTANCE11").count(), 0)
    
    def testLimitedModelList(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE", models=(TestModel1, TestModel2)).count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", models=(TestModel1, TestModel2)).count(), 2)
        self.assertEqual(watson.search("MODEL1", models=(TestModel1,)).count(), 2)
        self.assertEqual(watson.search("MODEL2", models=(TestModel1, TestModel2)).count(), 2)
        self.assertEqual(watson.search("MODEL2", models=(TestModel2,)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", models=(TestModel1, TestModel2)).count(), 1)
        self.assertEqual(watson.search("INSTANCE11", models=(TestModel1,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", models=(TestModel1, TestModel2,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", models=(TestModel2,)).count(), 1)
        # Test a search that should get zero models.
        self.assertEqual(watson.search("MODEL1", models=(TestModel2,)).count(), 0)
        self.assertEqual(watson.search("MODEL2", models=(TestModel1,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", models=(TestModel1,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE11", models=(TestModel2,)).count(), 0)
        
    def testExcludedModelList(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE", exclude=()).count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", exclude=()).count(), 2)
        self.assertEqual(watson.search("MODEL1", exclude=(TestModel2,)).count(), 2)
        self.assertEqual(watson.search("MODEL2", exclude=()).count(), 2)
        self.assertEqual(watson.search("MODEL2", exclude=(TestModel1,)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", exclude=()).count(), 1)
        self.assertEqual(watson.search("INSTANCE11", exclude=(TestModel2,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=()).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=(TestModel1,)).count(), 1)
        # Test a search that should get zero models.
        self.assertEqual(watson.search("MODEL1", exclude=(TestModel1,)).count(), 0)
        self.assertEqual(watson.search("MODEL2", exclude=(TestModel2,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", exclude=(TestModel2,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE11", exclude=(TestModel1,)).count(), 0)

    def testLimitedModelQuerySet(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE", models=(TestModel1.objects.filter(title__icontains="TITLE"), TestModel2.objects.filter(title__icontains="TITLE"),)).count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", models=(TestModel1.objects.filter(
            title__icontains = "MODEL1",
            description__icontains = "MODEL1",
        ),)).count(), 2)
        self.assertEqual(watson.search("MODEL2", models=(TestModel2.objects.filter(
            title__icontains = "MODEL2",
            description__icontains = "MODEL2",
        ),)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", models=(TestModel1.objects.filter(
            title__icontains = "MODEL1",
        ),)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", models=(TestModel2.objects.filter(
            title__icontains = "MODEL2",
        ),)).count(), 1)
        # Test a search that should get no models.
        self.assertEqual(watson.search("INSTANCE11", models=(TestModel1.objects.filter(
            title__icontains = "MODEL2",
        ),)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", models=(TestModel2.objects.filter(
            title__icontains = "MODEL1",
        ),)).count(), 0)
        
    def testExcludedModelQuerySet(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE", exclude=(TestModel1.objects.filter(title__icontains="FOO"), TestModel2.objects.filter(title__icontains="FOO"),)).count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", exclude=(TestModel1.objects.filter(
            title__icontains = "INSTANCE21",
            description__icontains = "INSTANCE22",
        ),)).count(), 2)
        self.assertEqual(watson.search("MODEL2", exclude=(TestModel2.objects.filter(
            title__icontains = "INSTANCE11",
            description__icontains = "INSTANCE12",
        ),)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", exclude=(TestModel1.objects.filter(
            title__icontains = "MODEL2",
        ),)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=(TestModel2.objects.filter(
            title__icontains = "MODEL1",
        ),)).count(), 1)
        # Test a search that should get no models.
        self.assertEqual(watson.search("INSTANCE11", exclude=(TestModel1.objects.filter(
            title__icontains = "MODEL1",
        ),)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", exclude=(TestModel2.objects.filter(
            title__icontains = "MODEL2",
        ),)).count(), 0)
        
        
class LiveFilterSearchTest(SearchTest):
    
    live_filter = True
    
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
        
    def testCanOverridePublication(self):
        # Unpublish two objects.
        with watson.context():
            self.test11.is_published = False
            self.test11.save()
        # This should still return 4, since we're overriding the publication.
        self.assertEqual(watson.search("tItle Content Description", models=(TestModel2, TestModel1._base_manager.all(),)).count(), 4)