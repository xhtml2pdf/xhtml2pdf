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

__version__ = "$Revision: 194 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-04-18 18:59:53 +0200 (Fr, 18 Apr 2008) $"

import ho.pisa as pisa
import os, os.path
import logging
log = logging.getLogger(__file__)

def helloWorld():
    filename = __file__ + ".pdf"
    datauri = pisa.makeDataURIFromFile('img/denker.png')
    bguri = os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir, "pdf/background-sample.pdf"))
    bguri = pisa.makeDataURIFromFile(bguri)
    html = u"""
            <style>
            @page {
                background: url("%s");
                @frame text {
                    top: 6cm;
                    left: 4cm;
                    right: 4cm;
                    bottom: 4cm;
                    -pdf-frame-border: 1;
                }
            }
            </style>

            <p>
            Hello <strong>World</strong>
            <p>
            <img src="%s">
        """ % (bguri, datauri)
    pdf = pisa.pisaDocument(
        html,
        file(filename, "wb"),
        path = __file__
        )
    if not pdf.err:
        pisa.startViewer(filename)

if __name__=="__main__":
    pisa.showLogging()
    helloWorld()
