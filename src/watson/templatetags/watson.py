"""Template helpers used by watsons search."""

from __future__ import unicode_literals

from django import template
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

register = template.Library()


@register.simple_tag(takes_context=True)
def search_results(context, search_results):
    """Renders a list of search results."""
    # Prefetch related for speed, if available.
    if hasattr(search_results, "prefetch_related"):
        search_results = search_results.prefetch_related("object")
	paginator = Paginator(search_results, context["view"].paginate_by)
	page = context["view"].request.GET.get('page')
	try:
        	search_results = paginator.page(page)
    	except PageNotAnInteger:
        	search_results = paginator.page(1)
    	except EmptyPage:
        	search_results = paginator.page(paginator.num_pages)
    # Render the template.
    context.push()
    try:
        context.update({
            "search_results": search_results,
            "query": context["query"],
	    "page": context["view"].request.GET.get('page'),
        })
	#import pdb; pdb.set_trace()
        return template.loader.render_to_string("watson/includes/search_results.html", context)
    finally:
        context.pop()
    
    
@register.simple_tag(takes_context=True)
def search_result_item(context, search_result):
    obj = search_result.object
    params = {
        "app_label": obj._meta.app_label,
        "model_name": obj.__class__.__name__.lower(),
    }
    # Render the template.
    context.push()
    try:
        context.update({
            "obj": obj,
            "result": search_result,
            "query": context["query"],
        })
        return template.loader.render_to_string((
            "watson/includes/search_result_{app_label}_{model_name}.html".format(**params),
            "watson/includes/search_result_{app_label}.html".format(**params),
            "watson/includes/search_result_item.html",
        ), context)
    finally:
        context.pop()
