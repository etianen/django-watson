"""
Multi-table search application for Django, using native database search engines.

Developed by Dave Hall.

<http://www.etianen.com/>
"""

from __future__ import unicode_literals

from watson.admin import SearchAdmin
from watson.registration import SearchAdapter, default_search_engine, search_context_manager


# The main search methods.
search = default_search_engine.search
filter = default_search_engine.filter


# Easy registration.
register = default_search_engine.register
unregister = default_search_engine.unregister
is_registered = default_search_engine.is_registered
get_registered_models = default_search_engine.get_registered_models
get_adapter = default_search_engine.get_adapter


# Easy context management.
update_index = search_context_manager.update_index
skip_index_update = search_context_manager.skip_index_update
