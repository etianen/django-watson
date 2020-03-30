# coding=utf-8
"""
Tests for django-watson.

Fun fact: The MySQL full text search engine does not support indexing of words
that are 3 letters or fewer. Thus, the standard metasyntactic variables in
these tests have been amended to 'fooo' and 'baar'. Ho hum.
"""

from __future__ import unicode_literals

import json
import string

try:
    from unittest import skipUnless
except ImportError:
    from django.utils.unittest import skipUnless

from django.test import TestCase
from django.core.management import call_command
from django.conf import settings
from django.contrib.auth.models import User
from django import template
from django.utils.encoding import force_str
from django.db.models import Case, When, Value, IntegerField

from watson import search as watson
from watson.models import SearchEntry

from test_watson.models import WatsonTestModel1, WatsonTestModel2, WatsonTestModel3
from test_watson import admin  # Force early registration of all admin models. # noQA


class RegistrationTest(TestCase):
    def testRegistration(self):
        # Register the model and test.
        watson.register(WatsonTestModel1)
        self.assertTrue(watson.is_registered(WatsonTestModel1))
        self.assertRaises(watson.RegistrationError, lambda: watson.register(WatsonTestModel1))
        self.assertTrue(WatsonTestModel1 in watson.get_registered_models())
        self.assertTrue(isinstance(watson.get_adapter(WatsonTestModel1), watson.SearchAdapter))
        # Unregister the model and text.
        watson.unregister(WatsonTestModel1)
        self.assertFalse(watson.is_registered(WatsonTestModel1))
        self.assertRaises(watson.RegistrationError, lambda: watson.unregister(WatsonTestModel1))
        self.assertTrue(WatsonTestModel1 not in watson.get_registered_models())
        self.assertRaises(watson.RegistrationError, lambda: isinstance(watson.get_adapter(WatsonTestModel1)))


complex_registration_search_engine = watson.SearchEngine("restricted")


class InstallUninstallTestBase(TestCase):

    @skipUnless(watson.get_backend().requires_installation, "search backend does not require installation")
    def testUninstallAndInstall(self):
        backend = watson.get_backend()
        call_command("uninstallwatson", verbosity=0)
        self.assertFalse(backend.is_installed())
        call_command("installwatson", verbosity=0)
        self.assertTrue(backend.is_installed())


class SearchTestBase(TestCase):

    model1 = WatsonTestModel1

    model2 = WatsonTestModel2

    model3 = WatsonTestModel3

    def setUp(self):
        # If migrations are off, then this is needed to get the indices installed. It has to
        # be called in the setUp() method, but multiple invocations should be safe.
        call_command("installwatson", verbosity=0)
        # Remove all the current registered models.
        self.registered_models = watson.get_registered_models()
        for model in self.registered_models:
            watson.unregister(model)
        # Register the test models.
        watson.register(self.model1)
        watson.register(self.model2, exclude=("id",))
        watson.register(self.model3, exclude=("id",))
        complex_registration_search_engine.register(
            WatsonTestModel1, exclude=("content", "description",), store=("is_published",)
        )
        complex_registration_search_engine.register(
            WatsonTestModel2, fields=("title",)
        )
        # Create some test models.
        self.test11 = WatsonTestModel1.objects.create(
            title="title model1 instance11",
            content="content model1 instance11",
            description="description model1 instance11",
        )
        self.test12 = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance12",
            description="description model1 instance12",
        )
        self.test21 = WatsonTestModel2.objects.create(
            title="title model2 instance21",
            content="content model2 instance21",
            description="description model2 instance21",
        )
        self.test22 = WatsonTestModel2.objects.create(
            title="title model2 instance22",
            content="content model2 instance22",
            description="description model2 instance22",
        )
        self.test31 = WatsonTestModel3.objects.create(
            title="title model3 instance31",
            content="content model3 instance31",
            description="description model3 instance31",
        )
        self.test32 = WatsonTestModel3.objects.create(
            title="title model3 instance32",
            content="content model3 instance32",
            description="description model3 instance32",
        )

    def tearDown(self):
        # Re-register the old registered models.
        for model in self.registered_models:
            watson.register(model)
        # Unregister the test models.
        watson.unregister(self.model1)
        watson.unregister(self.model2)
        watson.unregister(self.model3)
        complex_registration_search_engine.unregister(WatsonTestModel1)
        complex_registration_search_engine.unregister(WatsonTestModel2)
        # Delete the test models.
        WatsonTestModel1.objects.all().delete()
        WatsonTestModel2.objects.all().delete()
        del self.test11
        del self.test12
        del self.test21
        del self.test22
        # Delete the search index.
        SearchEntry.objects.all().delete()


