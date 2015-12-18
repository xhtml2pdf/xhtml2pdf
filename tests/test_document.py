from __future__ import unicode_literals

import io
import tempfile

from nose import tools
from unittest import skipIf as skip_if

from PyPDF2 import PdfFileReader

from xhtml2pdf.document import pisaDocument


HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
</head>
<body>
    <div>
        <h1> Hello, world! </div>

        <p>
            The quick red fox jumps over the lazy brown dog.
        </p>
    </div>
</body>
</html>"""


METADATA = {
    "author": "MyCorp Ltd.",
    "title": "My Document Title",
    "subject": "My Document Subject",
    "keywords": "pdf, documents",
}

try:
    import __pypy__
except ImportError:
    IN_PYPY = False
else:
    IN_PYPY = True


def _compare_pdf_metadata(pdf_file, assertion):

    # Ensure something has been written
    tools.assert_not_equal(pdf_file.tell(), 0)

    # Rewind to the start of the file to read the pdf and get the
    # docuemnt's metadata
    pdf_file.seek(0)
    pdf_reader = PdfFileReader(pdf_file)
    pdf_info = pdf_reader.documentInfo

    # Check the received metadata matches the expected metadata
    for original_key in METADATA:
        actual_key = "/{}".format(original_key.capitalize())
        actual_value = pdf_info[actual_key]
        expected_value = METADATA[original_key]

        assertion(actual_value, expected_value)


@skip_if(IN_PYPY, "This doesn't work in pypy")
def test_document_creation_without_metadata():
    with tempfile.TemporaryFile() as pdf_file:
        pisaDocument(
            src=io.StringIO(HTML_CONTENT),
            dest=pdf_file
        )
        _compare_pdf_metadata(pdf_file, tools.assert_not_equal)


@skip_if(IN_PYPY, "This doesn't work in pypy")
def test_document_creation_with_metadata():
    with tempfile.TemporaryFile() as pdf_file:
        pisaDocument(
            src=io.StringIO(HTML_CONTENT),
            dest=pdf_file,
            context_meta=METADATA
        )
        _compare_pdf_metadata(pdf_file, tools.assert_equal)
