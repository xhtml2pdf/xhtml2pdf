*********
xhtml2pdf
*********

.. image:: https://travis-ci.org/xhtml2pdf/xhtml2pdf.svg
    :target: https://travis-ci.org/xhtml2pdf/xhtml2pdf

This project is community-led! To strengthen it, please hang out on IRC #xhtml2pdf (Freenode)
or join `our maling list <http://groups.google.com/group/xhtml2pdf>`__.

About
=====

``xhtml2pdf`` is a html2pdf converter using the ReportLab Toolkit,
the HTML5lib and pyPdf. It supports HTML 5 and CSS 2.1 (and some of CSS 3).
It is completely written in pure Python so it is platform independent.

The main benefit of this tool that a user with Web skills like HTML and CSS
is able to generate PDF templates very quickly without learning new
technologies.

Requirements
============

#. `Reportlab Toolkit 2.2+ <http://www.reportlab.org/>`_
#. `html5lib 0.11.1+ <http://code.google.com/p/html5lib/>`_
#. `PyPDF2 1.19+ (optional) <https://pypi.python.org/pypi/PyPDF2>`_

All requirements are listed in ``requirements.txt`` file.

Development environment
=======================

#. Install Python 2.6.x or 2.7.x. Installation steps depends on your operating system.

#. Install Pip, the python package installer::

    sudo easy_install pip

   For more information about ``pip`` refer to http://www.pip-installer.org/.

#. I will recommend using ``virtualenv`` for development. This is great to have separate environment for
   each project, keeping the dependencies for multiple projects separated::

    sudo pip install virtualenv

   For more information about ``virtualenv`` refer to http://www.virtualenv.org/

#. Create virtualenv for the project. This can be inside the project directory, but cannot be under
   version control::

    virtualenv --distribute xhtml2pdfenv --python=python2

#. Activate your virtualenv::

    source xhtml2pdfenv/bin/activate

   Later to deactivate use::

    deactivate

#. Next step will be to install/upgrade dependencies from ``requirements.txt`` file::

    pip install -r requirements.txt

#. Run tests to check your configuration::

    nosetests --with-coverage

   You should have a log with success status::

    Ran 36 tests in 0.322s

    OK

Python integration
==================

Some simple demos of how to integrate xhtml2pdf into
a Python program may be found here: test/simple.py


Running tests
=============

Two different test suites are available to assert xhtml2pdf works reliably:

#. Unit tests. The unit testing framework is currently minimal, but is being
   improved on a daily basis (contributions welcome). They should run in the
   expected way for Python's unittest module, i.e.::

        nosetests --with-coverage (or your personal favorite)

#. Functional tests. Thanks to mawe42's super cool work, a full functional
   test suite lives in testrender/.

Contact
=======

* IRC: #xhtml2pdf on freenode
* Mailing list: xhtml2pdf@googlegroups.com
* Google group: http://groups.google.com/group/xhtml2pdf

History
=======

This are the major milestones and the maintainers of the project:

* 2000-2007, commercial project, spirito.de, written by Dirk Holtwich
* 2007-2010 Dirk Holtwich (project named "Pisa", project released as GPL)
* 2010-2012 Dirk Holtwick (project named "xhtml2pdf", changed license to Apache)
* 2012-2015 Chris Glass (@chrisglass)
* 2015- Benjamin Bach (@benjaoming)

For more history, see the CHANGELOG.

License
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
