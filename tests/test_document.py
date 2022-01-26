from __future__ import unicode_literals

import io
import os
import tempfile
from unittest import TestCase, skipIf

from PyPDF3 import PdfFileReader

from xhtml2pdf.document import pisaDocument

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
{head:s}
</head>
<body>
    <div>
        <h1> Hello, world! </h1>

        <p>
            The quick red fox jumps over the lazy brown dog.
        </p>
        {extra_html}
    </div>
</body>
</html>"""

CSS_TESTS = {
    """<style>
    @page {
        size: A4 portrait;
        @frame {left: 10pt}
    }
    </style>""",
    """<style>
    @page two {
        size: A4 landscape;
        @frame {left: 10pt}
    }
    </style>""",
    """<style>
    @page three {
        size: A4 landscape;
        @frame {left: 10pt}
        }
    </style>""",
}

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


class DocumentTest(TestCase):
    def _compare_pdf_metadata(self, pdf_file, assertion):

        # Ensure something has been written
        self.assertNotEqual(pdf_file.tell(), 0)

        # Rewind to the start of the file to read the pdf and get the
        # document's metadata
        pdf_file.seek(0)
        pdf_reader = PdfFileReader(pdf_file)
        pdf_info = pdf_reader.documentInfo

        # Check the received metadata matches the expected metadata
        for original_key in METADATA:
            actual_key = "/{}".format(original_key.capitalize())
            actual_value = pdf_info[actual_key]
            expected_value = METADATA[original_key]

            assertion(actual_value, expected_value)

    def test_document_with_transparent_image(self):
        """
        Test that a transparent PNG image is rendered properly.
        """
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        image_path = os.path.join(tests_folder, 'samples', 'img', 'denker-transparent.png')
        extra_html = "<img src=\"{image_path}\">".format(image_path=image_path)

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html=extra_html)),
                dest=pdf_file
            )
            pdf_file.seek(0)
            pdf_reader = PdfFileReader(pdf_file)

            xobjects = pdf_reader.getPage(0)['/Resources']['/XObject'].getObject()
            objects = [xobjects[key] for key in xobjects.keys()]

            # Identity the 'denker_transparent.png' image by its height and width, and make sure it's there.
            denker_transparant = [obj for obj in objects if obj['/Height'] == 137 and obj['/Width'] == 70]
            self.assertEqual(len(denker_transparant), 1)

    def test_document_background_image(self):
        """
        Test that a transparent PNG image is rendered properly.
        """
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        image_path = os.path.join(tests_folder, 'samples', 'img', 'denker-transparent.png')

        css_background = """<style>@page {{background-image: url('{background_location}');
                         @frame {{left: 10pt}}}}</style>""".format(
            background_location=image_path)

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head=css_background, extra_html="")),
                dest=pdf_file
            )
            pdf_file.seek(0)
            pdf_reader = PdfFileReader(pdf_file)

            xobjects = pdf_reader.getPage(0)['/Resources']['/XObject'].getObject()
            objects = [xobjects[key] for key in xobjects.keys()]

            # Identity the 'denker_transparent.png' image by its height and width, and make sure it's there.
            denker_transparant = [obj for obj in objects if obj['/Height'] == 137 and obj['/Width'] == 70]
            self.assertEqual(len(denker_transparant), 1)

    def test_document_background_image_not_on_all_pages(self):
        """
        Test that all pages are being rendered, when background is a pdf file and it's applied for the first page only.
        """
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        background_path = os.path.join(tests_folder, 'samples', 'images.pdf')

        css = """"<style>@page {{background-image: url('{background_location}'); @frame {{left: 10pt}}}}
              @page two {{@frame {{left: 10 pt}}}}</style>""".format(
            background_location=background_path)

        extra_html = """<pdf:nexttemplate name="two"> <pdf:nextpage> <p>Hello, world!</p>"""

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head=css, extra_html=extra_html)),
                dest=pdf_file
            )
            pdf_file.seek(0)
            pdf_reader = PdfFileReader(pdf_file)

            self.assertEqual(pdf_reader.getNumPages(), 2)

    @skipIf(IN_PYPY, "This doesn't work in pypy")
    def test_document_creation_without_metadata(self):
        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                dest=pdf_file
            )
            self._compare_pdf_metadata(pdf_file, self.assertNotEqual)

    @skipIf(IN_PYPY, "This doesn't work in pypy")
    def test_document_creation_with_metadata(self):
        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                dest=pdf_file,
                context_meta=METADATA
            )
            self._compare_pdf_metadata(pdf_file, self.assertEqual)

    @skipIf(IN_PYPY, "This doesn't work in pypy")
    def test_document_creation_with_css_metadata(self):
        for css_code in CSS_TESTS:
            with tempfile.TemporaryFile() as pdf_file:
                pisaDocument(
                    src=io.StringIO(HTML_CONTENT.format(head=css_code, extra_html="")),
                    dest=pdf_file,
                    context_meta=METADATA
                )
                self._compare_pdf_metadata(pdf_file, self.assertEqual)

    def test_destination_is_none(self):
        context = pisaDocument(HTML_CONTENT.format(head="", extra_html=""))
        self.assertGreater(len(context.dest.getvalue()), 0)

    def test_in_memory_document(self):
        with io.BytesIO() as in_memory_file:
            pisaDocument(HTML_CONTENT.format(head="", extra_html=""), dest=in_memory_file)
            self.assertGreater(len(in_memory_file.getvalue()), 0)

        with io.BytesIO() as in_memory_file:
            pisaDocument(io.StringIO(HTML_CONTENT.format(head="", extra_html="")), dest=in_memory_file)
            self.assertGreater(len(in_memory_file.getvalue()), 0)
