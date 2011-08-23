"""
Multi-table search application for Django, using native database search engines.

Developed by Dave Hall.

<http://www.etianen.com/>
"""

from watson.registration import SearchAdapter, default_search_engine


# The main search method.
search = default_search_engine.search


# Easy registration.
register = default_search_engine.register
unregister = default_search_engine.unregister
is_registered = default_search_engine.is_registered
get_registered_models = default_search_engine.get_registered_models
get_adapter = default_search_engine.get_adapter


# Easy context management.
context = default_search_engine.context
update_index = default_search_engine.update_index