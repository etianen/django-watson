"""Adaptors for registering models with django-watson."""


class SearchAdaptor(object):

    """An adaptor for performing a full-text search on a model."""
    
    # If set to True, then the search engine will only return
    # models accessible from the default manager of the model. This allows
    # you to limit the results according to some custom publication of your
    # own, at the expense of some search performance.
    live_filter = False
    
    # Use to specify the fields that should be included in the seach.
    fields = None
    
    # Use to exclude fields from the search.
    exclude = None
    
    # Use to specify object properties to be stored in the search index.
    store = None
    
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
        # Add in the stored fields.    
        if self.store:
            for field_name in self.store:
                value = getattr(obj, field_name)
                if callable(value):
                    value = value()
                meta[field_name] = value
        # Return the meta information.
        return meta
        
    def get_search_text(self, obj):
        """Returns the search text associated with the given obj."""
        # Get the field names to look up.
        if self.fields is None:
            field_names = [field.name for field in self.model._meta.fields if isinstance(field, (models.CharField, models.TextField))]
        else:
            field_names = self.fields
        # Exclude named fields.
        if exclude:
            field_names = [field_name for field_name in field_names if field_name not in self.exclude]
        # Create the text.
        text_parts = []
        for field_name in field_names:
            # Resolve the value.
            value = getattr(obj, field_name)
            if callable(value):
                value = value()
            value = unicode(value)
            # Store the value.
            text_parts.append(value)
        # Consolidate the text.
        return u"".join(text_parts)
        
    def get_weighted_search_text(self, obj):
        """Returns the weighted search text associated with the given obj."""
        return (unicode(obj), self.get_search_text(),)


class RegistrationError(Exception):

    """Something went wrong with registering a model with django-watson."""
        

# The registered models.
_registered_models = {}


def is_registered(model):
    """Checks whether the given model is registered with django-watson."""
    global _registered_models
    return model in _registered_models


def register(model, adaptor_cls=SearchAdaptor):
    """
    Registers the given model with django-watson.
    
    If the given model is already registered with django-watson, a
    RegistrationError will be raised.
    """
    global _registered_models
    # Check for existing registration.
    if is_registered(model):
        raise RegistrationError("{model!r} is already registered with django-watson".format(
            model = model,
        ))
    # Perform the registration.
    adaptor_obj = adaptor_cls(model)
    _registered_models[model] = adaptor_obj
    
    
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
        
        
def get_registered_models():
    """Returns a sequence of models that have been registered with django-watson."""
    global _registered_models
    return _registered_models.keys()
    
    
def get_adaptor(model):
    """Returns the adaptor associated with the given model."""
    global _registered_models
    if is_registered(model):
        return _registered_models[model]
    raise RegistrationError("{model!r} not registered with django-watson".format(
        model = model,
    ))