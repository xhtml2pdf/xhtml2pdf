# -*- coding: utf-8 -*-
#############################################
## (C)opyright by Dirk Holtwick            ##
## All rights reserved                     ##
#############################################

__version__ = "$Revision: 176 $"
__author__ = "$Author: kgrodzicki $"
__date__ = "$Date: 2011-01-15 10:11:47 +0100 (Fr, 15 July 2011) $"

"""
HTML/CSS to PDF converter
Test background image generation on the `portrait` and `landscape`
page.
"""

from cookbook import HTML2PDF

if __name__ == "__main__":
    xhtml = open('test-background-img.html')
    HTML2PDF(xhtml.read(), "testBackground.pdf")
