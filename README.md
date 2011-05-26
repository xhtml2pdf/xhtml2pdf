ABOUT
=====

xhtml2pdf is a html2pdf converter using the ReportLab Toolkit,
the HTML5lib and pyPdf. It supports HTML 5 and CSS 2.1 (and some of CSS 3).
It is completely written in pure Python so it is platform independent.

The main benefit of this tool that a user with Web skills like HTML and CSS
is able to generate PDF templates very quickly without learning new
technologies. 

Easy integration into Python frameworks like CherryPy,
KID Templating, TurboGears, Django, Zope, Plone, Google AppEngine (GAE) etc.

HELP
====

> xhtml2pdf -h

REQUIREMENTS
============

- Reportlab Toolkit 2.2+
  <http://www.reportlab.org/>

- html5lib 0.11.1+
  <http://code.google.com/p/html5lib/>

- pyPdf 1.11+ (optional)
  <http://pybrary.net/pyPdf/>

EXAMPLES
========

> xhtml2pdf -s test\test-loremipsum.html
> xhtml2pdf -s http://www.python.org
> xhtml2pdf test\test-*.html

PYTHON INTEGRATION
==================

Some simple demos of how to integrate PISA into
a Python program may be found here: test\simple.py

CONTACT
=======

dirk.holtwick@gmail.com

LICENSE
=======

Copyright 2010 Dirk Holtwick, holtwick.it

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.