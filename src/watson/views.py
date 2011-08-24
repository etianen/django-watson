"""Views used by the built-in site search functionality."""

from django.shortcuts import render

import watson
from watson.models import SearchEntry


def search(request, query_param="q", template_name="watson/result_list.html"):
    """Renders a list of matching search entries."""
    query = request.GET.get(query_param, u"")
    # Check for blank queries.
    if query:
        search_entries = watson.search(query)
    else:
        search_entries = SearchEntry.objects.none()
    # Render the template.
    return render(request, template_name, {
        "result_list": search_entries,
        "query": query,
    })