class InternalsTest(SearchTestBase):

    def testSearchEntriesCreated(self):
        self.assertEqual(SearchEntry.objects.filter(engine_slug="default").count(), 6)

    def testBuildWatsonForModelCommand(self):
        # Hack a change into the model using a bulk update, which doesn't send signals.
        WatsonTestModel1.objects.filter(id=self.test11.id).update(title="fooo1_selective")
        WatsonTestModel2.objects.filter(id=self.test21.id).update(title="fooo2_selective")
        WatsonTestModel3.objects.filter(id=self.test31.id).update(title="fooo3_selective")
        # Test that no update has happened.
        self.assertEqual(watson.search("fooo1_selective").count(), 0)
        self.assertEqual(watson.search("fooo2_selective").count(), 0)
        self.assertEqual(watson.search("fooo3_selective").count(), 0)
        # Run the rebuild command.
        call_command("buildwatson", "test_watson.WatsonTestModel1", verbosity=0)
        # Test that the update is now applied to selected model.
        self.assertEqual(watson.search("fooo1_selective").count(), 1)
        self.assertEqual(watson.search("fooo2_selective").count(), 0)
        self.assertEqual(watson.search("fooo3_selective").count(), 0)
        call_command(
            "buildwatson",
            "test_watson.WatsonTestModel1", "test_watson.WatsonTestModel2", "test_watson.WatsonTestModel3",
            verbosity=0,
        )
        # Test that the update is now applied to multiple selected models.
        self.assertEqual(watson.search("fooo1_selective").count(), 1)
        self.assertEqual(watson.search("fooo2_selective").count(), 1)
        self.assertEqual(watson.search("fooo3_selective").count(), 1)

    def testBuildWatsonCommand(self):
        # Hack a change into the model using a bulk update, which doesn't send signals.
        WatsonTestModel1.objects.filter(id=self.test11.id).update(title="fooo1")
        WatsonTestModel2.objects.filter(id=self.test21.id).update(title="fooo2")
        WatsonTestModel3.objects.filter(id=self.test31.id).update(title="fooo3")
        # Test that no update has happened.
        self.assertEqual(watson.search("fooo1").count(), 0)
        self.assertEqual(watson.search("fooo2").count(), 0)
        self.assertEqual(watson.search("fooo3").count(), 0)
        # Run the rebuild command.
        call_command("buildwatson", verbosity=0)
        # Test that the update is now applied.
        self.assertEqual(watson.search("fooo1").count(), 1)
        self.assertEqual(watson.search("fooo2").count(), 1)
        self.assertEqual(watson.search("fooo3").count(), 1)

    def testUpdateSearchIndex(self):
        # Update a model and make sure that the search results match.
        self.test11.title = "fooo"
        self.test11.save()
        # Test a search that should get one model.
        exact_search = watson.search("fooo")
        self.assertEqual(len(exact_search), 1)
        self.assertEqual(exact_search[0].title, "fooo")
        # Delete a model and make sure that the search results match.
        self.test11.delete()
        self.assertEqual(watson.search("fooo").count(), 0)

    def testSearchIndexUpdateDeferredByContext(self):
        with watson.update_index():
            self.test11.title = "fooo"
            self.test11.save()
            self.assertEqual(watson.search("fooo").count(), 0)
        self.assertEqual(watson.search("fooo").count(), 1)

    def testSearchIndexUpdateAbandonedOnError(self):
        try:
            with watson.update_index():
                self.test11.title = "fooo"
                self.test11.save()
                raise Exception("Foo")
        except Exception:
            pass
        # Test a search that should get not model.
        self.assertEqual(watson.search("fooo").count(), 0)

    def testSkipSearchIndexUpdate(self):
        with watson.skip_index_update():
            self.test11.title = "fooo"
            self.test11.save()
        # Test a search that should get not model.
        self.assertEqual(watson.search("fooo").count(), 0)

    def testNestedSkipInUpdateContext(self):
        with watson.update_index():
            self.test21.title = "baar"
            self.test21.save()
            with watson.skip_index_update():
                self.test11.title = "fooo"
                self.test11.save()
        # We should get "baar", but not "fooo"
        self.assertEqual(watson.search("fooo").count(), 0)
        self.assertEqual(watson.search("baar").count(), 1)

    def testNestedUpdateInSkipContext(self):
        with watson.skip_index_update():
            self.test21.title = "baar"
            self.test21.save()
            with watson.update_index():
                self.test11.title = "fooo"
                self.test11.save()
        # We should get "fooo", but not "baar"
        self.assertEqual(watson.search("fooo").count(), 1)
        self.assertEqual(watson.search("baar").count(), 0)

    def testFixesDuplicateSearchEntries(self):
        search_entries = SearchEntry.objects.filter(engine_slug="default")
        # Duplicate a couple of search entries.
        for search_entry in search_entries.all()[:2]:
            search_entry.id = None
            search_entry.save()
        # Make sure that we have eight (including duplicates).
        self.assertEqual(search_entries.all().count(), 8)
        # Run the rebuild command.
        call_command("buildwatson", verbosity=0)
        # Make sure that we have six again (including duplicates).
        self.assertEqual(search_entries.all().count(), 6)

    def testEmptyFilterGivesAllResults(self):
        for model in (WatsonTestModel1, WatsonTestModel2, WatsonTestModel3):
            self.assertEqual(watson.filter(model, "").count(), 2)
            self.assertEqual(watson.filter(model, " ").count(), 2)

    def testFilter(self):
        for model in (WatsonTestModel1, WatsonTestModel2, WatsonTestModel3):
            # Test can find all.
            self.assertEqual(watson.filter(model, "TITLE").count(), 2)
        # Test can find a specific one.
        obj = watson.filter(WatsonTestModel1, "INSTANCE12").get()
        self.assertTrue(isinstance(obj, WatsonTestModel1))
        self.assertEqual(obj.title, "title model1 instance12")
        # Test can do filter on a queryset.
        obj = watson.filter(WatsonTestModel1.objects.filter(title__icontains="TITLE"), "INSTANCE12").get()
        self.assertTrue(isinstance(obj, WatsonTestModel1))
        self.assertEqual(obj.title, "title model1 instance12")

    @skipUnless(watson.get_backend().supports_prefix_matching, "Search backend does not support prefix matching.")
    def testPrefixFilter(self):
        self.assertEqual(watson.filter(WatsonTestModel1, "INSTAN").count(), 2)


