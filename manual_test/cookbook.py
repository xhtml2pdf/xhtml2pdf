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

__version__ = "$Revision: 176 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-03-15 00:11:47 +0100 (Sa, 15 Mrz 2008) $"

"""
HTML/CSS to PDF converter

Most people know how to write a page with HTML and CSS. Why not using these skills to dynamically generate PDF
documents using it? The "pisa" project http://www.htmltopdf.org enables you to to this quite simple.
"""
import six

from xhtml2pdf import pisa
from faker import Faker

# Shortcut for dumping all logs to the screen
pisa.showLogging()


def html2pdf(data, filename, open_file=False):

    """
    Simple test showing how to create a PDF file from
    PML Source String. Also shows errors and tries to start
    the resulting PDF
    """

    pdf = pisa.CreatePDF(
        six.StringIO(data),
        open(filename, "wb"))

    if open_file and (not pdf.err):
        pisa.startViewer(filename)

    return not pdf.err

if __name__ == "__main__":
    HTMLTEST = """
    <html>
    <style>
    @page {
        size: a4 portrait;
        @frame header_frame {           /* Static Frame */
            -pdf-frame-content: header_content;
            left: 50pt; width: 512pt; top: 50pt; height: 40pt;
        }
        @frame content_frame {          /* Content Frame */
            left: 50pt; width: 512pt; top: 90pt; height: 632pt;
        }
        @frame footer_frame {           /* Another static Frame */
            -pdf-frame-content: footer_content;
            left: 50pt; width: 512pt; top: 772pt; height: 20pt;
        }

    }
    </style>
    <body dir="rtl">
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
    <pdf:language name="arabic"/>
    <p dir="rtl">Esto es un texto al revez</p>
    %s
   
    <div id="header_content">Lyrics-R-Us</div>
    <div id="footer_content">(c) - page <pdf:pagenumber>
        of <pdf:pagecount>
    </div>
     </body>
    </html>
    """



    fake = Faker()
    html  = HTMLTEST%(
        "<br>".join(["<p>%s  <span style=\"color: #f00;\"><pdf:pagenumber> of <pdf:pagecount> </span></p>"%fake.text() for x in range(10)])

    )
    html2pdf(html, "test.pdf", open_file=False)
