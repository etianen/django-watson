"""
Multi-table search application for Django, using native database search engines.

Developed by Dave Hall.

<http://www.etianen.com/>
"""

from watson.registration import SearchAdapter, register, unregister, is_registered, get_registered_models, search_context_manager, get_backend


# The main search method.
search = get_backend().search


# Easy context management.
context = search_context_manager.context
update_index = search_context_manager.update_index