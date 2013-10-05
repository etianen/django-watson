django-watson
=============

**django-watson** is a fast multi-model full-text search plugin for Django.

It is easy to install and use, and provides high quality search results. 


Features
--------

* Search across multiple models.
* Order results by by relevance.
* No need to install additional third-party modules or services.
* Fast and scaleable enough for most use cases.
* UPDATED: Can consider search config on row-level if there is column with language information (for PostgreSQL only)


Documentation
-------------

Please read the docs for main project first:

[main project website]: http://github.com/etianen/django-watson
    "django-watson on GitHub"

After installation register model with 

watson.register(Model, search_config='search_language')

where search_config point to model's field with language name ('english', 'russian', etc., like in pg_catalog.*)
Now you should be able to do search your model with or without search_config specified in your view, just like:

            if request.LANGUAGE_CODE == 'ru':
                results = watson.search(query, models=(my_model,), search_config='russian')
            else:
                results = watson.search(query, models=(my_model,))

filter() is search_config aware too.
    
More information
----------------

The django-watson project was developed by Dave Hall. You can get the code
from the [django-watson project site][].

[django-watson project site]: http://github.com/etianen/django-watson
    "django-watson on GitHub"
