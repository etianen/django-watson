"""Views used by the built-in site search functionality."""

from django.core.paginator import Paginator, InvalidPage
from django.shortcuts import render, redirect
from django.http import Http404

import watson
from watson.models import SearchEntry


def search(request, query_param="q", template_name="watson/search_results.html",
           empty_query_redirect=None, models=(), exclude=(), extra_context=None,
           context_object_name="search_results", paginate_by=None, page=None,
           page_param="page", last_page_value="last"):
    """Renders a list of matching search entries."""
    query = request.GET.get(query_param, u"")
    # Check for blank queries.
    if query:
        search_results = watson.search(query, models=models, exclude=exclude)
    else:
        if empty_query_redirect:
            return redirect(empty_query_redirect)
        search_results = SearchEntry.objects.none()
    # Start creating the context.
    context = {
        "query": query,
    }
    # Apply pagination.
    if paginate_by is None:
        context[context_object_name] = search_results
    else:
        paginator = Paginator(search_results, per_page=paginate_by, allow_empty_first_page=True)
        page = page or request.GET.get(page_param, 1)
        if page == last_page_value:
            page = paginator.num_pages
        try:
            page_obj = paginator.page(page)
        except InvalidPage:
            raise Http404(u"There are no items on page {page}".format(
                page = page,
            ))
        context[context_object_name] = search_results
        context["paginator"] = paginator
        context["page_obj"] = page_obj
        context[context_object_name] = page_obj.object_list
    # Update the context.
    if extra_context:
        for key, value in extra_context.iteritems():
            if callable(value):
                value = value()
            context[key] = value
    # Render the template.
    return render(request, template_name, context)