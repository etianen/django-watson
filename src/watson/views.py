"""Views used by the built-in site search functionality."""

from django.core.paginator import Paginator, InvalidPage
from django.shortcuts import render, redirect
from django.http import Http404, HttpResponse
from django.utils import simplejson as json

import watson


def _get_search_results(request, kwargs):
    """Performs the search and pagination of the results."""
    # Extract configuration.
    query_param = kwargs.get("query_param", "q")
    models = kwargs.get("models", ())
    exclude = kwargs.get("exclude", ())
    paginate_by = kwargs.get("paginate_by")
    page = kwargs.get("page", None)
    page_param = kwargs.get("page_param", "page")
    last_page_value = kwargs.get("last_page_value", "last")
    # Get the query.
    query = request.GET.get(query_param, u"").strip()
    search_results = watson.search(query, models=models, exclude=exclude)
    # Process the pagination.
    if paginate_by is None:
        return query, search_results, None, None
    else:
        paginator = Paginator(search_results, per_page=paginate_by, allow_empty_first_page=True)
        page = page or request.GET.get(page_param, 1)
        if page == last_page_value:
            page = paginator.num_pages
        page_obj = paginator.page(page)
        return query, page_obj.object_list, paginator, page_obj


def search(request, template_name="watson/search_results.html", empty_query_redirect=None,
    extra_context=None, context_object_name="search_results", **kwargs):
    """Renders a list of matching search entries."""
    # Get the search results.
    try:
        query, search_results, paginator, page_obj = _get_search_results(request, kwargs)
    except InvalidPage:
        raise Http404("There are no items on that page")
    # Process empty query redirects.
    if not query and empty_query_redirect:
        return redirect(empty_query_redirect)
    # Start creating the context.
    context = {
        "query": query,
        "paginator": paginator,
        "page_obj": page_obj,
        context_object_name: search_results,
    }
    # Update the context.
    if extra_context:
        for key, value in extra_context.iteritems():
            if callable(value):
                value = value()
            context[key] = value
    # Render the template.
    return render(request, template_name, context)
    
    
def search_json(request, **kwargs):
    """Renders a json representation of matching search entries."""
    # Get the search results.
    try:
        _, search_results, _, _ = _get_search_results(request, kwargs)
    except InvalidPage:
        search_results = ()
    # Render the payload.
    content = json.dumps({
        "results": [
            {
                "title": result.title,
                "description": result.description,
                "url": result.url,
                "meta": result.meta,
            } for result in search_results
        ]
    }).encode("utf-8")
    # Generate the response.
    response = HttpResponse(content)
    response["Content-Type"] = "application/json; charset=utf-8"
    response["Content-Length"] = len(content)
    return response