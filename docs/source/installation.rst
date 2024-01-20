
Installation
============

This is a typical Python library and is installed using pip

.. code:: bash

    pip install xhtml2pdf

Requirements
------------

Python 3.8+

All mandatory requirements are listed in the ``pyproject.toml`` file and are installed automatically using the ``pip install xhtml2pdf`` method.

As PDF library we depend on reportlab, which needs a rendering backend to generate bitmaps and vector graphic formats.
For more information about this, have a look at the `reportlab docs <https://docs.reportlab.com/install/open_source_installation/>`__.

The recommended choice is the `cairo graphics library <https://cairographics.org/>`__ which has to be installed system-wide e.g. via the OS package manager
in combination with the ``PyCairo`` extra dependency:

.. code:: bash

    pip install xhtml2pdf[pycairo]


Alternatively, the legacy ``RenderPM`` can be used by installing:

.. code:: bash

    pip install xhtml2pdf[renderpm]


Development environment
-----------------------

#. If you don't have it, install ``pip``, the python package installer

    .. code:: bash

        sudo easy_install pip

    For more information about ``pip`` refer to http://www.pip-installer.org/.

#. We recommend using ``venv`` for development. It is great to have a separate environment for
   each project, keeping the dependencies for multiple projects separated.

    For more information about ``venv`` refer to https://docs.python.org/3/library/venv.html

#. Create a virtual environment for the project. This can be inside the project directory, but cannot be under
   version control

    .. code:: bash

        python -m venv .venv

#. Activate your virtual environment

    .. code:: bash

        source .venv/bin/activate

    Later to deactivate use

    .. code:: bash

        deactivate

#. Run tests to check your configuration

    .. code:: bash

        python -m unittest discover tests

    You should have a log with success status::

        Ran 108 tests in 1.372s

        OK
