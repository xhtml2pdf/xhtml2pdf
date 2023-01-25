import base64
import gzip
import http.client as httplib
import logging
import mimetypes
import re
import sys
import tempfile
import threading
import urllib.parse as urlparse
from io import BytesIO
from pathlib import Path
from urllib import request
from urllib.parse import unquote as urllib_unquote

from xhtml2pdf.config.httpconfig import httpConfig

GAE = "google.appengine" in sys.modules
log = logging.getLogger("xhtml2pdf")
if GAE:
    STRATEGIES = (
        BytesIO,
        BytesIO)
else:
    STRATEGIES = (
        BytesIO,
        tempfile.NamedTemporaryFile)


class TmpFiles(threading.local):

    files = []

    def append(self, file):
        self.files.append(file)

    def cleanFiles(self):
        for file in self.files:
            file.close()
        self.files.clear()


files_tmp = TmpFiles()  # permanent safe file, to prevent file close


class pisaTempFile(object):
    """
    A temporary file implementation that uses memory unless
    either capacity is breached or fileno is requested, at which
    point a real temporary file will be created and the relevant
    details returned
    If capacity is -1 the second strategy will never be used.
    Inspired by:
    http://code.activestate.com/recipes/496744/
    """

    STRATEGIES = STRATEGIES

    CAPACITY = 10 * 1024

    def __init__(self, buffer="", capacity=CAPACITY):
        """Creates a TempFile object containing the specified buffer.
        If capacity is specified, we use a real temporary file once the
        file gets larger than that size.  Otherwise, the data is stored
        in memory.
        """
        self.name = None
        self.capacity = capacity
        self.strategy = int(len(buffer) > self.capacity)
        try:
            self._delegate = self.STRATEGIES[self.strategy]()
        except IndexError:
            # Fallback for Google AppEnginge etc.
            self._delegate = self.STRATEGIES[0]()
        self.write(buffer)
        # we must set the file's position for preparing to read
        self.seek(0)

    def makeTempFile(self):
        """
        Switch to next startegy. If an error occured,
        stay with the first strategy
        """

        if self.strategy == 0:
            try:
                new_delegate = self.STRATEGIES[1]()
                new_delegate.write(self.getvalue())
                self._delegate = new_delegate
                self.strategy = 1
                log.warning("Created temporary file %s", self.name)
            except:
                self.capacity = - 1

    def getFileName(self):
        """
        Get a named temporary file
        """

        self.makeTempFile()
        return self.name

    def fileno(self):
        """
        Forces this buffer to use a temporary file as the underlying.
        object and returns the fileno associated with it.
        """
        self.makeTempFile()
        return self._delegate.fileno()

    def getvalue(self):
        """
        Get value of file. Work around for second strategy.
        Always returns bytes
        """

        if self.strategy == 0:
            return self._delegate.getvalue()
        self._delegate.flush()
        self._delegate.seek(0)
        value = self._delegate.read()
        if not isinstance(value, bytes):
            value = value.encode('utf-8')
        return value

    def write(self, value):
        """
        If capacity != -1 and length of file > capacity it is time to switch
        """

        if self.capacity > 0 and self.strategy == 0:
            len_value = len(value)
            if len_value >= self.capacity:
                needs_new_strategy = True
            else:
                self.seek(0, 2)  # find end of file
                needs_new_strategy = \
                    (self.tell() + len_value) >= self.capacity
            if needs_new_strategy:
                self.makeTempFile()

        if not isinstance(value, bytes):
            value = value.encode('utf-8')

        self._delegate.write(value)

    def __getattr__(self, name):
        try:
            return getattr(self._delegate, name)
        except AttributeError:
            # hide the delegation
            e = "object '%s' has no attribute '%s'" \
                % (self.__class__.__name__, name)
            raise AttributeError(e)


