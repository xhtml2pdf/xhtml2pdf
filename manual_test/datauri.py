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

import logging
import os
import os.path

from xhtml2pdf import pisa

log = logging.getLogger(__name__)


def helloWorld():
    filename = __file__ + ".pdf"
    datauri = pisa.makeDataURIFromFile("img/denker.png")
    bguri = os.path.normpath(
        os.path.join(os.path.abspath(__file__), os.pardir, "pdf/background-sample.pdf")
    )
    bguri = pisa.makeDataURIFromFile(bguri)
    html = f"""
            <style>
            @page {{
                background: url("{bguri}");
                @frame text {{
                    top: 6cm;
                    left: 4cm;
                    right: 4cm;
                    bottom: 4cm;
                    -pdf-frame-border: 1;
                }}
            }}
            </style>

            <p>
            Hello <strong>World</strong>
            <p>
            <img src="{datauri}">
        """
    with open(filename, "wb") as file:
        pdf = pisa.pisaDocument(html, file, path=__file__)
    if not pdf.err:
        pisa.startViewer(filename)


if __name__ == "__main__":
    pisa.showLogging()
    helloWorld()
