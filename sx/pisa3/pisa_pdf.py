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


__reversion__ = "$Revision: 20 $"
__author__    = "$Author: holtwick $"
__date__      = "$Date: 2007-10-09 12:58:24 +0200 (Di, 09 Okt 2007) $"

from pisa_util import pisaTempFile, getFile

import logging
log = logging.getLogger("ho.pisa")

class pisaPDF:

    def __init__(self, capacity=-1):
        self.capacity = capacity
        self.files = []

    def addFromURI(self, url, basepath=None):
        obj = getFile(url, basepath)
        if obj and (not obj.notFound()):
            self.files.append(obj.getFile())

    addFromFileName = addFromURI

    def addFromFile(self, f):
        if hasattr(f, "read"):
            self.files.append(f)
        self.addFromURI(f)

    def addFromString(self, data):
        self.files.append(pisaTempFile(data, capacity=self.capacity))

    def addDocument(self, doc):
        if hasattr(doc.dest, "read"):
            self.files.append(doc.dest)

    def join(self, file=None):
        import pyPdf
        if pyPdf:
            output = pyPdf.PdfFileWriter()
            for pdffile in self.files:
                input = pyPdf.PdfFileReader(pdffile)
                for pageNumber in range(0, input.getNumPages()):
                    output.addPage(input.getPage(pageNumber))
        if file is not None:
            output.write(file)
            return file
        out = pisaTempFile(capacity=self.capacity)
        output.write(out)
        return out.getvalue()

    getvalue = join
    __str__ = join
