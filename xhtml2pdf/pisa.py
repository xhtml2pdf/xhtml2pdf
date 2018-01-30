# -*- coding: utf-8 -*-
"""
Copyright 2010 Dirk Holtwick, holtwick.it

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from xhtml2pdf.default import DEFAULT_CSS
from xhtml2pdf.document import pisaDocument
from xhtml2pdf.util import getFile
from xhtml2pdf import __version__
from xhtml2pdf.config.httpconfig import httpConfig

import getopt
import glob
import logging
import os
import six
import sys
import tempfile
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

log = logging.getLogger("xhtml2pdf")

# Backward compatibility
CreatePDF = pisaDocument

USAGE = ("""

USAGE: pisa [options] SRC [DEST]

SRC
  Name of a HTML file or a file pattern using * placeholder.
  If you want to read from stdin use "-" as file name.
  You may also load an URL over HTTP. Take care of putting
  the <src> in quotes if it contains characters like "?".

DEST
  Name of the generated PDF file or "-" if you like
  to send the result to stdout. Take care that the
  destination file is not already opened by an other
  application like the Adobe Reader. If the destination is
  not writeable a similar name will be calculated automatically.

[options]
  --base, -b:
    Specify a base path if input come via STDIN
  --css, -c:
    Path to default CSS file
  --css-dump:
    Dumps the default CSS definitions to STDOUT
  --debug, -d:
    Show debugging informations
  --encoding:
    the character encoding of SRC. If left empty (default) this
    information will be extracted from the HTML header data
  --help, -h:
    Show this help text
  --quiet, -q:
    Show no messages
  --start-viewer, -s:
    Start PDF default viewer on Windows and MacOSX
    (e.g. AcrobatReader)
  --version:
    Show version information
  --warn, -w:
    Show warnings
  --xml, --xhtml, -x:
    Force parsing in XML Mode
    (automatically used if file ends with ".xml")
  --html:
    Force parsing in HTML Mode (default)
    
[HTTP Connection options]

  --http_nosslcheck:
    No check ssl certificate.
    
See http.client.HTTPSConnection documentation for this parameters 

  --http_key_file
  --http_cert_file
  --http_source_address
  --http_timeout
