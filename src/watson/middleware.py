"""Middleware used by django-watson."""

from __future__ import unicode_literals

from watson.registration import search_context_manager


WATSON_MIDDLEWARE_FLAG = "watson.search_context_middleware_active"


class SearchContextMiddleware(object):
    
    """Wraps the entire request in a search context."""
    
    def process_request(self, request):
        """Starts a new search context."""
        request.META[WATSON_MIDDLEWARE_FLAG] = self
        search_context_manager.start()
    
    def _close_search_context(self, request):
        """Closes the search context."""
        if WATSON_MIDDLEWARE_FLAG in request.META:
            del request.META[WATSON_MIDDLEWARE_FLAG]
            search_context_manager.end()
    
    def process_response(self, request, response):
        """Closes the search context."""
        self._close_search_context(request)
        return response
        
    def process_exception(self, request, exception):
        """Closes the search context."""
        search_context_manager.invalidate()    
        self._close_search_context(request)
