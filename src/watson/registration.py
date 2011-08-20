"""Adaptors for registering models with django-watson."""


class SearchAdaptor(object):

    """An adaptor for performing a full-text search on a model."""
    
    def __init__(self, model):
        """Initializes the search adaptor."""
        self.model = model
    
    def get_meta(self, obj):
        """Returns a dictionary of meta information about the given obj."""
        meta = {
            "title": unicode(obj),
        }
        # Add in the URL.
        if hasattr(obj, "get_absolute_url"):
            meta["url"] = obj.get_absolute_url()
        # Return the meta information.
        return meta
        
    def get_search_text(self, obj):
        """Returns the search text associated with the given obj."""
        return unicode(obj)
        
    def get_weighted_search_text(self, obj):
        """Returns the weighted search text associated with the given obj."""
        return (self.get_search_text(),)


class RegistrationError(Exception):

    """Something went wrong with registering a model with django-watson."""
        

# The registered models.
_registered_models = {}


def is_registered(model):
    """Checks whether the given model is registered with django-watson."""
    global _registered_models
    return model in _registered_models


def register(model, live_filter=False):
    """
    Registers the given model with django-watson.
    
    If live_filter is set to True, then the search engine will only return
    models accessible from the default manager of the model. This allows
    you to limit the results according to some custom publication of your
    own, at the expense of some search performance.
    
    If the given model is already registered with django-watson, a
    RegistrationError will be raised.
    """
    global _registered_models
    # Check for existing registration.
    if is_registered(model):
        raise RegistrationError("{model!r} is already registered with django-watson".format(
            model = model,
        ))
    # Resolve the live queryset.
    if live_filter:
        live_queryset = model._default_manager.all()
    else:
        live_queryset = None
    # Perform the registration.
    _registered_models[model] = live_queryset
    
    
def unregister(model):
    """
    Unregisters the given model with django-watson.
    
    If the given model is not registered with django-watson, a RegistrationError
    will be raised.
    """
    global _registered_models
    if is_registered(model):
        del _registered_models[model]
    else:
        raise RegistrationError("{model!r} not registered with django-watson".format(
            model = model,
        ))
        
        
def get_registered_models(model):
    """Returns a sequence of models that have been registered with django-watson."""
    global _registered_models
    return _registered_models.keys()