class BaseFile:
    def __init__(self, path, basepath):
        self.path = path
        self.basepath = basepath
        self.mimetype = None
        self.suffix = None
        self.uri = None

    def get_uri(self):
        return self.uri

    def get_mimetype(self):
        return self.mimetype

    def get_named_tmp_file(self):
        data = self.get_data()
        tmp_file = tempfile.NamedTemporaryFile(suffix=self.suffix)
        # print(tmp_file.name, len(data))
        if data:
            tmp_file.write(data)
            tmp_file.flush()
            files_tmp.append(tmp_file)
        if self.path is None:
            self.path = tmp_file.name
        return tmp_file

    def get_BytesIO(self):
        data = self.get_data()
        if data:
            return BytesIO(data)


class B64InlineURI(BaseFile):
    _rx_datauri = re.compile(
        "^data:(?P<mime>[a-z]+/[a-z]+);base64,(?P<data>.*)$", re.M | re.DOTALL)

    def get_data(self):
        try:
            return self.extract_data()
        except Exception as e:
            log.error("Extract data form data: in tag")

    def extract_data(self):
        m = self._rx_datauri.match(self.path)
        self.mimetype = m.group("mime")

        b64 = urllib_unquote(m.group("data"))

        # The data may be incorrectly unescaped... repairs needed
        b64 = b64.strip("b'").strip("'").encode()
        b64 = re.sub(b"\\n", b'', b64)
        b64 = re.sub(b'[^A-Za-z0-9\\+\\/]+', b'', b64)

        # Add padding as needed, to make length into a multiple of 4
        #
        b64 += b"=" * ((4 - len(b64) % 4) % 4)

        return base64.b64decode(b64)


class LocalProtocolURI(BaseFile):

    def get_data(self):
        try:
            return self.extract_data()
        except Exception as e:
            log.error("Extract data form local file based on protocol")

    def extract_data(self):
        if self.basepath and self.path.startswith('/'):
            uri = urlparse.urljoin(self.basepath, self.path[1:])
            urlResponse = request.urlopen(uri)
            self.mimetype = urlResponse.info().get(
                "Content-Type", '').split(";")[0]
            return urlResponse.read()


class NetworkFileUri(BaseFile):
    def __init__(self, path, basepath):
        super().__init__(path, basepath)
        self.attempts = 3
        self.actual_attempts = 0

    def get_data(self):
        data = None
        # try several attempts if network problems happens
        while self.attempts > self.actual_attempts and data is None:
            self.actual_attempts += 1
            try:
                data = self.extract_data()
            except Exception as e:
                log.error("Extract data remote trying %d" % self.actual_attempts)
        return data

    def get_httplib(self, uri):
        log.debug(f"Sending request for {uri} with httplib")
        data, is_gzip = None, False
        url_splitted = urlparse.urlsplit(uri)
        server = url_splitted[1]
        path = url_splitted[2]
        path += "?" + url_splitted[3] if url_splitted[3] else ""

        if uri.startswith("https://"):
            conn = httplib.HTTPSConnection(server, **httpConfig)
        else:
            conn = httplib.HTTPConnection(server)
        conn.request("GET", path)
        r1 = conn.getresponse()
        if (r1.status, r1.reason) == (200, "OK"):
            self.mimetype = r1.getheader(
                "Content-Type", '').split(";")[0]
            data = r1.read()
            if r1.getheader("content-encoding") == "gzip":
                is_gzip = True
        else:
            log.debug(f"Received non-200 status: {r1.status} {r1.reason}")
        return data, is_gzip

    def extract_data(self):
        # FIXME: When self.path don't start with http
        if self.basepath and not self.path.startswith("http"):
            uri = urlparse.urljoin(self.basepath, self.path)
        else:
            uri = self.path
        self.uri = uri
        data, is_gzip = self.get_httplib(uri)
        if is_gzip:
            data = gzip.GzipFile(mode="rb", fileobj=BytesIO(data))
        log.debug("Uri parsed: {}".format(uri))
        return data


