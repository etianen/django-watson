"""Template helpers used by watsons search."""

from __future__ import unicode_literals

from django import template
from django.contrib.contenttypes.models import ContentType


register = template.Library()


@register.simple_tag(takes_context=True)
def search_results(context, search_results):
    """Renders a list of search results."""
    # Render the template.
    context.push()
    try:
        context.update({
            "search_results": search_results,
            "query": context["query"],
        })
        return template.loader.render_to_string("watson/includes/search_results.html", context.flatten())
    finally:
        context.pop()


@register.simple_tag(takes_context=True)
def search_result_item(context, search_result):
    obj = search_result.object
    content_type = ContentType.objects.get_for_id(search_result.content_type_id)

    params = {
        "app_label": content_type.app_label,
        "model_name": content_type.model,
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
        ), context.flatten())
    finally:
        context.pop()
