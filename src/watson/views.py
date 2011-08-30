"""Views used by the built-in site search functionality."""

from django.shortcuts import render, redirect

import watson
from watson.models import SearchEntry


def search(request, query_param="q", template_name="watson/search_results.html",
           empty_query_redirect=None, models=(), exclude=(), extra_context=None):
    """Renders a list of matching search entries."""
    query = request.GET.get(query_param, u"")
    # Check for blank queries.
    if query:
        search_results = watson.search(query, models=models, exclude=exclude)
    else:
        if empty_query_redirect:
            return redirect(empty_query_redirect)
        search_results = SearchEntry.objects.none()
    # Update the context.
    context = {
        "search_results": search_results,
        "query": query,
    }
    if extra_context:
        for key, value in extra_context.iteritems():
            if callable(value):
                value = value()
            context[key] = value
    # Render the template.
    return render(request, template_name, context)