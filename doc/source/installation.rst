
Installation
============

This is a typical Python library and is installed using pip

.. code:: bash

    pip install xhtml2pdf

To obtain the latest experimental version that has **Python 3 support**, please
use a prerelease

.. code:: bash

    pip install --pre xhtml2pdf

Requirements
--------------

Python 2.7+. Only Python 3.4+ is tested and guaranteed to work.

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

        nosetests --with-coverage

    You should have a log with success status::

        Ran 36 tests in 0.322s

        OK


