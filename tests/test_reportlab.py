import unittest
from xhtml2pdf import xhtml2pdf_reportlab


class PTCycleTest(unittest.TestCase):
    def test_init(self):
        xhtml2pdf_reportlab.PTCycle()

    def test_cyclicIterator(self):
        ptcycle = xhtml2pdf_reportlab.PTCycle()
        ptcycle.extend(range(10))
        for ele in ptcycle:
            pass


class PmlMaxHeightMixInTest(unittest.TestCase):
    def test_setMaxHeight_height_lt_70000(self):
        pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
        pmlmaxheightmixin.setMaxHeight(69999)

    # def test_setMaxHeight_height_lt_70000_and_canv(self):
    #     pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
    #     pmlmaxheightmixin.setMaxHeight(69999)

    # def test_setMaxHeight_height_lt_70000_and_canv_with_height(self):
    #     pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
    #     pmlmaxheightmixin.setMaxHeight(69999)

    def test_setMaxHeight_height_gte_70000(self):
        pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
        pmlmaxheightmixin.setMaxHeight(70000)

    def test_getMaxHeight(self):
        pmlmaxheightmixin = xhtml2pdf_reportlab.PmlMaxHeightMixIn()
        self.assertEqual(0, pmlmaxheightmixin.getMaxHeight())
        pmlmaxheightmixin.availHeightValue = 42
        self.assertEqual(42, pmlmaxheightmixin.getMaxHeight())


if __name__ == "__main__":
    unittest.main()
