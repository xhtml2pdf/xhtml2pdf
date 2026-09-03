import io
import os
import tempfile
from importlib.util import find_spec
from unittest import TestCase, skipIf

from pypdf import PdfReader

from xhtml2pdf.document import pisaDocument

from .httpserver import LocalServerMixin

DENKER_TRANSPARENT = os.path.join(
    os.path.dirname(__file__), "samples", "img", "denker-transparent.png"
)

TREE = os.path.join(os.path.dirname(__file__), "samples", "img", "tree.jpg")

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
    f"""<style>
    @page {{
        size: A4 landscape;
        background-image: url('{DENKER_TRANSPARENT}');
        @frame {{left: 10pt}}
        }}
    </style>""",
}

METADATA = {
    "author": "MyCorp Ltd.",
    "title": "My Document Title",
    "subject": "My Document Subject",
    "keywords": "pdf, documents",
}


IN_PYPY = find_spec("__pypy__") is not None


class DocumentTest(LocalServerMixin, TestCase):
    def _compare_pdf_metadata(self, pdf_file, assertion):
        # Ensure something has been written
        self.assertNotEqual(pdf_file.tell(), 0)

        # Rewind to the start of the file to read the pdf and get the
        # document's metadata
        pdf_file.seek(0)
        pdf_reader = PdfReader(pdf_file)
        pdf_info = pdf_reader.metadata

        # Check the received metadata matches the expected metadata
        for original_key, expected_value in METADATA.items():
            actual_key = f"/{original_key.capitalize()}"
            actual_value = pdf_info[actual_key]

            assertion(actual_value, expected_value)

    def test_document_with_transparent_image(self) -> None:
        """Test that a transparent PNG image is rendered properly."""
        extra_html = f'<img src="{DENKER_TRANSPARENT}">'

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
            denker_transparent = [
                obj for obj in objects if obj["/Height"] == 137 and obj["/Width"] == 70
            ]
            self.assertEqual(len(denker_transparent), 1)

    def test_document_background_image(self) -> None:
        """Test that a transparent PNG image is rendered properly."""
        css_background = f"""<style>@page {{background-image: url('{DENKER_TRANSPARENT}');
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
            denker_transparent = [
                obj for obj in objects if obj["/Height"] == 137 and obj["/Width"] == 70
            ]
            self.assertEqual(len(denker_transparent), 1)

    def test_document_background_image_not_on_all_pages(self) -> None:
        """Test that all pages are being rendered, when background is a pdf file and it's applied for the first page only."""
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        background_path = os.path.join(tests_folder, "samples", "images.pdf")

        css = f""""<style>@page {{background-image: url('{background_path}'); @frame {{left: 10pt}}}}
              @page two {{@frame {{left: 10 pt}}}}</style>"""

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

            self.assertIn("/XObject", pdf_reader.pages[0]["/Resources"])
            self.assertNotIn("/XObject", pdf_reader.pages[1]["/Resources"])

    def test_document_background_positioning_and_long_toc(self) -> None:
        """Test that a long toc is taken into account when positioning backgrounds."""
        css = f"""<style>@page {{@frame {{left: 10pt}}}}
              @page two {{background-image: url('{DENKER_TRANSPARENT}'); @frame {{left: 10 pt}}}}</style>"""
        marker_text = "Backgrounds should start from this page onwards."
        extra_html = (
            f"""
                <div>
                    <pdf:toc>
                </div>
                <pdf:nexttemplate name="two">
                <pdf:nextpage>
                <h1>Hello, world!</h1>
                <!-- special text we can test on. -->
                <p>{marker_text}</p>
            """
            + """<h1>Hello, world!</h1>\n""" * 100
        )

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head=css, extra_html=extra_html)),
                dest=pdf_file,
            )
            pdf_file.seek(0)
            pdf_reader = PdfReader(pdf_file)

            seen_marker_text = False
            for page in pdf_reader.pages:
                seen_marker_text |= marker_text in page.extract_text()
                if seen_marker_text:
                    self.assertIn("/XObject", page["/Resources"])
                else:
                    self.assertNotIn("/XObject", page["/Resources"])

            assert seen_marker_text

    def test_document_background_used_when_reusing_templates(self) -> None:
        """Test that a long toc is taken into account when positioning backgrounds."""
        css = f"""<style>
              @page one {{background-image: url('{TREE}'); @frame {{left: 10pt}}}}
              @page two {{background-image: url('{DENKER_TRANSPARENT}'); @frame {{left: 10 pt}}}}
        </style>"""
        extra_html = """
                <pdf:nexttemplate name="one">
                <pdf:nextpage>
                <h1>One</h1>
                <pdf:nexttemplate name="two">
                <pdf:nextpage>
                <h1>Two</h1>
                <pdf:nexttemplate name="one">
                <pdf:nextpage>
                <h1>One</h1>
                <pdf:nexttemplate name="two">
                <pdf:nextpage>
                <h1>Two</h1>
            """

        with tempfile.TemporaryFile() as pdf_file:
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head=css, extra_html=extra_html)),
                dest=pdf_file,
            )
            pdf_file.seek(0)
            pdf_reader = PdfReader(pdf_file)

            for page in pdf_reader.pages:
                if "One" in page.extract_text():
                    objects = page["/Resources"]["/XObject"].get_object().values()
                    self.assertEqual(len(objects), 1)
                    (obj,) = objects
                    # Dimensions of TREE
                    self.assertEqual(obj["/Height"], 180)
                    self.assertEqual(obj["/Width"], 240)
                if "Two" in page.extract_text():
                    objects = page["/Resources"]["/XObject"].get_object().values()
                    self.assertEqual(len(objects), 1)
                    (obj,) = objects
                    # Dimensions of DENKER_TRANSPARENT
                    self.assertEqual(obj["/Height"], 137)
                    self.assertEqual(obj["/Width"], 70)

    @skipIf(os.environ.get("HTTP_PROXY"), reason="Running on proxy")
    def test_document_with_broken_image(self) -> None:
        """Test that broken images don't cause unhandled exception"""
        # Although this is just html, it will be recognized as svg
        image_path = f"{self.base_url}/images.html"
        extra_html = f'<img src="{image_path}">'
        with (
            open(os.devnull, "wb") as pdf_file,
            self.assertLogs("xhtml2pdf.xhtml2pdf_reportlab", level="WARNING") as cm,
        ):
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html=extra_html)),
                dest=pdf_file,
            )
            self.assertEqual(
                cm.output,
                [
                    (
                        "WARNING:xhtml2pdf.xhtml2pdf_reportlab:SVG drawing could not"
                        f" be resized: {image_path!r}"
                    )
                ],
            )

    def test_document_cannot_identify_image(self) -> None:
        """Test that images which cannot be identified don't cause stack trace to be printed"""
        image_path = f"{self.base_url}/img/zero_width.gif"
        extra_html = f'<img src="{image_path}">'
        with (
            open(os.devnull, "wb") as pdf_file,
            self.assertLogs("xhtml2pdf.tags", level="WARNING") as cm,
        ):
            pisaDocument(
                src=io.StringIO(HTML_CONTENT.format(head="", extra_html=extra_html)),
                dest=pdf_file,
            )
            self.assertEqual(
                cm.output,
                [
                    (
                        "WARNING:xhtml2pdf.tags:Cannot identify image file:\n"
                        f"'<img src=\"{image_path}\"/>'"
                    )
                ],
            )

    def test_document_nested_table(self) -> None:
        """Test that nested tables are being rendered."""
        tests_folder = os.path.dirname(os.path.realpath(__file__))
        html_path = os.path.join(tests_folder, "samples", "nested_table.html")

        with open(html_path, encoding="utf-8") as html_file:
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


