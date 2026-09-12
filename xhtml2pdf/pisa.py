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
import subprocess
import sys
import urllib.parse as urlparse
from pathlib import Path

from xhtml2pdf import __version__
from xhtml2pdf.config.httpconfig import httpConfig
from xhtml2pdf.config.resources import PERMISSIVE_POLICY, ResourceAccessPolicy
from xhtml2pdf.default import DEFAULT_CSS
from xhtml2pdf.document import pisaDocument
from xhtml2pdf.files import getFile

log = logging.getLogger(__name__)

# Backward compatibility
CreatePDF = pisaDocument

USAGE = (
    """

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
  not writable a similar name will be calculated automatically.

[options]
  --base, -b:
    Specify a base path if input come via STDIN
  --css, -c:
    Path to default CSS file
  --css-dump:
    Dumps the default CSS definitions to STDOUT
  --debug, -d:
    Show debugging information
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

[Resource access options]

  A rendered document may pull in images, stylesheets and fonts. By default a
  document may not reach hosts on internal networks -- loopback, private,
  link-local, which is where cloud metadata services live -- because a
  document that can do that lends its network position to whoever wrote it.
  Local files are not confined on the command line, since the document being
  converted is one you named yourself; --resource-root turns that on.

  --resource-root:
    Confine local reads to this directory (repeatable). The first one given is
    the base; the rest are additional roots.
  --allow-host:
    Allow fetching only from this host (repeatable). Any other remote
    destination is refused, whatever address it resolves to.
  --allow-private-networks:
    Permit internal addresses. Needed to fetch from a host on the LAN.
  --no-remote:
    Refuse http and https altogether; only local resources are used.
  --unsafe-resources:
    Turn all of the above off and fetch anything, as versions before 0.2.19
    did.

[HTTP Connection options]

  --http_nosslcheck:
    No check ssl certificate.

See http.client.HTTPSConnection documentation for this parameters

  --http_key_file
  --http_cert_file
  --http_source_address
  --http_timeout
"""
).strip()

