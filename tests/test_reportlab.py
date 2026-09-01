from io import BytesIO
from unittest import TestCase

from reportlab.lib.pagesizes import A4
from reportlab.platypus.frames import Frame

from xhtml2pdf import pisa, xhtml2pdf_reportlab


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


class PmlBaseDocTest(TestCase):
    HTML = """
        <html><head><style>
        @page chapter_left  { size: a4 portrait; @frame { left: 2cm; top: 2cm;
                              width: 16cm; height: 24cm; } }
        @page chapter_right { size: a4 portrait; @frame { left: 3cm; top: 2cm;
                              width: 16cm; height: 24cm; } }
        </style></head>
        <body>
        <pdf:nexttemplate name="chapter" />
        <p>one</p>
        <pdf:nextpage />
        <p>two</p>
        </body></html>
    """

    @staticmethod
    def _doc() -> xhtml2pdf_reportlab.PmlBaseDoc:
        doc = xhtml2pdf_reportlab.PmlBaseDoc(BytesIO(), pagesize=A4)
        doc.addPageTemplates(
            [
                xhtml2pdf_reportlab.PmlPageTemplate(
                    id=f"chapter_{side}",
                    frames=[Frame(0, 0, A4[0], A4[1], id=side)],
                    pagesize=A4,
                )
                for side in ("left", "right")
            ]
        )
        return doc

    def test_next_page_template_cycles_left_and_right(self) -> None:
        doc = self._doc()
        doc.handle_nextPageTemplate("chapter")
        cycle = doc._nextPageTemplateCycle
        self.assertEqual(
            [cycle.next_value.id for _ in range(4)],
            ["chapter_left", "chapter_right", "chapter_left", "chapter_right"],
        )

    def test_alternating_templates_render(self) -> None:
        output = BytesIO()
        result = pisa.CreatePDF(self.HTML, dest=output)
        self.assertFalse(result.err)
        self.assertTrue(output.getvalue().startswith(b"%PDF"))


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
