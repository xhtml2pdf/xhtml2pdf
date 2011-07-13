ABOUT
=====

xhtml2pdf is a html2pdf converter using the ReportLab Toolkit,
the HTML5lib and pyPdf. It supports HTML 5 and CSS 2.1 (and some of CSS 3).
It is completely written in pure Python so it is platform independent.

The main benefit of this tool that a user with Web skills like HTML and CSS
is able to generate PDF templates very quickly without learning new
technologies. 

REQUIREMENTS
============

- `Reportlab Toolkit 2.2+ <http://www.reportlab.org/>`_
- `html5lib 0.11.1+ <http://code.google.com/p/html5lib/>`_
- `pyPdf 1.11+ (optional) <http://pybrary.net/pyPdf/>`_

PYTHON INTEGRATION
==================

Some simple demos of how to integrate xhtml2pdf into
a Python program may be found here: test/simple.py


CONTRIBUTING
============

Development for this software happend on github, and the main fork is
currently at https://github.com/chrisglass/xhtml2pdf

Contributions are welcome in any format, but using github's pull request
system is very highly preferred since it makes review and integration
much easier.

RUNNING TESTS
=============

Two different test suites are available to assert xhtml2pdf works reliably:

1. Unit tests. The unit testing framework is currently minimal, but is being
   improved on a daily basis (contributions welcome). They should run in the
   expected way for Python's unittest module, i.e.::

        nosetests --with-coverage (or your personal favorite)


2. Functional tests. Thanks to mawe42's super cool work, a full functional
   test suite lives in rendertests/.


CONTACT
=======

IRC: #xhtml2pdf on freenode
Mailing list: xhtml2pdf@googlegroups.com
Google group: http://groups.google.com/group/xhtml2pdf

Maintainer: Chris Glass <tribaal@gmail.com>

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