class LocalFileURI(BaseFile):
    def get_data(self):
        try:
            return self.extract_data()
        except Exception as e:
            log.error("Extract data form local file")

    def guess_mimetype(self, name):
        " Guess the mime type "
        mimetype = mimetypes.guess_type(str(name))[0]
        if mimetype is not None:
            mimetype = mimetypes.guess_type(str(name))[0].split(";")[0]
        return mimetype

    def extract_data(self):
        data = None
        log.debug("Unrecognized scheme, assuming local file path")
        path = Path(self.path)
        uri = None
        if self.basepath is not None:
            uri = Path(self.basepath) / path
        else:
            uri = Path('.') / path
        if path.exists() and not uri.exists():
            uri = path
        if uri.is_file():
            self.uri = uri
            self.suffix = uri.suffix
            self.mimetype = self.guess_mimetype(uri)
            if self.mimetype and self.mimetype.startswith('text'):
                with open(uri, "r") as file_handler:
                    # removed bytes... lets hope it goes ok :/
                    data = file_handler.read()
            else:
                with open(uri, "rb") as file_handler:
                    # removed bytes... lets hope it goes ok :/
                    data = file_handler.read()
        return data


class BytesFileUri(BaseFile):
    def get_data(self):
        return self.path


class LocalTmpFile(BaseFile):

    def __init__(self, path, basepath):
        self.path = path
        self.basepath = None
        self.mimetype = basepath
        self.suffix = None
        self.uri = None

    def get_named_tmp_file(self):
        tmp_file = super().get_named_tmp_file()
        if self.path is None:
            self.path = tmp_file.name
        return tmp_file

    def get_data(self):
        if self.path is None:
            return
        with open(self.path, 'rb') as arch:
            return arch.read()


class FileNetworkManager:
    @staticmethod
    def get_manager(uri, basepath=None):
        if uri is None:
            instance = LocalTmpFile(uri, basepath)
            return instance
        if isinstance(uri, bytes):
            instance = BytesFileUri(uri, basepath)
        elif uri.startswith("data:"):
            instance = B64InlineURI(uri, basepath)
        else:
            if basepath and not urlparse.urlparse(uri).scheme:
                urlParts = urlparse.urlparse(basepath)
            else:
                urlParts = urlparse.urlparse(uri)

            log.debug("URLParts: {}".format((urlParts, urlParts.scheme)))
            if urlParts.scheme == 'file':
                instance = LocalProtocolURI(uri, basepath)
            elif urlParts.scheme in ('http', 'https'):
                instance = NetworkFileUri(uri, basepath)
            else:
                instance = LocalFileURI(uri, basepath)
        return instance


class pisaFileObject:
    def __init__(self, uri, basepath=None, callback=None):
        self.uri = uri
        basepathret = None
        if callback is not None:
            basepathret = callback(uri, basepath)
        if basepathret is not None:
            self.basepath = None
            uri=basepathret
        else:
            self.basepath = basepath
        #uri = uri or str()
        # if not isinstance(uri, str):
        #    uri = uri.decode("utf-8")
        log.debug("FileObject %r, Basepath: %r", uri, basepath)

        self.instance = FileNetworkManager.get_manager(uri, basepath=self.basepath)

    def getFileContent(self):
        return self.instance.get_data()

    def getNamedFile(self):
        f = self.instance.get_named_tmp_file()
        if f:
            return f.name

    def getData(self):
        return self.instance.get_data()

    def getFile(self):
        if GAE:
            return self.instance.get_BytesIO()
        return self.instance.get_named_tmp_file()

    def getMimeType(self):
        return self.instance.get_mimetype()

    def notFound(self):
        return self.getData() is None

    def getAbsPath(self):
        return self.instance.get_uri()

    def getBytesIO(self):
        return self.instance.get_BytesIO()


def getFile(*a, **kw):
    return pisaFileObject(*a, **kw)


def cleanFiles():
    files_tmp.cleanFiles()
