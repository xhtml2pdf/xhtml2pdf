from unittest import TestCase

from xhtml2pdf import xhtml2pdf_reportlab


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
