django-watson
=============

[![Django CI](https://github.com/etianen/django-watson/actions/workflows/django.yml/badge.svg)](https://github.com/etianen/django-watson/actions/workflows/django.yml)
[![PyPI](https://img.shields.io/pypi/v/django-watson.svg)](https://pypi.python.org/pypi/django-watson)
[![GitHub license](https://img.shields.io/badge/license-New%20BSD-blue.svg)](https://raw.githubusercontent.com/etianen/django-watson/master/LICENSE)

**django-watson** is a fast multi-model full-text search plugin for Django.

It is easy to install and use, and provides high quality search results.


Features
--------

* Search across multiple models.
* Order results by relevance.
* No need to install additional third-party modules or services.
* Fast and scaleable enough for most use cases.
* Supports Django 2+, Python 3.6+.


Documentation
-------------

Please read the [Getting Started][] guide for more information.

[Getting Started]: https://github.com/etianen/django-watson/wiki
    "Getting started with django-watson"

Download instructions, bug reporting and links to full documentation can be
found at the [main project website][].

[main project website]: http://github.com/etianen/django-watson
    "django-watson on GitHub"

You can keep up to date with the latest announcements by joining the
[django-watson discussion group][].

[django-watson discussion group]: http://groups.google.com/group/django-watson
    "django-watson Google Group"


Contributing
------------
Bug reports, bug fixes, and new features are always welcome. Please raise issues on the
[django-watson github repository](https://github.com/etianen/django-watson/issues), and submit
pull requests for any new code.

You can run the test suite yourself from within a virtual environment with the following
commands.

```
    pip install psycopg2 mysqlclient -e .
    tests/runtests.py
    tests/runtests.py -d psql
    tests/runtests.py -d mysql
```

More information
----------------

The django-watson project was developed by Dave Hall. You can get the code
from the [django-watson project site][].

[django-watson project site]: http://github.com/etianen/django-watson
    "django-watson on GitHub"

Dave Hall is a freelance web developer, based in Cambridge, UK. You can usually
find him on the Internet in a number of different places:

*   [Website](http://www.etianen.com/ "Dave Hall's homepage")
*   [Twitter](http://twitter.com/etianen "Dave Hall on Twitter")
*   [Google Profile](http://www.google.com/profiles/david.etianen "Dave Hall's Google profile")
