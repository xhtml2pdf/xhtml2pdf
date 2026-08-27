import io
import re
from unittest import TestCase

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.platypus.frames import Frame

from xhtml2pdf import pisa, xhtml2pdf_reportlab

UNNAMED_MIRRORED_HTML = """
<html><head><style>
@page :left  { size: a5; @frame l { left: 5mm; right: 35mm; top: 10mm;
               bottom: 10mm; -pdf-frame-border: 1; } }
@page :right { size: a5; @frame r { left: 35mm; right: 5mm; top: 10mm;
               bottom: 10mm; -pdf-frame-border: 1; } }
</style></head>
<body>
<p>one</p><pdf:nextpage/>
<p>two</p><pdf:nextpage/>
<p>three</p>
</body></html>
"""

LEFT_RIGHT_HTML = """
<html><head><style>
@page book { size: a4 portrait; @frame content { left: 1cm; top: 1cm;
             width: 19cm; height: 27cm; } }
@page book:left  { margin-left: 3cm; }
@page book:right { margin-right: 3cm; }
</style></head>
<body>
<pdf:nexttemplate name="book"/>
<p>Page one</p><pdf:nextpage/>
<p>Page two</p><pdf:nextpage/>
<p>Page three</p><pdf:nextpage/>
<p>Page four</p>
</body></html>
"""


#: A document that needs two layout passes -- <pdf:pagecount> forces one --
#: and only switches to the mirrored templates near the end.
MULTIBUILD_HTML = """
<html><head><style>
@page { size: a4 portrait;
  @frame foot { -pdf-frame-content: foot; left: 2cm; right: 2cm;
                bottom: 1cm; height: 1cm; }
  @frame body { left: 2cm; right: 2cm; top: 2cm; bottom: 3cm; } }
@page book { size: a4 portrait;
  @frame content { left: 1cm; top: 2cm; width: 12cm; height: 24cm; } }
@page book:left  { margin-left: 3cm; }
@page book:right { margin-right: 3cm; }
</style></head>
<body>
<div id="foot"><p>footer <pdf:pagenumber> of <pdf:pagecount></p></div>
<p>Page one</p><pdf:nextpage/>
<p>Page two</p><pdf:nextpage/>
<p>Page three</p>
<pdf:nextpage name="book"/>
<p>Page four</p>
</body></html>
"""


class PTCycleTest(TestCase):
    @staticmethod
    def test_init() -> None:
        xhtml2pdf_reportlab.PTCycle()

    @staticmethod
    def test_cyclicIterator() -> None:
        ptcycle = xhtml2pdf_reportlab.PTCycle()
        ptcycle.extend(range(10))
        for _ele in ptcycle:
            pass

    def test_next_value_cycles(self) -> None:
        """
        Reportlab's BaseDocTemplate._setPageTemplate reads ``next_value``.
        A PTCycle that only offers ``cyclicIterator`` breaks page cycling.
        """
        ptcycle = xhtml2pdf_reportlab.PTCycle()
        ptcycle.extend(["a", "b"])
        self.assertEqual(["a", "b", "a", "b"], [ptcycle.next_value for _ in range(4)])


def _page_template(name: str) -> xhtml2pdf_reportlab.PmlPageTemplate:
    return xhtml2pdf_reportlab.PmlPageTemplate(
        id=name, frames=[Frame(0, 0, *A4, id="content")], pagesize=A4
    )


class PmlBaseDocTest(TestCase):
    @staticmethod
    def _doc(*names: str) -> xhtml2pdf_reportlab.PmlBaseDoc:
        doc = xhtml2pdf_reportlab.PmlBaseDoc(io.BytesIO(), pagesize=A4)
        doc.addPageTemplates([_page_template(name) for name in names])
        return doc

    def test_nextPageTemplate_expands_left_right_pair(self) -> None:
        """
        A template with both a _left and a _right variant must produce an
        alternating cycle rather than exiting the interpreter.
        """
        doc = self._doc("book_left", "book_right", "body")
        doc.handle_nextPageTemplate("book")

        cycle = doc._nextPageTemplateCycle
        self.assertEqual(
            ["book_left", "book_right", "book_left"],
            [cycle.next_value.id for _ in range(3)],
        )

    def test_nextPageTemplate_plain_name_sets_index(self) -> None:
        doc = self._doc("body", "other")
        doc.handle_nextPageTemplate("other")
        self.assertEqual(1, doc._nextPageTemplateIndex)
        self.assertFalse(hasattr(doc, "_nextPageTemplateCycle"))

    def test_nextPageTemplate_unknown_name_raises(self) -> None:
        doc = self._doc("body")
        with self.assertRaises(ValueError):
            doc.handle_nextPageTemplate("nope")

    def test_nextPageTemplate_empty_cycle_raises(self) -> None:
        """This error path was unreachable while the stray sys.exit() stood."""
        doc = self._doc("body")
        with self.assertRaises(ValueError):
            doc.handle_nextPageTemplate(["nope"])

    def test_nextPageTemplate_bad_type_raises(self) -> None:
        doc = self._doc("body")
        with self.assertRaises(TypeError):
            doc.handle_nextPageTemplate(3.5)  # type: ignore[arg-type]

    def test_left_right_document_renders(self) -> None:
        """
        End-to-end regression: @page name:left / @page name:right used to make
        pisaDocument raise SystemExit and kill the calling process.
        """
        dest = io.BytesIO()
        result = pisa.pisaDocument(io.StringIO(LEFT_RIGHT_HTML), dest)
        self.assertEqual(0, result.err)

        dest.seek(0)
        pages = PdfReader(dest).pages
        self.assertEqual(4, len(pages))
        self.assertEqual(
            ["Page one", "Page two", "Page three", "Page four"],
            [page.extract_text().strip() for page in pages],
        )


