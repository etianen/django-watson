django-watson changelog
==========================

1.1.1 - 19/07/2012
------------------

* Ability to use a custom search adapter class in SearchAdmin.
* Template tag helpers for search results.
* Ability to specify search configuration for PostgreSQL backend.


1.1.0 - 05/04/2012
------------------

* Django 1.4 admin compatibility.
* Improved efficiency of large search index updates using update and bulk_create (when available).
* Added in SearchContextMiddleware.
* Removed potentially unreliable automatic wrapping of entire request in a search context.
* Improved escaping of PostgreSQL query characters.


1.0.2 - 07/03/2012
------------------

* Support for prefix matching in search queries.


1.0.1 - 06/02/2012
------------------

* Removing hacky searchentry_set generic relation being applied to registered models, which was causing spurious deletion warnings in the admin interface.


1.0.0 - 10/10/2012
------------------

* First production release.