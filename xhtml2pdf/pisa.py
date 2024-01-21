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
from __future__ import annotations

import getopt
import glob
import logging
import os
import sys
import urllib.parse as urlparse
from io import BytesIO
from typing import TYPE_CHECKING

from xhtml2pdf import __version__
from xhtml2pdf.config.httpconfig import httpConfig
from xhtml2pdf.default import DEFAULT_CSS
from xhtml2pdf.document import pisaDocument
from xhtml2pdf.files import getFile

if TYPE_CHECKING:
    from collections.abc import Callable
    from io import BufferedWriter
    from typing import TextIO


log = logging.getLogger(__name__)

# Backward compatibility
CreatePDF: Callable = pisaDocument

USAGE: str = ("""

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

COPYRIGHT: str = """
Copyright 2010 Dirk Holtwick, holtwick.it

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

LOG_FORMAT: str = "%(levelname)s [%(name)s] %(message)s"
LOG_FORMAT_DEBUG: str = (
    "%(levelname)s [%(name)s] %(pathname)s line %(lineno)d: %(message)s"
)


def usage() -> None:
    print(USAGE)


class pisaLinkLoader:
    """
    Helper to load page from an URL and load corresponding
    files to temporary files. If getFileName is called it
    returns the temporary filename and takes care to delete
    it when pisaLinkLoader is unloaded.
    """

    def __init__(self, src, *, quiet: bool = True) -> None:
        self.quiet = quiet
        self.src = src
        self.tfileList: list[str] = []

    def __del__(self) -> None:
        for path in self.tfileList:
            os.remove(path)

    def getFileName(self, name: str, relative: str | None = None):
        url = urlparse.urljoin(relative or self.src, name)
        instance = getFile(url)
        path = instance.getNamedFile()
        self.tfileList.append(path)

        if not self.quiet:
            print(f"  Loading {url} to {path}")

        return path


def command() -> None:
    if "--profile" in sys.argv:
        print("*** PROFILING ENABLED")
        # ruff: noqa: PLC0415
        import cProfile
        import pstats

        prof = cProfile.Profile()
        prof.runcall(execute)
        pstats.Stats(prof).strip_dirs().sort_stats("cumulative").print_stats()
    else:
        execute()


def execute() -> None:
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "dhqstwcxb",
            [
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
                "http_timeout",
            ],
        )
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    errors: int = 0
    startviewer: int = 0
    quiet: int = 0
    debug: int = 0
    tempdir: str | None = None
    file_format: str = "pdf"
    css: str | None = None
    xhtml: bool | None = None
    encoding: str | None = None
    xml_output: TextIO | BytesIO | None = None
    base_dir: str | None = None

    log_level: int = logging.ERROR
    log_format: str = LOG_FORMAT

    for o, a in opts:
        if o in {"-h", "--help"}:
            # Hilfe anzeigen
            usage()
            sys.exit()

        elif o == "--version":
            print(__version__)
            sys.exit(0)

        elif o in ("--copyright"):
            print(COPYRIGHT)
            sys.exit(0)

        elif o == "--system":
            print(COPYRIGHT)
            print()
            print("SYSTEM INFORMATIONS")
            print("--------------------------------------------")
            print("OS:                %s" % sys.platform)
            print("Python:            %s" % sys.version)
            print("html5lib:          ?")
            import reportlab

            print("Reportlab:         %s" % reportlab.Version)
            sys.exit(0)

        elif o in {"-s", "--start-viewer", "--start"}:
            # Anzeigeprogramm starten
            startviewer = 1

        elif o in {"-q", "--quiet"}:
            # Suppress output
            quiet = 1

        elif o in {"-w", "--warn"}:
            # Warnings
            log_level = min(log_level, logging.WARNING)  # If also -d ignore -w

        elif o in {"-d", "--debug"}:
            # Debug
            log_level = logging.DEBUG
            log_format = LOG_FORMAT_DEBUG

            if a:
                log_level = int(a)

        elif o in {"-t", "--format"}:
            # Format XXX ???
            file_format = a

        elif o in {"-b", "--base"}:
            base_dir = a

        elif o == "--encoding" and a:
            # Encoding
            encoding = a

        elif o in {"-c", "--css"}:
            # CSS
            with open(a, encoding="utf-8") as file_handler:
                css = file_handler.read()

        elif o == "--css-dump":
            # CSS dump
            print(DEFAULT_CSS)
            return

        elif o == "--xml-dump":
            xml_output = sys.stdout

        elif o in {"-x", "--xml", "--xhtml"}:
            xhtml = True

        elif o == "--html":
            xhtml = False

        elif httpConfig.is_http_config(o, a):
            continue

    if not quiet:
        logging.basicConfig(level=log_level, format=log_format)

    if len(args) not in {1, 2}:
        usage()
        sys.exit(2)

    if len(args) == 2:
        a_src, a_dest = args
    else:
        a_src = args[0]
        a_dest = None

    a_src_list = glob.glob(a_src) if "*" in a_src else [a_src]

    for src in a_src_list:
        # If not forced to parse in a special way have a look
        # at the filename suffix
        if xhtml is None:
            xhtml = src.lower().endswith(".xml")

        lc = None
        fsrc: TextIO | bytes | str | None

        if src == "-" or base_dir is not None:
            # Output to console
            fsrc = sys.stdin
            wpath = os.getcwd()
            if base_dir:
                wpath = base_dir
        elif src.startswith(("http:", "https:")):
            wpath = src
            fsrc = getFile(src).getFileContent()
            src = "".join(urlparse.urlsplit(src)[1:3]).replace("/", "-")
        else:
            fsrc = wpath = os.path.abspath(src)
            if TYPE_CHECKING:
                assert isinstance(fsrc, str)
            with open(fsrc, "rb") as file_handler:
                fsrc = file_handler.read()

        if a_dest is None:
            dest_part = src
            if dest_part.lower().endswith(".html") or dest_part.lower().endswith(
                ".htm"
            ):
                dest_part = ".".join(src.split(".")[:-1])
            dest = dest_part + "." + file_format.lower()
            for i in range(10):
                try:
                    with open(dest, "wb") as file:
                        file.close()
                    break
                except Exception:
                    pass
                dest = dest_part + "-%d.%s" % (i, file_format.lower())
        else:
            dest = a_dest

        fdest: BufferedWriter | TextIO
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
                with open(dest, "wb") as file:
                    file.close()
            except Exception:
                print("File '%s' seems to be in use of another application." % dest)
                sys.exit(2)
            fdest = open(dest, "wb")  # noqa: SIM115
            fdestclose = 1

        if not quiet:
            print(f"Converting {src} to {dest}...")

        pisaDocument(
            fsrc,
            fdest,
            debug=debug,
            path=wpath,
            errout=sys.stdout,
            tempdir=tempdir,
            format=file_format,
            link_callback=lc,
            default_css=css,
            xhtml=xhtml,
            encoding=encoding,
            xml_output=xml_output,
        )

        if isinstance(xml_output, BytesIO):
            xml_output.getvalue()

        if fdestclose:
            fdest.close()

        if (not errors) and startviewer:
            if not quiet:
                print("Open viewer for file %s" % dest)
            startViewer(dest)


