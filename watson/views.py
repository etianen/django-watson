"""Views used by the built-in site search functionality."""

from __future__ import unicode_literals

import json

from django.shortcuts import redirect
from django.http import HttpResponse
from django.views import generic
from django.views.generic.list import BaseListView

from watson import search as watson


class SearchMixin(object):

    """Base mixin for search views."""

    context_object_name = "search_results"

    query_param = "q"

    def get_query_param(self):
        """Returns the query parameter to use in the request GET dictionary."""
        return self.query_param

    models = ()

    def get_models(self):
        """Returns the models to use in the query."""
        return self.models

    exclude = ()

    def get_exclude(self):
        """Returns the models to exclude from the query."""
        return self.exclude

    def get_queryset(self):
        """Returns the initial queryset."""
        return watson.search(self.query, models=self.get_models(), exclude=self.get_exclude())

    def get_query(self, request):
        """Parses the query from the request."""
        return request.GET.get(self.get_query_param(), "").strip()

    empty_query_redirect = None

    def get_empty_query_redirect(self):
        """Returns the URL to redirect an empty query to, or None."""
        return self.empty_query_redirect

    extra_context = {}

    def get_extra_context(self):
        """
        Returns any extra context variables.

        Required for backwards compatibility with old function-based views.
        """
        return self.extra_context

    def get_context_data(self, **kwargs):
        """Generates context variables."""
        context = super(SearchMixin, self).get_context_data(**kwargs)
        context["query"] = self.query
        # Process extra context.
        for key, value in self.get_extra_context().items():
            if callable(value):
                value = value()
            context[key] = value
        return context

    def get(self, request, *args, **kwargs):
        """Performs a GET request."""
        self.query = self.get_query(request)
        if not self.query:
            empty_query_redirect = self.get_empty_query_redirect()
            if empty_query_redirect:
                return redirect(empty_query_redirect)
        return super(SearchMixin, self).get(request, *args, **kwargs)


class SearchView(SearchMixin, generic.ListView):

    """View that performs a search and returns the search results."""

    template_name = "watson/search_results.html"


class SearchApiView(SearchMixin, BaseListView):

    """A JSON-based search API."""

    def render_to_response(self, context, **response_kwargs):
        """Renders the search results to the response."""
        content = json.dumps({
            "results": [
                {
                    "title": result.title,
                    "description": result.description,
                    "url": result.url,
                    "meta": result.meta,
                } for result in context[self.get_context_object_name(self.get_queryset())]
            ]
        }).encode("utf-8")
        # Generate the response.
        response = HttpResponse(content, **response_kwargs)
        response["Content-Type"] = "application/json; charset=utf-8"
        response["Content-Length"] = len(content)
        return response


# Older function-based views.

def search(request, **kwargs):
    """Renders a page of search results."""
    return SearchView.as_view(**kwargs)(request)


def search_json(request, **kwargs):
    """Renders a JSON representation of matching search entries."""
    return SearchApiView.as_view(**kwargs)(request)
