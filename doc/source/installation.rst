
Installation
============

This is a typical Python library and is installed using pip

.. code:: bash

    pip install xhtml2pdf

Requirements
--------------

Tested are Python 2.7, 3.5, 3.6, 3.7 aand 3.8 at the moment. But support for Python < 3.6 will be dropped in the next release! Support for Python 3.9 is being worked on.

All additional requirements are listed in ``requirements.txt`` file and are
installed automatically using the ``pip install xhtml2pdf`` method.


Development environment
---------------------------

#. If you don't have it, install ``pip``, the python package installer

    .. code:: bash

        sudo easy_install pip

    For more information about ``pip`` refer to http://www.pip-installer.org/.

#. I will recommend using ``virtualenv`` for development. This is great to have separate environment for
   each project, keeping the dependencies for multiple projects separated

    .. code:: bash

        sudo pip install virtualenv


    For more information about ``virtualenv`` refer to http://www.virtualenv.org/

#. Create virtualenv for the project. This can be inside the project directory, but cannot be under
   version control

    .. code:: bash

        virtualenv --distribute xhtml2pdfenv --python=python2

#. Activate your virtualenv

    .. code:: bash

        source xhtml2pdfenv/bin/activate

    Later to deactivate use

    .. code:: bash

        deactivate

#. Next step will be to install/upgrade dependencies from ``requirements.txt`` file

    .. code:: bash

        pip install -r requirements.txt

#. Run tests to check your configuration

    .. code:: bash

        -m unittest discover

    You should have a log with success status::

        Ran 108 tests in 1.372s

        OK


