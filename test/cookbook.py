# -*- coding: ISO-8859-1 -*-

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

__version__ = "$Revision: 176 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-03-15 00:11:47 +0100 (Sa, 15 Mrz 2008) $"

"""
HTML/CSS to PDF converter

Most people know how to write a page with HTML and CSS. Why not using these skills to dynamically generate PDF documents using it? The "pisa" project http://www.htmltopdf.org enables you to to this quite simple.
"""

import cStringIO
import ho.pisa as pisa
import os

# Shortcut for dumping all logs to the screen
pisa.showLogging()

def HTML2PDF(data, filename, open=False):

    """
    Simple test showing how to create a PDF file from
    PML Source String. Also shows errors and tries to start
    the resulting PDF
    """

    pdf = pisa.CreatePDF(
        cStringIO.StringIO(data),
        file(filename, "wb"))

    if open and (not pdf.err):
        pisa.startViewer(filename)

    return not pdf.err

if __name__=="__main__":
    HTMLTEST = """
    <html><body>
    <p>Hello <strong style="color: #f00;">World</strong>
    <hr>
    <table border="1" style="background: #eee; padding: 0.5em;">
        <tr>
            <td>Amount</td>
            <td>Description</td>
            <td>Total</td>
        </tr>
        <tr>
            <td>1</td>
            <td>Good weather</td>
            <td>0 EUR</td>
        </tr>
        <tr style="font-weight: bold">
            <td colspan="2" align="right">Sum</td>
            <td>0 EUR</td>
        </tr>
    </table>
    </body></html>
    """

    HTML2PDF(HTMLTEST, "test.pdf", open=True)
