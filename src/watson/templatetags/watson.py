"""Template helpers used by watsons search."""

from __future__ import unicode_literals

from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def search_results(context, search_results):
    """Renders a list of search results."""
    # Prefetch related for speed, if available.
    if hasattr(search_results, "prefetch_related"):
        search_results = search_results.prefetch_related("object")
    # Render the template.
    context.push()
    try:
        context.update({
            "search_results": search_results,
            "query": context["query"],
        })
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
