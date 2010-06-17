#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__version__ = "$Revision: 247 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-08-15 13:37:57 +0200 (Fr, 15 Aug 2008) $"
__svnid__   = "$Id: setup.py 247 2008-08-15 11:37:57Z holtwick $"

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name           = "pisa",
    version        = "VERSION{3.0.33}VERSION"[8:-8],
    description    = "PDF generator using HTML and CSS",
    license        = "Apache License 2.0",
    author         = "Dirk Holtwick",
    author_email   = "dirk.holtwick@gmail.com",
    url            = "http://www.xhtml2pdf.com",
    download_url   = "http://pypi.python.org/pypi/pisa/",
    keywords       = "PDF, HTML, XHTML, XML, CSS",

    requires       = ["html5lib", "pypdf", "pil"], #, "reportlab"],

    include_package_data = False,

    packages = [
        'ho',
        'ho.pisa',
        'sx',
        'sx.pisa3',
        'sx.w3c',
        ],

    test_suite = "tests",

    entry_points = {
        'console_scripts': [
            'pisa = sx.pisa3:command',
            'xhtml2pdf = sx.pisa3:command',
            ]
        },

    long_description = """
pisa is a html2pdf converter using the ReportLab Toolkit,
the HTML5lib and pyPdf. It supports HTML 5 and CSS 2.1 (and some of CSS 3).
It is completely written in pure Python so it is platform independent.
The main benefit of this tool that a user with Web skills like HTML and CSS
is able to generate PDF templates very quickly without learning new
technologies. Easy integration into Python frameworks like CherryPy,
KID Templating, TurboGears, Django, Zope, Plone, Google AppEngine (GAE) etc.
(see 'demo' folder for examples)
        """.strip(),

    classifiers = [x.strip() for x in """
        License :: Freeware
        License :: OSI Approved
        License :: OSI Approved :: Apache Software License
        Development Status :: 5 - Production/Stable
        Development Status :: 6 - Mature
        Environment :: Console
        Environment :: MacOS X
        Environment :: Other Environment
        Environment :: Web Environment
        Environment :: Win32 (MS Windows)
        Framework :: Django
        Framework :: Plone
        Framework :: Pylons
        Framework :: TurboGears
        Framework :: Zope2
        Framework :: Zope3
        Intended Audience :: Customer Service
        Intended Audience :: Developers
        Intended Audience :: Education
        Intended Audience :: Financial and Insurance Industry
        Intended Audience :: Healthcare Industry
        Intended Audience :: Information Technology
        Intended Audience :: Legal Industry
        Intended Audience :: Manufacturing
        Intended Audience :: Science/Research
        Intended Audience :: System Administrators
        Intended Audience :: Telecommunications Industry
        Natural Language :: English
        Natural Language :: German
        Operating System :: MacOS
        Operating System :: MacOS :: MacOS X
        Operating System :: Microsoft
        Operating System :: Microsoft :: MS-DOS
        Operating System :: Microsoft :: Windows
        Operating System :: Other OS
        Operating System :: POSIX
        Operating System :: POSIX :: Linux
        Operating System :: Unix
        Topic :: Documentation
        Topic :: Internet
        Topic :: Multimedia
        Topic :: Office/Business
        Topic :: Office/Business :: Financial
        Topic :: Office/Business :: Financial :: Accounting
        Topic :: Printing
        Topic :: Text Processing
        Topic :: Text Processing :: Filters
        Topic :: Text Processing :: Fonts
        Topic :: Text Processing :: General
        Topic :: Text Processing :: Indexing
        Topic :: Text Processing :: Linguistic
        Topic :: Text Processing :: Markup
        Topic :: Text Processing :: Markup :: HTML
        Topic :: Text Processing :: Markup :: XML
        Topic :: Utilities
        """.strip().splitlines()],

    )