COPYRIGHT = """
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

LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"
LOG_FORMAT_DEBUG = "%(levelname)s [%(name)s] %(pathname)s line %(lineno)d: %(message)s"


def usage():
    print(USAGE)


class pisaLinkLoader:
    """
    Helper to load page from an URL and load corresponding
    files to temporary files. If getFileName is called it
    returns the temporary filename and takes care to delete
    it when pisaLinkLoader is unloaded.
    """

    def __init__(self, src, *, quiet=True) -> None:
        self.quiet = quiet
        self.src = src
        self.tfileList: list[str] = []

    def __del__(self) -> None:
        for path in self.tfileList:
            os.remove(path)

    def getFileName(self, name, relative=None):
        url = urlparse.urljoin(relative or self.src, name)
        instance = getFile(url)
        filetmpdownloaded = instance.getNamedFile()
        path = filetmpdownloaded.name
        self.tfileList.append(path)

        if not self.quiet:
            print(f"  Loading {url} to {path}")

        return path


def command():
    if "--profile" in sys.argv:
        print("*** PROFILING ENABLED")
        import cProfile
        import pstats

        prof = cProfile.Profile()
        prof.runcall(execute)
        pstats.Stats(prof).strip_dirs().sort_stats("cumulative").print_stats()
    else:
        execute()


def execute():
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
                "resource-root=",
                "allow-host=",
                "allow-private-networks",
                "no-remote",
                "unsafe-resources",
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

    errors = 0
    startviewer = 0
    quiet = 0
    file_format = "pdf"
    css = None
    xhtml = None
    encoding = None
    xml_output = None
    base_dir = None
    resource_roots: list[str] = []
    allowed_hosts: list[str] = []
    allow_remote = True
    allow_private_networks = False
    unsafe_resources = False

    log_level = logging.ERROR
    log_format = LOG_FORMAT

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
            print("SYSTEM INFORMATION")
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
            # Output unterdr�cken
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

        elif o == "--resource-root":
            resource_roots.append(a)

        elif o == "--allow-host":
            allowed_hosts.append(a.lower())

        elif o == "--allow-private-networks":
            allow_private_networks = True

        elif o == "--no-remote":
            allow_remote = False

        elif o == "--unsafe-resources":
            unsafe_resources = True

        elif httpConfig.is_http_config(o, a):
            continue

    if not quiet:
        logging.basicConfig(level=log_level, format=log_format)

    if len(args) not in {1, 2}:
        usage()
        sys.exit(2)

    if unsafe_resources:
        resource_policy = PERMISSIVE_POLICY
    else:
        roots = [Path(root) for root in resource_roots]
        resource_policy = ResourceAccessPolicy(
            allow_remote=allow_remote,
            allow_private_networks=allow_private_networks,
            allowed_hosts=frozenset(allowed_hosts) if allowed_hosts else None,
            base_dir=roots[0] if roots else None,
            extra_roots=tuple(roots[1:]),
            # The document named on the command line is the operator's own, so
            # its local resources are as trusted as it is. --resource-root is
            # how a caller converting someone else's HTML asks for confinement.
            allow_local_outside_base=not roots,
        )

    if len(args) == 2:
        a_src, a_dest = args
    else:
        a_src = args[0]
        a_dest = None

    a_src = glob.glob(a_src) if "*" in a_src else [a_src]

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
        elif src.startswith(("http:", "https:")):
            wpath = src
            # The source document is a command-line argument, not something
            # the markup asked for: it is fetched under the caller's own
            # authority, whatever the policy says about the document's
            # resources.
            fsrc = getFile(src, policy=PERMISSIVE_POLICY).getFileContent()
            src = "".join(urlparse.urlsplit(src)[1:3]).replace("/", "-")
        else:
            fsrc = wpath = os.path.abspath(src)
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
            path=wpath,
            link_callback=lc,
            default_css=css,
            xhtml=xhtml,
            encoding=encoding,
            xml_output=xml_output,
            resource_policy=resource_policy,
        )

        if xml_output:
            xml_output.getvalue()

        if fdestclose:
            fdest.close()

        if (not errors) and startviewer:
            if not quiet:
                print("Open viewer for file %s" % dest)
            startViewer(dest)


def startViewer(filename) -> None:
    """
    Open a PDF in the platform's default viewer.

    The file name is passed as a discrete argument, never interpolated into a
    shell string: a destination such as ``x"; rm -rf ~; #.pdf`` is a file name
    here, not a command. Selecting the opener by platform rather than probing
    with ``os.startfile`` also fixes Linux, where the old fallback ran the
    macOS ``open`` and did nothing.
    """
    if not filename:
        return
    if sys.platform == "win32":
        os.startfile(filename)  # Windows-only, no shell involved
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.run([opener, filename], check=False)
    except OSError:
        log.warning("Could not start a viewer for %r: %s not found", filename, opener)


def showLogging(*, debug=False):
    """Shortcut for enabling log dump."""
    try:
        log_level = logging.WARNING
        log_format = LOG_FORMAT_DEBUG
        if debug:
            log_level = logging.DEBUG
        logging.basicConfig(level=log_level, format=log_format)
    except Exception:
        logging.basicConfig()


# Background information in data URI here:
# http://en.wikipedia.org/wiki/Data_URI_scheme


def makeDataURI(data=None, mimetype=None, filename=None):
    import base64

    if not mimetype:
        if filename:
            import mimetypes

            mimetype = mimetypes.guess_type(filename)[0].split(";")[0]
        else:
            msg = "You need to provide a mimetype or a filename for makeDataURI"
            raise RuntimeError(msg)

    encoded_data = base64.encodebytes(data).split()

    return "data:" + mimetype + ";base64," + "".join(encoded_data)


def makeDataURIFromFile(filename):
    with open(filename, "rb") as file_handler:
        data = file_handler.read()
    return makeDataURI(data, filename=filename)


if __name__ == "__main__":
    command()
