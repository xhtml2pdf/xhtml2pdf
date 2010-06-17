import unittest
from sx.pisa3.pisa_util import *

_datauri = """data:image/png;base64,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
TkSuQmCC"""

class TestCase(unittest.TestCase):

    def testAbsouluteUri(self):

        # URL
        f = getFile("http://www.holtwick.it")
        c = f.getFile().read(1)

        self.assertEqual(len(c), 1)
        self.assertEqual(c, "<")
        self.assertEqual(f.mimetype, "text/html")

        # Path
        f = getFile("__init__.py")
        c = f.getFile().read(1)

        self.assertEqual(len(c), 1)
        self.assertEqual(c, "f")
        self.assertEqual(f.mimetype, "text/x-python")

        # Data URI
        f = getFile(_datauri)
        c = f.getFile().read(1)

        self.assertEqual(len(c), 1)
        self.assertEqual(c, '\x89')
        self.assertEqual(f.mimetype, "image/png")

    def testRelativeUri(self):

        # URL
        f = getFile("index", basepath="http://www.holtwick.it")
        c = f.getFile().read(1)

        self.assertEqual(len(c), 1)
        self.assertEqual(c, "<")
        self.assertEqual(f.mimetype, "text/html")

        # Path
        base =  os.path.join(os.path.abspath(__file__), os.pardir, os.pardir)
        f = getFile("tests/__init__.py", base)
        c = f.getFile().read(1)

        # print f.mimetype
        self.assertEqual(len(c), 1)
        self.assertEqual(c, "f")
        self.assertEqual(f.mimetype, "text/x-python")

def buildTestSuite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)

def main():
    buildTestSuite()
    unittest.main()

if __name__ == "__main__":
    main()