""").strip()

COPYRIGHT = __doc__

LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"
LOG_FORMAT_DEBUG = "%(levelname)s [%(name)s] %(pathname)s line %(lineno)d: %(message)s"


def usage():
    print (USAGE)


class pisaLinkLoader:
    """
    Helper to load page from an URL and load corresponding
    files to temporary files. If getFileName is called it
    returns the temporary filename and takes care to delete
    it when pisaLinkLoader is unloaded.
    """

    def __init__(self, src, quiet=True):
        self.quiet = quiet
        self.src = src
        self.tfileList = []

    def __del__(self):
        for path in self.tfileList:
            os.remove(path)

    def getFileName(self, name, relative=None):
        url = urlparse.urljoin(relative or self.src, name)
        path = urlparse.urlsplit(url)[2]
        suffix = ""
        if "." in path:
            new_suffix = "." + path.split(".")[-1].lower()
            if new_suffix in (".css", ".gif", ".jpg", ".png"):
                suffix = new_suffix
        path = tempfile.mktemp(prefix="pisa-", suffix=suffix)
        ufile = urllib2.urlopen(url)
        tfile = open(path, "wb")
        while True:
            data = ufile.read(1024)
            if not data:
                break
            tfile.write(data)
        ufile.close()
        tfile.close()
        self.tfileList.append(path)

        if not self.quiet:
            print ("  Loading %s to %s" % (url, path))

        return path


def command():
    if "--profile" in sys.argv:
        print ("*** PROFILING ENABLED")
        import cProfile as profile
        import pstats

        prof = profile.Profile()
        prof.runcall(execute)
        pstats.Stats(prof).strip_dirs().sort_stats('cumulative').print_stats()
    else:
        execute()


def execute():

    try:
        opts, args = getopt.getopt(sys.argv[1:], "dhqstwcxb", [
            "quiet",
            "help",
            "start-viewer",
            "start",
            "debug=",
            "copyright",
            "version",
            "warn",
            "tempdir=",
            "format=",
            "css=",
            "base=",
            "css-dump",
            "xml-dump",
            "xhtml",
            "xml",
            "html",
            "encoding=",
            "system",
            "profile",
            "http_nosslcheck",
            "http_key_file",
            "http_cert_file",
            "http_source_address",
            "http_timeout"
        ])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    errors = 0
    startviewer = 0
    quiet = 0
    debug = 0
    tempdir = None
    format = "pdf"
    css = None
    xhtml = None
    encoding = None
    xml_output = None
    base_dir = None

    log_level = logging.ERROR
    log_format = LOG_FORMAT

    for o, a in opts:
        if o in ("-h", "--help"):
            # Hilfe anzeigen
            usage()
            sys.exit()

        elif o in("--version",):
            print(__version__)
            sys.exit(0)

        elif o in ("--copyright"):
            print (COPYRIGHT)
            sys.exit(0)

        elif o in ("--system",):
            print (COPYRIGHT)
            print ()
            print ("SYSTEM INFORMATIONS")
            print ("--------------------------------------------")
            print ("OS:                %s" % sys.platform)
            print ("Python:            %s" % sys.version)
            print ("html5lib:          ?")
            import reportlab

            print ("Reportlab:         %s" % reportlab.Version)
            sys.exit(0)

        elif o in ("-s", "--start-viewer", "--start"):
            # Anzeigeprogramm starten
            startviewer = 1

        elif o in ("-q", "--quiet"):
            # Output unterdr�cken
            quiet = 1

        elif o in ("-w", "--warn"):
            # Warnings
            log_level = min(log_level, logging.WARN)  # If also -d ignore -w

        elif o in ("-d", "--debug"):
            # Debug
            log_level = logging.DEBUG
            log_format = LOG_FORMAT_DEBUG

            if a:
                log_level = int(a)

        elif o in ("-t", "--format"):
            # Format XXX ???
            format = a

        elif o in ("-b", "--base"):
            base_dir = a

        elif o in ("--encoding",) and a:
            # Encoding
            encoding = a

        elif o in ("-c", "--css"):
            # CSS
            css = open(a, "r").read()

        elif o in ("--css-dump",):
            # CSS dump
            print (DEFAULT_CSS)
            return

        elif o in ("--xml-dump",):
            xml_output = sys.stdout

        elif o in ("-x", "--xml", "--xhtml"):
            xhtml = True
        
        elif o in ("--html",):
            xhtml = False

        elif httpConfig.is_http_config(o, a):
            continue

    if not quiet:
        logging.basicConfig(
            level=log_level,
            format=log_format)

    if len(args) not in (1, 2):
        usage()
        sys.exit(2)

    if len(args) == 2:
        a_src, a_dest = args
    else:
        a_src = args[0]
        a_dest = None

    if "*" in a_src:
        a_src = glob.glob(a_src)
        # print a_src
    else:
        a_src = [a_src]

    for src in a_src:

        # If not forced to parse in a special way have a look
        # at the filename suffix
        if xhtml is None:
            xhtml = src.lower().endswith(".xml")

        lc = None

        if src == "-" or base_dir is not None:
            # Output to console
            fsrc = sys.stdin
            wpath = os.getcwd()
            if base_dir:
                wpath = base_dir
        else:
            if src.startswith("http:") or src.startswith("https:"):
                wpath = src
                fsrc = getFile(src).getFile()
                src = "".join(urlparse.urlsplit(src)[1:3]).replace("/", "-")
            else:
                fsrc = wpath = os.path.abspath(src)
                fsrc = open(fsrc, "rb")

        if a_dest is None:
            dest_part = src
            if dest_part.lower().endswith(".html") or dest_part.lower().endswith(".htm"):
                dest_part = ".".join(src.split(".")[:-1])
            dest = dest_part + "." + format.lower()
            for i in six.moves.range(10):
                try:
                    open(dest, "wb").close()
                    break
                except:
                    pass
                dest = dest_part + "-%d.%s" % (i, format.lower())
        else:
            dest = a_dest

        fdestclose = 0

        if dest == "-" or base_dir:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

            fdest = sys.stdout
            startviewer = 0
        else:
            dest = os.path.abspath(dest)
            try:
                open(dest, "wb").close()
            except:
                print ("File '%s' seems to be in use of another application." % dest)
                sys.exit(2)
            fdest = open(dest, "wb")
            fdestclose = 1

        if not quiet:
            print ("Converting {} to {}...".format(src, dest))

        pisaDocument(
            fsrc,
            fdest,
            debug=debug,
            path=wpath,
            errout=sys.stdout,
            tempdir=tempdir,
            format=format,
            link_callback=lc,
            default_css=css,
            xhtml=xhtml,
            encoding=encoding,
            xml_output=xml_output
        )

        if xml_output:
            xml_output.getvalue()

        if fdestclose:
            fdest.close()

        if (not errors) and startviewer:
            if not quiet:
                print ("Open viewer for file %s" % dest)
            startViewer(dest)


def startViewer(filename):
    """
    Helper for opening a PDF file
    """

    if filename:
        try:
            os.startfile(filename)
        except:
            # try to opan a la apple
            os.system('open "%s"' % filename)


def showLogging(debug=False):
    """
    Shortcut for enabling log dump
    """

    try:
        log_level = logging.WARN
        log_format = LOG_FORMAT_DEBUG
        if debug:
            log_level = logging.DEBUG
        logging.basicConfig(
            level=log_level,
            format=log_format)
    except:
        logging.basicConfig()


# Background informations in data URI here:
# http://en.wikipedia.org/wiki/Data_URI_scheme

def makeDataURI(data=None, mimetype=None, filename=None):
    import base64

    if not mimetype:
        if filename:
            import mimetypes


            mimetype = mimetypes.guess_type(filename)[0].split(";")[0]
        else:
            raise Exception("You need to provide a mimetype or a filename for makeDataURI")
    return "data:" + mimetype + ";base64," + "".join(base64.encodestring(data).split())


def makeDataURIFromFile(filename):
    data = open(filename, "rb").read()
    return makeDataURI(data, filename=filename)


if __name__ == "__main__":
    command()
