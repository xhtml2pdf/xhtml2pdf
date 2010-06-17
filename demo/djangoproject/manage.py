#!/usr/bin/env python
from django.core.management import execute_manager

# Patch for Python 2.5

try:
    import sitecustomize
except:
    pass

# Set logging

import logging

try:
    logging.basicConfig(
        level=logging.WARN,
        format="%(levelname)s [%(name)s] %(pathname)s line %(lineno)d in %(funcName)s: %(message)s")
except:
    logging.basicConfig()

try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    execute_manager(settings)