class CanvasBackgroundTest(TestCase):
    """
    CSS 2.1 14.2: when the html element declares no background of its own, the
    background of body propagates to the canvas, so it covers the whole page
    rather than only the area body's boxes happen to occupy.
    """

    @staticmethod
    def _content(html: str):
        dest = io.BytesIO()
        pisaDocument(io.StringIO(html), dest)
        dest.seek(0)
        page = PdfReader(dest).pages[0]
        return page, page.get_contents().get_data().decode("latin-1")

    @staticmethod
    def _full_page_fill(page, content: str) -> bool:
        width = round(float(page.mediabox.width), 4)
        height = round(float(page.mediabox.height), 4)
        return f"0 0 {width} {height} re" in content

    def test_body_background_covers_the_page(self) -> None:
        page, content = self._content(
            '<html><body style="background-color: #ff0000">x</body></html>'
        )
        self.assertIn("1 0 0 rg", content, "expected a red fill colour")
        self.assertTrue(
            self._full_page_fill(page, content),
            "body background did not propagate to the canvas",
        )

    def test_no_body_background_leaves_the_canvas_alone(self) -> None:
        page, content = self._content("<html><body>x</body></html>")
        self.assertFalse(
            self._full_page_fill(page, content),
            "a page-sized fill appeared without any background declared",
        )

    def test_background_covers_every_page(self) -> None:
        dest = io.BytesIO()
        pisaDocument(
            io.StringIO(
                '<html><body style="background-color: #00ff00">one'
                "<pdf:nextpage/>two</body></html>"
            ),
            dest,
        )
        dest.seek(0)
        pages = PdfReader(dest).pages
        self.assertEqual(2, len(pages))
        for number, page in enumerate(pages, 1):
            with self.subTest(page=number):
                content = page.get_contents().get_data().decode("latin-1")
                self.assertIn("0 1 0 rg", content)
                self.assertTrue(self._full_page_fill(page, content))