def startViewer(filename: str) -> None:
    """Helper for opening a PDF file."""
    if filename:
        try:
            os.startfile(filename)  # type: ignore[attr-defined]
        except Exception:
            # try to opan a la apple
            os.system('open "%s"' % filename)


def showLogging(*, debug: bool = False) -> None:
    """Shortcut for enabling log dump."""
    try:
        log_level = logging.WARNING
        log_format = LOG_FORMAT_DEBUG
        if debug:
            log_level = logging.DEBUG
        logging.basicConfig(level=log_level, format=log_format)
    except Exception:
        logging.basicConfig()


# Background informations in data URI here:
# http://en.wikipedia.org/wiki/Data_URI_scheme


def makeDataURI(
    data: bytes, mimetype: str | None = None, filename: str | None = None
) -> str:
    import base64

    if not mimetype:
        if not filename:
            msg = "You need to provide a mimetype or a filename for makeDataURI"
            raise RuntimeError(msg)

        import mimetypes

        mimetype, _encoding = mimetypes.guess_type(filename)

        if not mimetype:
            msg = "The mimetype could not be derived from the filename"
            raise RuntimeError(msg)

        mimetype = mimetype.split(";")[0]

    encoded_data = base64.encodebytes(data).decode("UTF-8")

    return f"data:{mimetype};base64,{encoded_data}"


def makeDataURIFromFile(filename: str) -> str:
    with open(filename, "rb") as file_handler:
        data = file_handler.read()
    return makeDataURI(data, filename=filename)


if __name__ == "__main__":
    command()
