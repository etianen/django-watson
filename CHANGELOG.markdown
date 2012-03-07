django-watson changelog
==========================


1.1.0 - UNRELEASED
------------------

* Added in SearchContextMiddleware.
* Removed potentially unreliable automatic wrapping of entire request in a search context.


1.0.2 - 07/03/2012
------------------

* Support for prefix matching in search queries.


1.0.1 - 06/02/2012
------------------

* Removing hacky searchentry_set generic relation being applied to registered models, which was causing spurious deletion warnings in the admin interface.


1.0.0 - 10/10/2012
------------------

* First production release.