================
How to run tests
================

This file describes how people should run the various test suites included
with xhtml2pdf.

Unit tests
==========

Running unit tests should be pretty intuitive to most python developers.
xhtml2pdf uses the standard library's unittest library to write tests.
As such, the following command should "just work"::

    nosetests

A few extra bells and whistles are available. Specifically, a .coveragerc file
is included with this project, therefore running coverage reports should give
you immediately useful information::

    pip install coverage
    nosetests --with-coverage
    coverage html
    x-www-browser htmlcov/index.html

The coverage percentage is currently pretty low - feel free to add extra tests!


Functional tests
================

xhtml2pdf ships with a functional tests suite.
To see it in action, run the following commands from the xhtml2pdf directory::

    python testrender/testrender.py
    x-www-browser testrender/output/index.html

The suite renders a set of templates to pdf, then uses imagemagic (available on
most unix-like systems) to convert the pdfs to png images, and finally creates
a image of differences between the generated image and a reference image.

Image sets with a "difference score" of more than 0 are highlighted in red -
this means the rendering library produced a bad result.

Caveats
-------

Font rendering is a very tricky business. As such, the functional suite often
creates "ghost differences" for some font renderings (the images look perfect
for a human eye, but the computer gives them a bad score anyway).

To solve theses, you should try regenerating reference images on your
particular system, so that the exact mechanism used on your platform are used
in both cases::

    python testrender/testrender.py --create-reference local_reference
    python testrender/testrender.py --ref-dir local_reference
    x-www-browser testrender/output/index.html

You can now happily hack away at the library, without any ghost images.
