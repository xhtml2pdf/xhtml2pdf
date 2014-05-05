import unittest
from xhtml2pdf.parser import pisaParser
from xhtml2pdf.context import pisaContext

_data = """
<!doctype html>
<html>
<title>TITLE</title>
<body>
BODY
</body>
</html>
"""

class TestCase(unittest.TestCase):

    def testParser(self):
        c = pisaContext(".")
        r = pisaParser(_data, c)
        self.assertEqual(c, r)

    def test_getFile(self):
        c = pisaContext(".")
        r = pisaParser(_data, c)
        self.assertEqual(c.getFile(None), None)

def buildTestSuite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)

def main():
    buildTestSuite()
    unittest.main()

if __name__ == "__main__":
    main()
