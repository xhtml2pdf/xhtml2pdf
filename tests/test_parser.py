import unittest
from sx.pisa3.pisa_parser import pisaParser
from sx.pisa3.pisa_context import pisaContext
import StringIO

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

def buildTestSuite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)

def main():
    buildTestSuite()
    unittest.main()

if __name__ == "__main__":
    main()
