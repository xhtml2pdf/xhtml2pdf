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

from sx.pisa3 import pisa, pisa_pdf

if __name__ == "__main__":
    pdf = pisa_pdf.pisaPDF()

    subPdf = pisa.pisaDocument("""
            Hello <strong>World</strong>
        """)
    pdf.addDocument(subPdf)

    with open("test-loremipsum.pdf", "rb") as file:
        raw = file.read()
    pdf.addFromString(raw)

    pdf.addFromURI("test-loremipsum.pdf")

    with open("test-loremipsum.pdf", "rb") as file:
        pdf.addFromFile(file)

    datauri = pisa.makeDataURIFromFile("test-loremipsum.pdf")
    pdf.addFromURI(datauri)

    # Write the result to a file and open it
    filename = __file__ + ".pdf"
    result = pdf.getvalue()
    with open(filename, "wb") as file:
        file.write(result)
    pisa.startViewer(filename)