class PmlBaseDocMultiBuildTest(TestCase):
    """
    beforeDocument runs at the start of every pass and clears what the last
    one left behind.

    A <pdf:nextpage name="x"/> onto a :left/:right pair leaves a PTCycle on the
    document, and reportlab never clears it. With a second pass -- which
    <pdf:pagecount> and <pdf:toc> both force -- every page after the first came
    out on the mirrored templates whatever the markup said.
    """

    @staticmethod
    def _doc(*names: str) -> xhtml2pdf_reportlab.PmlBaseDoc:
        doc = xhtml2pdf_reportlab.PmlBaseDoc(io.BytesIO(), pagesize=A4)
        doc.addPageTemplates([_page_template(name) for name in names])
        return doc

    def test_beforeDocument_drops_a_pending_cycle(self) -> None:
        doc = self._doc("book_left", "book_right", "body")
        doc.handle_nextPageTemplate("book")
        self.assertTrue(hasattr(doc, "_nextPageTemplateCycle"))

        doc.beforeDocument()
        self.assertFalse(hasattr(doc, "_nextPageTemplateCycle"))

    def test_beforeDocument_drops_a_pending_index(self) -> None:
        doc = self._doc("body", "other")
        doc.handle_nextPageTemplate("other")
        self.assertTrue(hasattr(doc, "_nextPageTemplateIndex"))

        doc.beforeDocument()
        self.assertFalse(hasattr(doc, "_nextPageTemplateIndex"))

    def test_beforeDocument_keeps_the_cycle_reportlab_just_built(self) -> None:
        """
        handle_documentBegin builds the cycle itself when the first template is
        a list, in the two lines before it calls beforeDocument. That one is
        not a leftover and has to survive.
        """
        doc = self._doc("book_left", "book_right", "body")
        doc._firstPageTemplateIndex = ["book_left", "book_right"]
        doc.handle_nextPageTemplate("book")

        doc.beforeDocument()
        self.assertTrue(hasattr(doc, "_nextPageTemplateCycle"))

    def test_a_second_pass_does_not_move_the_templates(self) -> None:
        """
        End-to-end: the footer belongs to the default template, so a page
        without it is a page that took the mirrored one. Only the last page
        should be missing it.
        """
        dest = io.BytesIO()
        result = pisa.pisaDocument(io.StringIO(MULTIBUILD_HTML), dest)
        self.assertEqual(0, result.err)

        dest.seek(0)
        pages = [page.extract_text() for page in PdfReader(dest).pages]
        self.assertEqual(4, len(pages))
        self.assertEqual(
            [True, True, True, False], ["footer" in text for text in pages]
        )
        self.assertIn("footer 1 of 4", pages[0])


class UnnamedMirroredPairTest(TestCase):
    """
    A stylesheet whose only page rules are @page :left and @page :right
    describes a mirrored document from its first page.

    Nothing used to select those templates: the cycle is built by
    handle_nextPageTemplate, which only runs for a <pdf:nextpage>, so the
    document ran on the synthetic body template and the mirrored rules were
    silently ignored. (Before that, the unnamed form did not even parse.)
    """

    @staticmethod
    def frame_origins(html: str) -> list[str]:
        """The x origin of the frame outline drawn on each page."""
        dest = io.BytesIO()
        result = pisa.pisaDocument(io.StringIO(html), dest)
        assert result.err == 0
        dest.seek(0)
        origins = []
        for page in PdfReader(dest).pages:
            content = page.get_contents().get_data().decode("latin-1")
            found = re.findall(r"n ([\d.]+) [\d.]+ [\d.]+ [\d.]+ re S", content)
            origins.append(found[0] if found else "")
        return origins

    def test_the_document_starts_on_the_pair(self) -> None:
        origins = self.frame_origins(UNNAMED_MIRRORED_HTML)

        self.assertEqual(3, len(origins))
        self.assertTrue(all(origins), origins)
        self.assertEqual(origins[0], origins[2])
        self.assertNotEqual(origins[0], origins[1])

    def test_an_explicit_page_still_says_where_to_start(self) -> None:
        """A declared @page wins; only a document without one starts mirrored."""
        html = UNNAMED_MIRRORED_HTML.replace(
            "<style>",
            "<style>@page { size: a5; @frame b { left: 20mm; right: 20mm;"
            " top: 10mm; bottom: 10mm; -pdf-frame-border: 1; } }",
        )
        origins = self.frame_origins(html)

        self.assertEqual([origins[0]] * 3, origins)


class PmlMaxHeightMixInTest(TestCase):
    @staticmethod
    def test_setMaxHeight_height_lt_70000() -> None:
        pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
        pmlmaxheightmixin.setMaxHeight(69999)

    # def test_setMaxHeight_height_lt_70000_and_canv(self):
    #     pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
    #     pmlmaxheightmixin.setMaxHeight(69999)

    # def test_setMaxHeight_height_lt_70000_and_canv_with_height(self):
    #     pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
    #     pmlmaxheightmixin.setMaxHeight(69999)

    @staticmethod
    def test_setMaxHeight_height_gte_70000() -> None:
        pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
        pmlmaxheightmixin.setMaxHeight(70000)

    def test_getMaxHeight(self) -> None:
        pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
        self.assertEqual(0, pmlmaxheightmixin.getMaxHeight())
        pmlmaxheightmixin.availHeightValue = 42
        self.assertEqual(42, pmlmaxheightmixin.getMaxHeight())
