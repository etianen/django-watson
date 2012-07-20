from distutils.core import setup


setup(
    name = "django-watson",
    version = "1.1.1",
    description = "Full-text multi-table search application for Django. Easy to install and use, with good performance.",
    long_description = open("README.markdown").read(),
    author = "Dave Hall",
    author_email = "dave@etianen.com",
    url = "http://github.com/etianen/django-watson",
    download_url = "http://github.com/downloads/etianen/django-watson/django-watson-1.1.1.tar.gz",
    zip_safe = False,
    packages = [
        "watson",
        "watson.management",
        "watson.management.commands",
        "watson.migrations",
        "watson.templatetags",
    ],
    package_dir = {
        "": "src",
    },
    package_data = {
        "watson": [
            "locale/*/LC_MESSAGES/django.*",
            "templates/watson/*.html",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Framework :: Django",
    ],
)