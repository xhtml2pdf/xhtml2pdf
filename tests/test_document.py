import io
import os
import tempfile
from importlib.util import find_spec
from unittest import TestCase, skipIf

from pypdf import PdfReader

from xhtml2pdf.document import pisaDocument

HTML_CONTENT: str = """<!DOCTYPE html>
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


IN_PYPY = find_spec("__pypy__") is not None


class DocumentTest(TestCase):
    def _compare_pdf_metadata(self, pdf_file, assertion):
        # Ensure something has been written
        self.assertNotEqual(pdf_file.tell(), 0)

        # Rewind to the start of the file to read the pdf and get the
        # document's metadata
        pdf_file.seek(0)
        pdf_reader = PdfReader(pdf_file)
        pdf_info = pdf_reader.metadata

        # Check the received metadata matches the expected metadata
        for original_key in METADATA:
            actual_key = f"/{original_key.capitalize()}"
            actual_value = pdf_info[actual_key]
            expected_value = METADATA[original_key]

            assertion(actual_value, expected_value)

    def test_document_with_transparent_image(self) -> None:
        """Test that a transparent PNG image is rendered properly."""
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        image_path = os.path.join(
            tests_folder, "samples", "img", "denker-transparent.png"
        )
        extra_html = f'<img src="{image_path}">'

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html=extra_html)),
                dest=pdf_file,
            )
            pdf_file.seek(0)
            pdf_reader = PdfReader(pdf_file)

            xobjects = pdf_reader.pages[0]["/Resources"]["/XObject"].get_object()
            objects = [xobjects[key] for key in xobjects]

            # Identity the 'denker_transparent.png' image by its height and width, and make sure it's there.
            denker_transparant = [
                obj for obj in objects if obj["/Height"] == 137 and obj["/Width"] == 70
            ]
            self.assertEqual(len(denker_transparant), 1)

    def test_document_background_image(self) -> None:
        """Test that a transparent PNG image is rendered properly."""
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        image_path = os.path.join(
            tests_folder, "samples", "img", "denker-transparent.png"
        )

        css_background = f"""<style>@page {{background-image: url('{image_path}');
                         @frame {{left: 10pt}}}}</style>"""

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(
                    HTML_CONTENT.format(head=css_background, extra_html="")
                ),
                dest=pdf_file,
            )
            pdf_file.seek(0)
            pdf_reader = PdfReader(pdf_file)

            xobjects = pdf_reader.pages[0]["/Resources"]["/XObject"].get_object()
            objects = [xobjects[key] for key in xobjects]

            # Identity the 'denker_transparent.png' image by its height and width, and make sure it's there.
            denker_transparant = [
                obj for obj in objects if obj["/Height"] == 137 and obj["/Width"] == 70
            ]
            self.assertEqual(len(denker_transparant), 1)

    def test_document_background_image_not_on_all_pages(self) -> None:
        """Test that all pages are being rendered, when background is a pdf file and it's applied for the first page only."""
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        background_path = os.path.join(tests_folder, "samples", "images.pdf")

        css = """"<style>@page {{background-image: url('{background_location}'); @frame {{left: 10pt}}}}
              @page two {{@frame {{left: 10 pt}}}}</style>""".format(
            background_location=background_path
        )

        extra_html = (
            """<pdf:nexttemplate name="two"> <pdf:nextpage> <p>Hello, world!</p>"""
        )

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head=css, extra_html=extra_html)),
                dest=pdf_file,
            )
            pdf_file.seek(0)
            pdf_reader = PdfReader(pdf_file)

            self.assertEqual(len(pdf_reader.pages), 2)

    def test_document_with_broken_image(self) -> None:
        """Test that broken images don't cause unhandled exception"""
        # Although this is just html, it will be recognized as svg
        image_path = "https://raw.githubusercontent.com/xhtml2pdf/xhtml2pdf/b01b1d8f9497dedd0f2454409d03408bdeea997c/tests/samples/images.html"
        extra_html = f'<img src="{image_path}">'
        with open(os.devnull, "wb") as pdf_file, self.assertLogs(
            "xhtml2pdf.xhtml2pdf_reportlab", level="WARNING"
        ) as cm:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html=extra_html)),
                dest=pdf_file,
            )
            self.assertEqual(
                cm.output,
                [
                    "WARNING:xhtml2pdf.xhtml2pdf_reportlab:SVG drawing could not be"
                    " resized:"
                    " 'https://raw.githubusercontent.com/xhtml2pdf/xhtml2pdf/b01b1d8f9497dedd0f2454409d03408bdeea997c/tests/samples/images.html'"
                ],
            )

    def test_document_cannot_identify_image(self) -> None:
        """Test that images which cannot be identified don't cause stack trace to be printed"""
        image_path = "https://raw.githubusercontent.com/python-pillow/Pillow/7921da54a73dd4a30c23957369b79cda176005c6/Tests/images/zero_width.gif"
        extra_html = f'<img src="{image_path}">'
        with open(os.devnull, "wb") as pdf_file, self.assertLogs(
            "xhtml2pdf.tags", level="WARNING"
        ) as cm:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html=extra_html)),
                dest=pdf_file,
            )
            self.assertEqual(
                cm.output,
                [
                    "WARNING:xhtml2pdf.tags:Cannot identify image file:\n"
                    "'<img "
                    'src="https://raw.githubusercontent.com/python-pillow/Pillow/7921da54a73dd4a30c23957369b79cda176005c6/Tests/images/zero_width.gif"/>\''
                ],
            )

    def test_document_nested_table(self) -> None:
        """Test that nested tables are being rendered."""
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        html_path = os.path.join(tests_folder, "samples", "nested_table.html")

        with open(html_path) as html_file:
            html = html_file.read()

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(src=io.StringIO(html), dest=pdf_file)
            pdf_file.seek(0)
            pdf_reader = PdfReader(pdf_file)
            self.assertEqual(len(pdf_reader.pages), 1)

    @skipIf(IN_PYPY, "This doesn't work in pypy")
    def test_document_creation_without_metadata(self) -> None:
        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                dest=pdf_file,
            )
            self._compare_pdf_metadata(pdf_file, self.assertNotEqual)

    @skipIf(IN_PYPY, "This doesn't work in pypy")
    def test_document_creation_with_metadata(self) -> None:
        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                dest=pdf_file,
                context_meta=METADATA,
            )
            self._compare_pdf_metadata(pdf_file, self.assertEqual)

    @skipIf(IN_PYPY, "This doesn't work in pypy")
    def test_document_creation_with_css_metadata(self) -> None:
        for css_code in CSS_TESTS:
            with tempfile.TemporaryFile() as pdf_file:
                pisaDocument(
                    src=io.StringIO(HTML_CONTENT.format(head=css_code, extra_html="")),
                    dest=pdf_file,
                    context_meta=METADATA,
                )
                self._compare_pdf_metadata(pdf_file, self.assertEqual)

    def test_destination_is_none(self) -> None:
        context = pisaDocument(HTML_CONTENT.format(head="", extra_html=""))
        self.assertGreater(len(context.dest.getvalue()), 0)

    def test_in_memory_document(self) -> None:
        with io.BytesIO() as in_memory_file:
            pisaDocument(
                HTML_CONTENT.format(head="", extra_html=""), dest=in_memory_file
            )
            self.assertGreater(len(in_memory_file.getvalue()), 0)

        with io.BytesIO() as in_memory_file:
            pisaDocument(
                io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                dest=in_memory_file,
            )
            self.assertGreater(len(in_memory_file.getvalue()), 0)
