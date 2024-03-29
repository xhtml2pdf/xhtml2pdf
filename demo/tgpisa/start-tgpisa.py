#!/usr/bin/env python3

"""
Start script for the tgpisa TurboGears project.

This script is only needed during development for running from the project
directory. When the project is installed, easy_install will create a
proper start script.
"""

import sys

from tgpisa.commands import ConfigurationError, start

if __name__ == "__main__":
    try:
        start()
    except ConfigurationError as exc:
        sys.stderr.write(str(exc))
        sys.exit(1)