class SearchTest(SearchTestBase):

    def testEscaping(self):
        # This must not crash the database with a syntax error.
        list(watson.search(string.printable))

    def emptySearchTextGivesNoResults(self):
        self.assertEqual(watson.search("").count(), 0)
        self.assertEqual(watson.search(" ").count(), 0)

    def testMultiTableSearch(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE").count(), 6)
        self.assertEqual(watson.search("CONTENT").count(), 6)
        self.assertEqual(watson.search("DESCRIPTION").count(), 6)
        self.assertEqual(watson.search("TITLE CONTENT DESCRIPTION").count(), 6)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1").count(), 2)
        self.assertEqual(watson.search("MODEL2").count(), 2)
        self.assertEqual(watson.search("MODEL3").count(), 2)
        self.assertEqual(watson.search("TITLE MODEL1").count(), 2)
        self.assertEqual(watson.search("TITLE MODEL2").count(), 2)
        self.assertEqual(watson.search("TITLE MODEL3").count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11").count(), 1)
        self.assertEqual(watson.search("INSTANCE21").count(), 1)
        self.assertEqual(watson.search("INSTANCE31").count(), 1)
        self.assertEqual(watson.search("TITLE INSTANCE11").count(), 1)
        self.assertEqual(watson.search("TITLE INSTANCE21").count(), 1)
        self.assertEqual(watson.search("TITLE INSTANCE31").count(), 1)
        # Test a search that should get zero models.
        self.assertEqual(watson.search("FOOO").count(), 0)
        self.assertEqual(watson.search("FOOO INSTANCE11").count(), 0)
        self.assertEqual(watson.search("MODEL2 INSTANCE11").count(), 0)

    def testSearchWithAccent(self):
        WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance13 café",
            description="description model1 instance13",
        )
        self.assertEqual(watson.search("café").count(), 1)

    def testSearchWithSpecialChars(self):
        WatsonTestModel1.objects.all().delete()

        x = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance13 d'Argent",
            description="description model1 instance13",
        )
        self.assertEqual(watson.search("d'Argent").count(), 1)
        x.delete()

        x = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="'content model1 instance13",
            description="description model1 instance13",
        )
        # Some database engines ignore leading apostrophes, some count them.
        self.assertTrue(watson.search("'content").exists())
        x.delete()

        x = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance13 d'Argent",
            description="description abcd&efgh",
        )
        self.assertEqual(watson.search("abcd&efgh").count(), 1)
        x.delete()

        x = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance13 d'Argent",
            description="description abcd.efgh",
        )
        self.assertEqual(watson.search("abcd.efgh").count(), 1)
        x.delete()

        x = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance13 d'Argent",
            description="description abcd,efgh",
        )
        self.assertEqual(watson.search("abcd,efgh").count(), 1)
        x.delete()

        x = WatsonTestModel1.objects.create(
            title="title model1 instance12",
            content="content model1 instance13 d'Argent",
            description="description abcd@efgh",
        )
        self.assertEqual(watson.search("abcd@efgh").count(), 1)
        x.delete()

    @skipUnless(
        watson.get_backend().supports_prefix_matching,
        "Search backend does not support prefix matching."
    )
    def testMultiTablePrefixSearch(self):
        self.assertEqual(watson.search("DESCR").count(), 6)

    def testLimitedModelList(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE", models=(WatsonTestModel1, WatsonTestModel2)).count(), 4)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", models=(WatsonTestModel1, WatsonTestModel2)).count(), 2)
        self.assertEqual(watson.search("MODEL1", models=(WatsonTestModel1,)).count(), 2)
        self.assertEqual(watson.search("MODEL2", models=(WatsonTestModel1, WatsonTestModel2)).count(), 2)
        self.assertEqual(watson.search("MODEL2", models=(WatsonTestModel2,)).count(), 2)
        self.assertEqual(watson.search("MODEL3", models=(WatsonTestModel2, WatsonTestModel3)).count(), 2)
        self.assertEqual(watson.search("MODEL3", models=(WatsonTestModel3,)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", models=(WatsonTestModel1, WatsonTestModel2)).count(), 1)
        self.assertEqual(watson.search("INSTANCE11", models=(WatsonTestModel1,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", models=(WatsonTestModel1, WatsonTestModel2,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", models=(WatsonTestModel2,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE31", models=(WatsonTestModel2, WatsonTestModel3,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE31", models=(WatsonTestModel3,)).count(), 1)
        # Test a search that should get zero models.
        self.assertEqual(watson.search("MODEL1", models=(WatsonTestModel2,)).count(), 0)
        self.assertEqual(watson.search("MODEL2", models=(WatsonTestModel1,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", models=(WatsonTestModel1,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE11", models=(WatsonTestModel2,)).count(), 0)

    def testExcludedModelList(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search("TITLE", exclude=()).count(), 6)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", exclude=()).count(), 2)
        self.assertEqual(watson.search("MODEL1", exclude=(WatsonTestModel2,)).count(), 2)
        self.assertEqual(watson.search("MODEL2", exclude=()).count(), 2)
        self.assertEqual(watson.search("MODEL2", exclude=(WatsonTestModel1,)).count(), 2)
        self.assertEqual(watson.search("MODEL3", exclude=()).count(), 2)
        self.assertEqual(watson.search("MODEL3", exclude=(WatsonTestModel1,)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", exclude=()).count(), 1)
        self.assertEqual(watson.search("INSTANCE11", exclude=(WatsonTestModel2,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=()).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=(WatsonTestModel1,)).count(), 1)
        self.assertEqual(watson.search("INSTANCE31", exclude=()).count(), 1)
        self.assertEqual(watson.search("INSTANCE31", exclude=(WatsonTestModel1,)).count(), 1)
        # Test a search that should get zero models.
        self.assertEqual(watson.search("MODEL1", exclude=(WatsonTestModel1,)).count(), 0)
        self.assertEqual(watson.search("MODEL2", exclude=(WatsonTestModel2,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", exclude=(WatsonTestModel2,)).count(), 0)
        self.assertEqual(watson.search("INSTANCE11", exclude=(WatsonTestModel1,)).count(), 0)

    def testLimitedModelQuerySet(self):
        # Test a search that should get all models.
        self.assertEqual(watson.search(
            "TITLE",
            models=(
                WatsonTestModel1.objects.filter(title__icontains="TITLE"),
                WatsonTestModel2.objects.filter(title__icontains="TITLE"),
            )
        ).count(), 4)
        # Test a search that should get two models.
        self.assertEqual(
            watson.search(
                "MODEL1",
                models=(WatsonTestModel1.objects.filter(
                    title__icontains="MODEL1",
                    description__icontains="MODEL1",
                ),)
            ).count(), 2)
        self.assertEqual(watson.search("MODEL2", models=(WatsonTestModel2.objects.filter(
            title__icontains="MODEL2",
            description__icontains="MODEL2",
        ),)).count(), 2)
        self.assertEqual(watson.search("MODEL3", models=(WatsonTestModel3.objects.filter(
            title__icontains="MODEL3",
            description__icontains="MODEL3",
        ),)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", models=(WatsonTestModel1.objects.filter(
            title__icontains="MODEL1",
        ),)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", models=(WatsonTestModel2.objects.filter(
            title__icontains="MODEL2",
        ),)).count(), 1)
        self.assertEqual(watson.search("INSTANCE31", models=(WatsonTestModel3.objects.filter(
            title__icontains="MODEL3",
        ),)).count(), 1)
        # Test a search that should get no models.
        self.assertEqual(watson.search("INSTANCE11", models=(WatsonTestModel1.objects.filter(
            title__icontains="MODEL2",
        ),)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", models=(WatsonTestModel2.objects.filter(
            title__icontains="MODEL1",
        ),)).count(), 0)

    def testExcludedModelQuerySet(self):
        # Test a search that should get all models.
        self.assertEqual(
            watson.search(
                "TITLE",
                exclude=(
                    WatsonTestModel1.objects.filter(title__icontains="FOOO"),
                    WatsonTestModel2.objects.filter(title__icontains="FOOO"),)
            ).count(), 6)
        # Test a search that should get two models.
        self.assertEqual(watson.search("MODEL1", exclude=(WatsonTestModel1.objects.filter(
            title__icontains="INSTANCE21",
            description__icontains="INSTANCE22",
        ),)).count(), 2)
        self.assertEqual(watson.search("MODEL2", exclude=(WatsonTestModel2.objects.filter(
            title__icontains="INSTANCE11",
            description__icontains="INSTANCE12",
        ),)).count(), 2)
        self.assertEqual(watson.search("MODEL3", exclude=(WatsonTestModel3.objects.filter(
            title__icontains="INSTANCE11",
            description__icontains="INSTANCE12",
        ),)).count(), 2)
        # Test a search that should get one model.
        self.assertEqual(watson.search("INSTANCE11", exclude=(WatsonTestModel1.objects.filter(
            title__icontains="MODEL2",
        ),)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=(WatsonTestModel2.objects.filter(
            title__icontains="MODEL1",
        ),)).count(), 1)
        self.assertEqual(watson.search("INSTANCE21", exclude=(WatsonTestModel3.objects.filter(
            title__icontains="MODEL1",
        ),)).count(), 1)
        # Test a search that should get no models.
        self.assertEqual(watson.search("INSTANCE11", exclude=(WatsonTestModel1.objects.filter(
            title__icontains="MODEL1",
        ),)).count(), 0)
        self.assertEqual(watson.search("INSTANCE21", exclude=(WatsonTestModel2.objects.filter(
            title__icontains="MODEL2",
        ),)).count(), 0)

    def testKitchenSink(self):
        """For sanity, let's just test everything together in one giant search of doom!"""
        self.assertEqual(watson.search(
            "INSTANCE11",
            models=(
                WatsonTestModel1.objects.filter(title__icontains="INSTANCE11"),
                WatsonTestModel2.objects.filter(title__icontains="TITLE"),
            ),
            exclude=(
                WatsonTestModel1.objects.filter(title__icontains="MODEL2"),
                WatsonTestModel2.objects.filter(title__icontains="MODEL1"),
            )
        ).get().title, "title model1 instance11")

    def testReferencingWatsonRankInAnnotations(self):
        """We should be able to reference watson_rank from annotate expressions"""
        entries = watson.search("model1").annotate(
            relevant=Case(
                When(watson_rank__gt=1.0, then=Value(1)),
                default_value=Value(0),
                output_field=IntegerField()
            )
        )

        # watson_rank does not return the same value across backends, so we
        # can't hard code what those will be. In some cases (e.g. the regex
        # backend) all ranking is hard coded to 1.0. That doesn't matter - we
        # just want to make sure that Django is able to construct a valid query
        for entry in entries:
            if entry.watson_rank > 1.0:
                self.assertTrue(entry.relevant)
            else:
                self.assertFalse(entry.relevant)


class LiveFilterSearchTest(SearchTest):

    model1 = WatsonTestModel1.objects.filter(is_published=True)

    model2 = WatsonTestModel2.objects.filter(is_published=True)

    def testUnpublishedModelsNotFound(self):
        # Make sure that there are four to find!
        self.assertEqual(watson.search("tItle Content Description").count(), 6)
        # Unpublish some objects.
        self.test11.is_published = False
        self.test11.save()
        self.test21.is_published = False
        self.test21.save()
        self.test31.is_published = False
        self.test31.save()
        # This should return 4, but two of them are unpublished.
        self.assertEqual(watson.search("tItle Content Description").count(), 4)

    def testCanOverridePublication(self):
        # Unpublish two objects.
        self.test11.is_published = False
        self.test11.save()
        # This should still return 4, since we're overriding the publication.
        self.assertEqual(watson.search(
            "tItle Content Description",
            models=(WatsonTestModel2, WatsonTestModel1._base_manager.all(),)
        ).count(), 4)


class RankingTest(SearchTestBase):

    def setUp(self):
        super(RankingTest, self).setUp()
        self.test11.title += " fooo baar fooo"
        self.test11.save()
        self.test12.content += " fooo baar"
        self.test12.save()

    def testRankingParamPresentOnSearch(self):
        self.assertGreater(watson.search("TITLE")[0].watson_rank, 0)

    def testRankingParamPresentOnFilter(self):
        self.assertGreater(watson.filter(WatsonTestModel1, "TITLE")[0].watson_rank, 0)

    def testRankingParamAbsentOnSearch(self):
        self.assertRaises(AttributeError, lambda: watson.search("TITLE", ranking=False)[0].watson_rank)

    def testRankingParamAbsentOnFilter(self):
        self.assertRaises(
            AttributeError,
            lambda: watson.filter(WatsonTestModel1, "TITLE", ranking=False)[0].watson_rank
        )

    @skipUnless(watson.get_backend().supports_ranking, "search backend does not support ranking")
    def testRankingWithSearch(self):
        self.assertEqual(
            [entry.title for entry in watson.search("FOOO")],
            ["title model1 instance11 fooo baar fooo", "title model1 instance12"]
        )

    @skipUnless(watson.get_backend().supports_ranking, "search backend does not support ranking")
    def testRankingWithFilter(self):
        self.assertEqual(
            [entry.title for entry in watson.filter(WatsonTestModel1, "FOOO")],
            ["title model1 instance11 fooo baar fooo", "title model1 instance12"]
        )


class ComplexRegistrationTest(SearchTestBase):

    def testMetaStored(self):
        self.assertEqual(complex_registration_search_engine.search("instance11")[0].meta["is_published"], True)

    def testMetaNotStored(self):
        self.assertRaises(
            KeyError,
            lambda: complex_registration_search_engine.search("instance21")[0].meta["is_published"]
        )

    def testFieldsExcludedOnSearch(self):
        self.assertEqual(complex_registration_search_engine.search("TITLE").count(), 4)
        self.assertEqual(complex_registration_search_engine.search("CONTENT").count(), 0)
        self.assertEqual(complex_registration_search_engine.search("DESCRIPTION").count(), 0)

    def testFieldsExcludedOnFilter(self):
        self.assertEqual(complex_registration_search_engine.filter(WatsonTestModel1, "TITLE").count(), 2)
        self.assertEqual(complex_registration_search_engine.filter(WatsonTestModel1, "CONTENT").count(), 0)
        self.assertEqual(complex_registration_search_engine.filter(WatsonTestModel1, "DESCRIPTION").count(), 0)
        self.assertEqual(complex_registration_search_engine.filter(WatsonTestModel2, "TITLE").count(), 2)
        self.assertEqual(complex_registration_search_engine.filter(WatsonTestModel2, "CONTENT").count(), 0)
        self.assertEqual(complex_registration_search_engine.filter(WatsonTestModel2, "DESCRIPTION").count(), 0)


class AdminIntegrationTest(SearchTestBase):

    def setUp(self):
        super(AdminIntegrationTest, self).setUp()
        self.user = User(
            username="foo",
            is_staff=True,
            is_superuser=True,
        )
        self.user.set_password("bar")
        self.user.save()

    @skipUnless("django.contrib.admin" in settings.INSTALLED_APPS, "Django admin site not installed")
    def testAdminIntegration(self):
        # Log the user in.
        self.client.login(
            username="foo",
            password="bar",
        )
        # Test a search with no query.
        response = self.client.get("/admin/test_watson/watsontestmodel1/")
        self.assertContains(response, "instance11")
        self.assertContains(response, "instance12")
        self.assertContains(response, "searchbar")  # Ensure that the search bar renders.
        # Test a search for all the instances.
        response = self.client.get("/admin/test_watson/watsontestmodel1/?q=title content description")
        self.assertContains(response, "instance11")
        self.assertContains(response, "instance12")
        # Test a search for half the instances.
        response = self.client.get("/admin/test_watson/watsontestmodel1/?q=instance11")
        self.assertContains(response, "instance11")
        self.assertNotContains(response, "instance12")

    def tearDown(self):
        super(AdminIntegrationTest, self).tearDown()
        self.user.delete()
        del self.user


class SiteSearchTest(SearchTestBase):
    def testSiteSearch(self):
        # Test a search than should find everything.
        response = self.client.get("/simple/?q=title")
        self.assertContains(response, "instance11")
        self.assertContains(response, "instance12")
        self.assertContains(response, "instance21")
        self.assertContains(response, "instance22")
        self.assertTemplateUsed(response, "watson/search_results.html")
        # Test a search that should find one thing.
        response = self.client.get("/simple/?q=instance11")
        self.assertContains(response, "instance11")
        self.assertNotContains(response, "instance12")
        self.assertNotContains(response, "instance21")
        self.assertNotContains(response, "instance22")
        # Test a search that should find nothing.
        response = self.client.get("/simple/?q=fooo")
        self.assertNotContains(response, "instance11")
        self.assertNotContains(response, "instance12")
        self.assertNotContains(response, "instance21")
        self.assertNotContains(response, "instance22")

    def testSiteSearchJSON(self):
        # Test a search that should find everything.
        response = self.client.get("/simple/json/?q=title")
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        results = set(result["title"] for result in json.loads(force_str(response.content))["results"])
        self.assertEqual(len(results), 6)
        self.assertTrue("title model1 instance11" in results)
        self.assertTrue("title model1 instance12" in results)
        self.assertTrue("title model2 instance21" in results)
        self.assertTrue("title model2 instance22" in results)
        self.assertTrue("title model3 instance31" in results)
        self.assertTrue("title model3 instance32" in results)

    def testSiteSearchCustom(self):
        # Test a search than should find everything.
        response = self.client.get("/custom/?fooo=title")
        self.assertContains(response, "instance11")
        self.assertContains(response, "instance12")
        self.assertContains(response, "instance21")
        self.assertContains(response, "instance22")
        self.assertTemplateUsed(response, "watson/search_results.html")
        # Test that the extra context is included.
        self.assertEqual(response.context["foo"], "bar")
        self.assertEqual(response.context["foo2"], "bar2")
        # Test that pagination is included.
        self.assertEqual(response.context["paginator"].num_pages, 1)
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(response.context["search_results"], response.context["page_obj"].object_list)
        # Test a request for an empty page.
        try:
            response = self.client.get("/custom/?fooo=title&page=10")
        except template.TemplateDoesNotExist as ex:
            # No 404 template defined.
            self.assertEqual(ex.args[0], "404.html")
        else:
            self.assertEqual(response.status_code, 404)
        # Test a requet for the last page.
        response = self.client.get("/custom/?fooo=title&page=last")
        self.assertEqual(response.context["paginator"].num_pages, 1)
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(response.context["search_results"], response.context["page_obj"].object_list)
        # Test a search that should find nothing.
        response = self.client.get("/custom/?q=fooo")
        self.assertRedirects(response, "/simple/")

    def testSiteSearchCustomJSON(self):
        # Test a search that should find everything.
        response = self.client.get("/custom/json/?fooo=title&page=last")
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        results = set(result["title"] for result in json.loads(force_str(response.content))["results"])
        self.assertEqual(len(results), 6)
        self.assertTrue("title model1 instance11" in results)
        self.assertTrue("title model1 instance12" in results)
        self.assertTrue("title model2 instance21" in results)
        self.assertTrue("title model2 instance22" in results)
        self.assertTrue("title model3 instance31" in results)
        self.assertTrue("title model3 instance32" in results)
        # Test a search with an invalid page.
        response = self.client.get("/custom/json/?fooo=title&page=200")
        self.assertEqual(response.status_code, 404)
