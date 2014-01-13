# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import glob
import subprocess
import tempfile
import os
import os.path

CONVERT = r"C:\Programme\ImageMagick-6.3.8-Q16\convert.exe"
DIFF = "tortoiseidiff.exe"

__version__ = "0.1"

class VisualObject:

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
        print "EXECUTE", " ".join(a)
        return subprocess.Popen(a, stdout=subprocess.PIPE).communicate()[0]

    def getFiles(self, folder, pattern="*.*"):
        pattern = os.path.join(folder, pattern)
        self.files = [x for x in glob.glob(pattern) if not x.startswith(".")]
        self.files.sort()
        print "FILES", self.files
        return self.files

    def loadFile(self, file, folder=None, delete=True):
        if folder is None:
            folder = self.folder4del = tempfile.mkdtemp(prefix="visualdiff-tmp-")
            delete = True
        print "FOLDER", folder, "DELETE", delete
        source = os.path.abspath(file)
        destination = os.path.join(folder, "image.png")
        self.execute(CONVERT, source, destination)
        self.files4del = self.getFiles(folder, "*.png")
        return folder

    def compare(self, other, chunk=16 * 1024):
        if len(self.files) <> len(other.files):
            return False
        for i in range(len(self.files)):
            a = open(self.files[i], "rb")
            b = open(other.files[i], "rb")
            if a.read() <> b.read():
                return False
        return True

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

def main():

    options, args = getoptions()

    print args

    a = VisualObject()
    b = VisualObject()

    a.loadFile("expected/test-loremipsum.pdf")
    b.files = a.files

    print a.compare(b)

if __name__=="__main__":
    main()
