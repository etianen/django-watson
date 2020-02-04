import os
from setuptools import setup
from watson import __version__

setup(
    name="django-watson",
    version='.'.join(str(x) for x in __version__),
    description="Full-text multi-table search application for Django. Easy to install and use, with good performance.",
    long_description=open(os.path.join(os.path.dirname(__file__), "README.markdown")).read(),
    author="Dave Hall",
    author_email="dave@etianen.com",
    url="http://github.com/etianen/django-watson",
    zip_safe=False,
    long_description_content_type="text/markdown",
    packages=[
        "watson",
        "watson.management",
        "watson.management.commands",
        "watson.migrations",
        "watson.templatetags",
    ],
    package_data={
        "watson": [
            "locale/*/LC_MESSAGES/django.*",
            "templates/watson/*.html",
            "templates/watson/includes/*.html",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        "Framework :: Django",
    ],
)
