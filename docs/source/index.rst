xhtml2pdf documentation
=======================

**xhtml2pdf** is a HTML to PDF converter using Python, the ReportLab Toolkit, turbohtml and pypdf. It supports HTML5 and CSS 2.1 (and some of CSS 3). xhtml2pdf's own code is Python. turbohtml is a compiled dependency, so installation needs a compatible wheel or a C build toolchain.

The main benefit of this tool is that a user with web skills like HTML and CSS is able to generate PDF templates very quickly without learning new technologies.

The **Python module** can be used in any Python environment, including Django.
The **Command line tool** is a stand-alone program that can be executed from the command line.


Contents
--------

.. toctree::
   :maxdepth: 2

   quickstart
   security
   release-notes

.. toctree::
   :caption: User guide
   :maxdepth: 2

   format_html
   advanced-usage
   https_options
   graphics
   encryption_and_signatures
   watermarks
   examples
   Fonts <guide/fonts>

.. toctree::
   :caption: Reference
   :maxdepth: 2

   reference
   reference/python
   reference/html
   reference/cli

.. toctree::
   :caption: Contributing
   :maxdepth: 2

   contributing/development-guide
