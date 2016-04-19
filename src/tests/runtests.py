#!/usr/bin/env python
import sys, os, os.path
from optparse import OptionParser

AVAILABLE_DATABASES = {
    'psql': {'ENGINE': 'django.db.backends.postgresql_psycopg2'},
    'mysql': {'ENGINE': 'django.db.backends.mysql'},
    'sqlite': {'ENGINE': 'django.db.backends.sqlite3'},
}


def main():
    # Parse the command-line options.
    parser = OptionParser()
    parser.add_option(
        "-v", "--verbosity",
        action="store",
        dest="verbosity",
        default="1",
        type="choice",
        choices=["0", "1", "2", "3"],
        help="Verbosity level; 0=minimal output, 1=normal output, 2=all output",
    )
    parser.add_option(
        "--noinput",
        action="store_false",
        dest="interactive",
        default=True,
        help="Tells Django to NOT prompt the user for input of any kind.",
    )
    parser.add_option(
        "--failfast",
        action="store_true",
        dest="failfast",
        default=False,
        help="Tells Django to stop running the test suite after first failed test.",
    )
    parser.add_option(
        "-d", "--database",
        action="store",
        dest="database",
        default="sqlite",
        type="choice",
        choices=list(AVAILABLE_DATABASES.keys()),
        help="Select database backend for tests. Available choices: {}".format(
            ', '.join(AVAILABLE_DATABASES.keys())),
    )
    options, args = parser.parse_args()
    # Configure Django.
    from django.conf import settings

    # database settings
    if options.database:
        database_setting = AVAILABLE_DATABASES[options.database]
        if options.database == "sqlite":
            database_default_name = os.path.join(os.path.dirname(__file__), "db.sqlite3")
        else:
            database_default_name = "test_project"
        database_setting.update(dict(
            NAME=os.environ.get("DB_NAME", database_default_name),
            USER=os.environ.get("DB_USER", ""),
            PASSWORD=os.environ.get("DB_PASSWORD", "")))
    else:
        database_setting = dict(
            ENGINE=os.environ.get("DB_ENGINE", 'django.db.backends.sqlite3'),
            NAME=os.environ.get("DB_NAME", os.path.join(os.path.dirname(__file__), "db.sqlite3")),
            USER=os.environ.get("DB_USER", ""),
            PASSWORD=os.environ.get("DB_PASSWORD", ""))

    settings.configure(
        DEBUG=False,
        DATABASES={
            "default": database_setting
        },
        ROOT_URLCONF="urls",
        INSTALLED_APPS=(
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.sites",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "django.contrib.admin",
            "watson",
            "test_watson",
        ),
        MIDDLEWARE_CLASSES=(
            "django.middleware.common.CommonMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
        ),
        USE_TZ=True,
        STATIC_URL="/static/",
        TEST_RUNNER="django.test.runner.DiscoverRunner",
    )
    # Run Django setup (1.7+).
    import django
    try:
        django.setup()
    except AttributeError:
        pass  # This is Django < 1.7
    # Configure the test runner.
    from django.test.utils import get_runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner(
        verbosity = int(options.verbosity),
        interactive = options.interactive,
        failfast = options.failfast,
    )
    # Run the tests.
    failures = test_runner.run_tests(["test_watson"])
    if failures:
        sys.exit(failures)


if __name__ == "__main__":
    main()
