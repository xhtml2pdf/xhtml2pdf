*********
xhtml2pdf
*********

THIS PROJECT WAS INHERITED BY NECESSITY - PLEASE DO NOT CONTACT ME DIRECTLY
FOR HELP BUT USE THE MAILING LIST INSTEAD.

I picked up the code because I needed to patch it, and nobody was around to 
merge my pull requests in. So now 
I can merge pull requests in, but I did not write the code.

If you think you can do a better job maintaing this project, feel free to let me know
and I'll give you commit rights (or ownership, or whatever).

Thanks!


HTML/CSS to PDF converter based on Python

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

Python, virtualenv and dependencies
-----------------------------------

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

Contributing
============

Development for this software happend on github, and the main fork is
currently at https://github.com/chrisglass/xhtml2pdf

Contributions are welcome in any format, but using github's pull request
system is very highly preferred since it makes review and integration
much easier.

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

Maintainer: Chris Glass <tribaal@gmail.com>

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
