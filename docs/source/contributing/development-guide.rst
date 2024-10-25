=================
Development guide
=================

Setting up
----------

**Prerequisites:** Python v3.8 or newer

#. Your Python installation should have ``pip`` pre-installed. If, for some
   reason, it doesn't, follow `the installation instructions <https://pip.pypa.io/en/stable/installation/>`_.

#. We recommend using ``venv`` or ``virtualenv`` for development. It is a good
   idea to have a separate environment for each project, keeping the
   dependencies for multiple projects separated.

   ``venv`` is shipped with Python, while ``virtualenv`` is a separate package.
   Learn more about ``virtualenv`` at https://virtualenv.pypa.io/

#. Create a virtual environment for the project. This can be inside the project
   directory, but it should not be added to the version control.

    .. code:: shell

        python3 -m venv .venv

    Or, if you're using ``virtualenv``:

    .. code:: shell

        python3 -m virtualenv .venv

#. Activate your virtual environment

    .. code:: shell

        source .venv/bin/activate

    Later, to deactivate the environment, use

    .. code:: shell

        deactivate

#. Finally, you can install the project along with its dependencies:

    .. code:: shell

        pip install -e '.[test,docs,release]'

Running tests
-------------

This section describes how people should run the various test suites included
with xhtml2pdf.

To run all tests across all supported Python versions (this is probably what
you want), you can use tox:

.. code:: shell

    tox

If you want to run individual test categories or are just curious, continue with
the following subsections.

Unit tests
^^^^^^^^^^

Unit tests apply to individual classes and methods in isolation from each other.
Running these should be pretty intuitive to most Python developers, as xhtml2pdf
uses the standard library's ``unittest``.

As such, the following command should "just work":

.. code:: shell

    python3 -m unittest discover tests

This command will run the tests and print a status looking something like this::

    Ran 108 tests in 1.372s

    OK


Functional tests
^^^^^^^^^^^^^^^^

xhtml2pdf ships with a functional tests suite. To see it in action, run the
following commands:

.. code:: shell

    python3 testrender/testrender.py
    x-www-browser testrender/output/index.html

The suite renders a set of HTML templates to PDF, then uses `ImageMagick <https://imagemagick.org/>`_
(available on most systems) to convert the PDFs into PNG images, and finally
creates a difference image between the generated image and a reference image.

Image sets with a "difference score" of more than 0 are highlighted in red —
this means the rendering library produced a bad result.

Font rendering is a very tricky business. As such, the functional suite often
creates "ghost differences" for some font renderings (the images look perfect
for a human eye, but the computer gives them a bad score anyway).

To solve these, you should try regenerating reference images on your
particular system, so that the exact mechanism used on your platform are used
in both cases:

.. code:: shell

    python testrender/testrender.py --create-reference local_reference
    python testrender/testrender.py --ref-dir local_reference
    x-www-browser testrender/output/index.html

You can now happily hack away at the library, without any ghost images.


Running tests with coverage
^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can run both unit and functional tests with coverage, which will show the
percentage of our code base covered by tests. For this, replace ``python`` in
the commands with ``coverage run``, like this:

.. code:: shell

    coverage run -m unittest discover tests
    coverage run -a testrender/testrender.py

After running the tests, display the report:

.. code:: shell

    coverage report

We strive to get our coverage as high as possible, so feel free to add extra
tests to help us!
