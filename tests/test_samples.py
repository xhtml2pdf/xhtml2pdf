import sys
import glob
import subprocess
import tempfile
import os
import os.path

__version__ = "0.1"

class VisualObject:

    CONVERT = r"C:\Programme\ImageMagick-6.3.8-Q16\convert.exe"
    DIFF = r"C:\Programme\TortoiseSVN\bin\tortoiseidiff.exe"
    SUFFIX = ".png"

    # C:\Programme\gs\gs8.54\bin\gswin32.exe -q -dSAFER -dNOPAUSE -dBATCH -sOutputFile=rl_hello-page%04d.png -sDEVICE=png256 -r144x144 -f test-font-and-styles.pdf
    #

    def __init__(self):
        self.files = []
        self.files4del = []
        self.folder4del = None

    def __del__(self):
        for file in self.files4del:
            os.remove(file)
        self.files4del = []
        if self.folder4del:
            os.rmdir(self.folder4del)
        self.folder4del = None

    def execute(self, *a):
        #print
        #print "EXECUTE", " ".join(a)
        #print
        # os.system(" ".join(a))
        r = subprocess.Popen(a, stdout=subprocess.PIPE).communicate()[0]
        # print r
        return r

    def showDiff(self, left, right):
        return self.execute(self.DIFF, "/fit", "/overlay", "/left:" + left, "/right:" + right)

    def convertFile(self, source, destination):
        self.execute(self.CONVERT, "-strip", source, destination)

    def getFiles(self, folder, pattern="*.*"):
        pattern = os.path.join(folder, pattern)
        self.files = [os.path.abspath(x) for x in glob.glob(pattern)]
        self.files.sort()
        # print "FILES", self.files
        return self.files

    def loadFile(self, file, folder=None, delete=True):
        if folder is None:
            folder = self.folder4del = tempfile.mkdtemp(prefix="visualdiff-tmp-")
            delete = True
        # print "FOLDER", folder, "DELETE", delete
        source = os.path.abspath(file)
        destination = os.path.join(folder, os.path.basename(file) + "-%04d" + self.SUFFIX)
        self.convertFile(source, destination)
        self.getFiles(folder, os.path.basename(file)  + "-????" + self.SUFFIX)
        if delete:
            self.files4del = self.files
        return folder

    def compare(self, other, chunk=16*1024, show=True):
        if not self.files:
            return False, "No files"
        if len(self.files) <> len(other.files):
            return False, "Different number of files"
        for i in range(len(self.files)):
            left = self.files[i]
            right = other.files[i]
            a = open(left, "rb")
            b = open(right, "rb")
            diff = a.read() <> b.read()
            a.close()
            b.close()
            del a
            del b
            if diff:
                if show:
                    self.showDiff(left, right)
                return False, "Difference in file %r" % left
        return True, ""

'''
def getoptions():
    from optparse import OptionParser
    usage = "usage: %prog [options] arg"
    description = """
    Visual Differences
    """.strip()
    version = __version__
    parser = OptionParser(
        usage,
        description=description,
        version=version,
        )
    #parser.add_option(
    #    "-c", "--css",
    #    help="Path to default CSS file",
    #    dest="css",
    #    )
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")
    parser.set_defaults(
        # css=None,
        )
    (options, args) = parser.parse_args()

    #if not (0 < len(args) <= 2):
    #    parser.error("incorrect number of arguments")

    return options, args

def main_command():

    options, args = getoptions()

    print args

    a = VisualObject()
    b = VisualObject()

    a.loadFile("expected/test-loremipsum.pdf")
    b.files = a.files

    print a.compare(b)
'''

import unittest
import sx.pisa3.pisa as pisa
import shutil

class TestCase(unittest.TestCase):

    def testSamples(self):

        # Enable logging
        pisa.showLogging()

        # Calculate paths
        here = os.path.abspath(os.path.join(__file__, os.pardir))
        folder = os.path.join(here, "tmp")
        left = os.path.join(folder, "left")
        right = os.path.join(folder, "right")

        # Cleanup old tests and create new structure
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        os.makedirs(left)
        os.makedirs(right)

        for name in glob.glob(os.path.join(here, "samples", "*.html")):
            # print name

            # Create new PDF
            bname = os.path.basename(name)
            fname = os.path.join(right, bname[:-5] + ".pdf")

            dest = open(fname, "wb")
            pdf = pisa.pisaDocument(
                open(name, "rb"),
                dest,
                path = name)
            dest.close()

            self.assertTrue(not pdf.err, name)

            # New object
            r = VisualObject()
            r.loadFile(fname, right, delete=False)

            # Expected object
            l = VisualObject()
            l.loadFile(name[:-5] + ".pdf", left, delete=False)

            # Compare both and open Diff if differences
            result, msg = l.compare(r)
            self.assertTrue(result, name + ": " + msg)

def buildTestSuite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)

def main():
    buildTestSuite()
    unittest.main()

if __name__ == "__main__":
    main()
