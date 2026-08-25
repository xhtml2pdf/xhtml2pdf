import io
from unittest import TestCase

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.platypus.frames import Frame

from xhtml2pdf import pisa, xhtml2pdf_reportlab

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
        reportlab's BaseDocTemplate._setPageTemplate reads ``next_value``.
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
            doc.handle_nextPageTemplate(3.5)

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
