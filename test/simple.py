# -*- coding: utf-8 -*-

# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__version__ = "$Revision: 194 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-04-18 18:59:53 +0200 (Fr, 18 Apr 2008) $"

import os
import sys
import cgi
import cStringIO
import logging

import xhtml2pdf.pisa as pisa

# Shortcut for dumping all logs to the screen
pisa.showLogging()

def dumpErrors(pdf, showLog=True):
    #if showLog and pdf.log:
    #    for mode, line, msg, code in pdf.log:
    #        print "%s in line %d: %s" % (mode, line, msg)
    #if pdf.warn:
    #    print "*** %d WARNINGS OCCURED" % pdf.warn
    if pdf.err:
        print "*** %d ERRORS OCCURED" % pdf.err

def testSimple(
    data="""Hello <b>World</b><br/><img src="img/test.jpg"/>""",
    dest="test.pdf"):

    """
    Simple test showing how to create a PDF file from
    PML Source String. Also shows errors and tries to start
    the resulting PDF
    """

    pdf = pisa.CreatePDF(
        cStringIO.StringIO(data),
        file(dest, "wb")
        )

    if pdf.err:
        dumpErrors(pdf)
    else:
        pisa.startViewer(dest)

def testCGI(data="Hello <b>World</b>"):

    """
    This one shows, how to get the resulting PDF as a
    file object and then send it to STDOUT
    """

    result = cStringIO.StringIO()

    pdf = pisa.CreatePDF(
        cStringIO.StringIO(data),
        result
        )

    if pdf.err:
        print "Content-Type: text/plain"
        print
        dumpErrors(pdf)
    else:
        print "Content-Type: application/octet-stream"
        print
        sys.stdout.write(result.getvalue())

def testBackgroundAndImage(
    src="test-background.html",
    dest="test-background.pdf"):

    """
    Simple test showing how to create a PDF file from
    PML Source String. Also shows errors and tries to start
    the resulting PDF
    """

    pdf = pisa.CreatePDF(
        file(src, "r"),
        file(dest, "wb"),
        log_warn = 1,
        log_err = 1,
        path = os.path.join(os.getcwd(), src)
        )

    dumpErrors(pdf)
    if not pdf.err:
        pisa.startViewer(dest)

def testURL(
    url="http://www.htmltopdf.org",
    dest="test-website.pdf"):

    """
    Loading from an URL. We open a file like object for the URL by
    using 'urllib'. If there have to be loaded more data from the web,
    the pisaLinkLoader helper is passed as 'link_callback'. The
    pisaLinkLoader creates temporary files for everything it loads, because
    the Reportlab Toolkit needs real filenames for images and stuff. Then
    we also pass the url as 'path' for relative path calculations.
    """
    import urllib

    pdf = pisa.CreatePDF(
        urllib.urlopen(url),
        file(dest, "wb"),
        log_warn = 1,
        log_err = 1,
        path = url,
        link_callback = pisa.pisaLinkLoader(url).getFileName
        )

    dumpErrors(pdf)
    if not pdf.err:
        pisa.startViewer(dest)

if __name__=="__main__":

    testSimple()
    # testCGI()
    #testBackgroundAndImage()
    #testURL()
