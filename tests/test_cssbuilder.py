import unittest

from xhtml2pdf.context import pisaCSSBuilder

class TestCase(unittest.TestCase):

    def testFrameDimensions(self):
        builder = pisaCSSBuilder(mediumSet=['all'])
        dims = {
            'left': '10pt',
            'top': '20pt',
            'width': '30pt',
            'height': '40pt',
        }
        expected = (10.0, 20.0, 30.0, 40.0)
        result = builder._pisaDimensions(dims, 100, 200)
        self.assertEquals(expected, result)

        dims = {
            'left': '10pt',
            'top': '20pt',
            'bottom': '30pt',
            'right': '40pt',
        }
        expected = (10.0, 20.0, 50.0, 150.0)
        result = builder._pisaDimensions(dims, 100, 200)
        self.assertEquals(expected, result)

        dims = {
            'bottom': '10pt',
            'right': '20pt',
            'width': '70pt',
            'height': '80pt',
        }
        expected = (10.0, 110.0, 70.0, 80.0)
        result = builder._pisaDimensions(dims, 100, 200)
        self.assertEquals(expected, result)

        dims = {
            'left': '10pt',
            'top': '20pt',
            'width': '70pt',
            'height': '80pt',
            'margin-top': '10pt',
            'margin-left': '15pt',
            'margin-bottom': '20pt',
            'margin-right': '25pt',
        }
        expected = (25.0, 30.0, 30.0, 50.0)
        result = builder._pisaDimensions(dims, 100, 200)
        self.assertEquals(expected, result)

        dims = {
            'bottom': '10pt',
            'right': '20pt',
            'width': '70pt',
            'height': '80pt',
            'margin-top': '10pt',
            'margin-left': '15pt',
            'margin-bottom': '20pt',
            'margin-right': '25pt',
        }
        expected = (25.0, 120.0, 30.0, 50.0)
        result = builder._pisaDimensions(dims, 100, 200)
        self.assertEquals(expected, result)

def buildTestSuite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)

def main():
    buildTestSuite()
    unittest.main()

if __name__ == "__main__":
    main()