class EncryptAndSignTest(TestCase):
    """
    Asking for both says which two arguments are the problem.

    The document is encrypted while it is built and signed afterwards, so
    pyHanko was handed a PDF it had no password for and the call failed with
    PdfKeyNotAvailableError several steps later, from inside a library the
    caller never named.
    """

    HTML = "<html><body><p>x</p></body></html>"

    def test_the_two_together_are_refused(self) -> None:
        with self.assertRaises(ValueError) as raised:
            pisaDocument(
                io.StringIO(self.HTML),
                io.BytesIO(),
                encrypt="password",
                signature={"engine": "simple", "type": "simple"},
            )

        self.assertIn("cannot be combined", str(raised.exception))

    def test_a_user_password_converts(self) -> None:
        """
        The simplest form in the documentation, and it aborted the whole
        conversion: every document was read back through pypdf to apply
        backgrounds, and a document encrypted with a user password cannot be
        read without it, so it died with FileNotDecryptedError.
        """
        dest = io.BytesIO()
        result = pisaDocument(io.StringIO(self.HTML), dest, encrypt="password")

        self.assertEqual(0, result.err)
        dest.seek(0)
        reader = PdfReader(dest)
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt("password"))
        self.assertEqual(1, len(reader.pages))

    def test_a_background_on_an_encrypted_document_says_why_not(self) -> None:
        html = (
            "<html><head><style>@page { background-image:"
            ' url("tests/samples/img/tree.jpg"); }</style></head>'
            "<body><p>x</p></body></html>"
        )

        with self.assertRaises(ValueError) as raised:
            pisaDocument(io.StringIO(html), io.BytesIO(), encrypt="password", path=".")

        self.assertIn("cannot be merged", str(raised.exception))


class ArgumentsThatDoSomethingTest(TestCase):
    """
    Three arguments of pisaDocument promised something and did nothing.

    raise_exception was marked unused and every failure propagated whatever it
    said; show_error_as_pdf did not exist even though pisaErrorDocument was
    written for it, and the WSGI middleware in this package passed it on every
    call; and anything else at all disappeared into **_kwargs, including the
    errout, tempdir and format that this package's own CLI passed.
    """

    #: Not a document, not a path: the conversion cannot even start.
    BROKEN = object()

    def test_a_failure_raises_by_default(self) -> None:
        with self.assertRaises(TypeError):
            pisaDocument(self.BROKEN, io.BytesIO())

    def test_raise_exception_false_returns_the_context(self) -> None:
        context = pisaDocument(self.BROKEN, io.BytesIO(), raise_exception=False)

        self.assertTrue(context.err)

    def test_show_error_as_pdf_writes_the_errors(self) -> None:
        dest = io.BytesIO()
        pisaDocument(self.BROKEN, dest, show_error_as_pdf=True)

        dest.seek(0)
        self.assertIn("error", (PdfReader(dest).pages[0].extract_text() or "").lower())

    def test_an_unknown_argument_is_named(self) -> None:
        with self.assertWarns(DeprecationWarning) as warned:
            pisaDocument(
                io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                io.BytesIO(),
                errout=None,
            )

        self.assertIn("errout", str(warned.warning))

    def test_debug_says_it_does_nothing(self) -> None:
        with self.assertWarns(DeprecationWarning) as warned:
            pisaDocument(
                io.StringIO(HTML_CONTENT.format(head="", extra_html="")),
                io.BytesIO(),
                debug=1,
            )

        self.assertIn("debug", str(warned.warning))
