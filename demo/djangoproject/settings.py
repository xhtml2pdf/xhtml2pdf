# Django settings for the example project.

import os
DEBUG = True
TEMPLATE_DEBUG = DEBUG
ROOT_URLCONF = 'djangoproject.urls'
TEMPLATE_DIRS = (
    os.path.join(os.path.dirname(__file__), 'templates'),
)

