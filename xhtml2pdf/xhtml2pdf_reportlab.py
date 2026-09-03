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

import contextlib
import copy
import logging
import sys
from hashlib import md5
from html import escape as html_escape
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import uuid4

from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from PIL.Image import Image
from reportlab.graphics.shapes import Drawing
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import LazyImageReader, flatten, haveImages, open_for_read
from reportlab.pdfbase import pdfform
from reportlab.platypus.doctemplate import (
    BaseDocTemplate,
    IndexingFlowable,
    PageTemplate,
    PTCycle,
)
from reportlab.platypus.flowables import (
    CondPageBreak,
    Flowable,
    KeepInFrame,
    ParagraphAndImage,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.tables import Table, TableStyle
from reportlab.rl_config import register_reset

from xhtml2pdf.files import pisaFileObject, pisaTempFile
from xhtml2pdf.reportlab_paragraph import Paragraph
from xhtml2pdf.util import (
    ImageWarning,
    drawBackgroundImage,
    drawBorderLine,
    getBackgroundImageReader,
    getBackgroundImageSize,
    getBorderWidth,
)

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas


try:
    from reportlab.graphics import renderPM
    from svglib.svglib import svg2rlg
except ImportError:
    svg2rlg = None
    renderPM = None

log = logging.getLogger(__name__)

MAX_IMAGE_RATIO: float = 0.95
PRODUCER: str = "xhtml2pdf <https://github.com/xhtml2pdf/xhtml2pdf/>"


class PmlMaxHeightMixIn:
    def setMaxHeight(self, availHeight: int) -> int:
        self.availHeightValue: int = availHeight
        if availHeight < 70000 and hasattr(self, "canv"):
            if not hasattr(self.canv, "maxAvailHeightValue"):
                self.canv.maxAvailHeightValue = 0
            self.availHeightValue = self.canv.maxAvailHeightValue = max(
                availHeight, self.canv.maxAvailHeightValue
            )
        return self.availHeightValue

    def getMaxHeight(self) -> int:
        return self.availHeightValue if hasattr(self, "availHeightValue") else 0


class PmlBaseDoc(BaseDocTemplate):
    """We use our own document template to get access to the canvas and set some information once."""

    # Stores a list of page templates, and the first page from which they're active.
    pisaTemplateList: list[tuple[int, PmlPageTemplate]]

    def beforeDocument(self) -> None:
        """
        This is called before any processing is done on the document.

        In case of multiBuild is used, this will be called before any build, not just the first.
        """
        # Clear the list of templates, to ensure the list refers to the *final* rendering, also
        # in a multiBuild rendering.
        self.pisaTemplateList = []

        # And the page template left pending by the previous pass. A
        # <pdf:nextpage name="x"/> onto a :left/:right pair leaves a cycle on
        # the document and reportlab never clears it, so on the second pass of
        # a multiBuild every page after the first came out on the mirrored
        # templates whatever the markup said. handle_documentBegin has already
        # chosen this page's template by the time we get here, and the story --
        # with its NextPageTemplate flowables -- is walked again on every pass,
        # so the cycle rebuilds itself where it belongs.
        if not isinstance(self._firstPageTemplateIndex, list):
            # A list is the one case where reportlab has just built the cycle
            # itself, in the two lines above this call.
            for attribute in ("_nextPageTemplateCycle", "_nextPageTemplateIndex"):
                if hasattr(self, attribute):
                    delattr(self, attribute)

    def beforePage(self) -> None:
        self.canv._doc.info.producer = PRODUCER

        """
        # Convert to ASCII because there is a Bug in Reportlab not
        # supporting other than ASCII. Send to list on 23.1.2007
        author = toString(self.pml_data.get("author", "")).encode("ascii","ignore")
        subject = toString(self.pml_data.get("subject", "")).encode("ascii","ignore")
        title = toString(self.pml_data.get("title", "")).encode("ascii","ignore")
        # print repr((author,title,subject))
        self.canv.setAuthor(author)
        self.canv.setSubject(subject)
        self.canv.setTitle(title)
        if self.pml_data.get("fullscreen", 0):
            self.canv.showFullScreen0()
        if self.pml_data.get("showoutline", 0):
            self.canv.showOutline()
        if self.pml_data.get("duration", None) is not None:
            self.canv.setPageDuration(self.pml_data["duration"])
        """

    def afterFlowable(self, flowable: Flowable) -> None:
        # Does the flowable contain fragments?
        if getattr(flowable, "outline", False):
            self.notify(
                "TOCEntry",
                (
                    flowable.outlineLevel,
                    html_escape(copy.deepcopy(flowable.text), quote=True),
                    self.page,
                ),
            )

    def handle_nextPageTemplate(self, pt: str | int | list | tuple) -> None:
        """If pt has also templates for even and odd page convert it to list."""
        has_left_template: bool = self._has_template_for_name(f"{pt}_left")
        has_right_template: bool = self._has_template_for_name(f"{pt}_right")

        if has_left_template and has_right_template:
            pt = [f"{pt}_left", f"{pt}_right"]

        """On endPage change to the page template with name or index pt"""
        if isinstance(pt, str):
            if hasattr(self, "_nextPageTemplateCycle"):
                del self._nextPageTemplateCycle
            for t in self.pageTemplates:
                if t.id == pt:
                    self._nextPageTemplateIndex: int = self.pageTemplates.index(t)
                    return
            msg = f"can't find template('{pt}')"
            raise ValueError(msg)
        if isinstance(pt, int):
            if hasattr(self, "_nextPageTemplateCycle"):
                del self._nextPageTemplateCycle
            self._nextPageTemplateIndex = pt
        elif isinstance(pt, list | tuple):
            # used for alternating left/right pages
            # collect the refs to the template objects, complain if any are bad
            c: PTCycle = PTCycle()
            for ptn in pt:
                # special case name used to short circuit the iteration
                if ptn == "*":
                    c._restart = len(c)  # type: ignore[attr-defined]
                    continue
                for t in self.pageTemplates:
                    if t.id == ptn.strip():
                        c.append(t)
                        break
            if not c:
                msg = "No valid page templates in cycle"
                raise ValueError(msg)
            if c._restart > len(c):  # type: ignore[attr-defined]
                msg = "Invalid cycle restart position"
                raise ValueError(msg)

            # ensure we start on the first one
            # NB: reportlab's BaseDocTemplate._setPageTemplate reads
            # ``_nextPageTemplateCycle.next_value``, so this must be the PTCycle
            # itself and not an iterator over it.
            self._nextPageTemplateCycle: PTCycle = c
        else:
            msg = "Argument pt should be string or integer or list"
            raise TypeError(msg)

    def _has_template_for_name(self, name: str) -> bool:
        return any(template.id == name.strip() for template in self.pageTemplates)


class PmlPageTemplate(PageTemplate):
    PORTRAIT: str = "portrait"
    LANDSCAPE: str = "landscape"
    # by default portrait
    pageorientation: str = PORTRAIT

    #: How the content of a static frame that outgrows its @frame is painted,
    #: when the frame itself does not say. See xhtml2pdf.util.getKeepInFrameMode.
    staticOverflowMode: str = "shrink"

    #: Slack, in points, before a static frame counts as overflowing. Below it
    #: the two measurements are the same number said in different words.
    STATIC_OVERFLOW_FUZZ: float = 0.1

    def __init__(self, **kw) -> None:
        self.pisaStaticList: list = []
        self.pisaBackground: Any = None
        #: Colour propagated from <body> to the page canvas; see CSS 2.1 14.2.
        self.canvasBackground = None
        super().__init__(**kw)
        self._page_count: int = 0
        self._first_flow: bool = True
        #: (complaint, frame id) pairs already logged, so that a hundred-page
        #: document says each one once and not once per page and layout pass.
        self._staticFrameWarned: set[tuple[str, str]] = set()

        # Background Image
        self.img = None
        self.ph: int = 0
        self.h: int = 0
        self.w: int = 0

    def isFirstFlow(self, canvas: Canvas) -> bool:
        if self._first_flow:
            if canvas.getPageNumber() <= self._page_count:
                self._first_flow = False
            else:
                self._page_count = canvas.getPageNumber()
                canvas._doctemplate._page_count = canvas.getPageNumber()
        return self._first_flow

    def isPortrait(self) -> bool:
        return self.pageorientation == self.PORTRAIT

    def isLandscape(self) -> bool:
        return self.pageorientation == self.LANDSCAPE

    def beforeDrawPage(self, canvas: Canvas, doc):
        canvas.saveState()
        try:
            # CSS 2.1 14.2: a background propagated from body paints the whole
            # canvas, underneath everything else including the @page background.
            if self.canvasBackground is not None:
                canvas.saveState()
                canvas.setFillColor(self.canvasBackground)
                canvas.rect(0, 0, self.pagesize[0], self.pagesize[1], stroke=0, fill=1)
                canvas.restoreState()
            if (
                # No template was set yet, or the previous template differs from the last
                not doc.pisaTemplateList
                or doc.pisaTemplateList[-1][-1] != self
            ):
                doc.pisaTemplateList.append((canvas.getPageNumber(), self))

            def pageNumbering(objList):
                for obj in flatten(objList):
                    if isinstance(obj, PmlParagraph):
                        for frag in obj.frags:
                            if frag.pageNumber:
                                frag.text = str(pagenumber)
                            elif frag.pageCount:
                                frag.text = str(canvas._doctemplate._page_count)

                    elif isinstance(obj, PmlTable):
                        # Flatten the cells ([[1,2], [3,4]] becomes [1,2,3,4])
                        flat_cells = [
                            item for sublist in obj._cellvalues for item in sublist
                        ]
                        pageNumbering(flat_cells)

            # Paint static frames
            pagenumber = canvas.getPageNumber()
            if pagenumber > self._page_count:
                self._page_count = pagenumber
                canvas._doctemplate._page_count = pagenumber

            for frame in self.pisaStaticList:
                self._paintStaticFrame(frame, canvas, pageNumbering)
        finally:
            canvas.restoreState()

    def _firstComplaint(self, complaint: str, frame_id: str) -> bool:
        """Whether this is the first time a frame draws this complaint."""
        key = (complaint, frame_id)
        if key in self._staticFrameWarned:
            return False
        self._staticFrameWarned.add(key)
        return True

    @staticmethod
    def _storyHeight(story, frame, canvas: Canvas) -> float:
        """
        The height a static frame's story takes up in that frame.

        Measured with the very calls ``Frame.add`` is about to make, and not
        with ``_listWrapOn``: an image is allowed to scale itself down to the
        height it is offered (see ``PmlParagraph._calcImageMaxSizes``), so
        measuring against unlimited height would report an overflow for a logo
        that fits its header perfectly well. Wrapping is idempotent, so the
        real pass right after this one gets the same numbers.
        """
        used = 0.0
        spaceAfter = 0.0
        for flowable in story:
            # reportlab's Frame swallows the space before a flowable into the
            # space after the one above it; see Frame._add.
            space = max(flowable.getSpaceBefore() - spaceAfter, 0.0) if used else 0.0
            height = flowable.wrapOn(
                canvas, frame._aW, max(frame._aH - used - space, 0.0)
            )[1]
            spaceAfter = flowable.getSpaceAfter()
            used += space + height + spaceAfter
        # The space after the last flowable is not height the frame has to
        # find room for.
        return used - spaceAfter

    def _paintStaticFrame(self, frame, canvas: Canvas, renumber) -> None:
        """
        Draw the story of one static frame on the page being started.

        Anything that goes wrong is caught here, per frame: the guard used to
        sit around the loop over every static frame, so a header that could not
        be painted took the page's footer with it.
        """
        try:
            self._drawStaticFrame(frame, canvas, renumber)
        except Exception:
            frame_id = str(getattr(frame, "id", None))
            log.debug("static frame %r", frame_id, exc_info=True)
            if self._firstComplaint("unpainted", frame_id):
                log.warning("Could not paint the static frame %r", frame_id)

    def _drawStaticFrame(self, frame, canvas: Canvas, renumber) -> None:
        """
        Lay the story of one static frame out and draw it.

        Both the frame and its story are deep-copied first: reportlab consumes
        the list and mutates the flowables and the frame's cursor as it draws,
        and the originals have to survive for every remaining page.
        """
        frame = copy.deepcopy(frame)
        story = frame.pisaStaticStory
        renumber(story)

        # A static frame has no continuation frame, so anything that does not
        # fit is content the page will simply be missing -- most visibly the
        # logo at the end of a header, which is an inline fragment of the last
        # paragraph and so the last flowable of the story.
        needed = self._storyHeight(story, frame, canvas)
        if needed > frame._aH + self.STATIC_OVERFLOW_FUZZ:
            mode = (
                getattr(frame, "pisaStaticOverflowMode", None)
                or self.staticOverflowMode
            )
            if self._firstComplaint("overflow", frame.id):
                log.warning(
                    "The content of the static frame %r needs %.1f pt of"
                    " height and the @frame is %.1f pt tall, so it was fitted"
                    " with -pdf-keep-in-frame-mode: %s. Give the @frame more"
                    " height.",
                    frame.id,
                    needed,
                    frame._aH,
                    mode,
                )
            # KeepInFrame is the only thing a Frame will accept here: for
            # truncate and overflow it reports a height that fits and then
            # clips or spills on its own, and for shrink it scales the whole
            # story down. Not PmlKeepInFrame -- that one overrides maxHeight
            # with the largest height seen on the canvas, which is the body
            # frame of some earlier page, and would decide nothing is wrong.
            story = [
                KeepInFrame(
                    maxWidth=frame._aW, maxHeight=frame._aH, mode=mode, content=story
                )
            ]

        frame.addFromList(story, canvas)

        if story and self._firstComplaint("dropped", frame.id):
            # addFromList stops at the first flowable that does not fit and
            # leaves the rest of the list "for later". There is no later here:
            # whatever is still in it is missing from the page.
            log.warning(
                "The static frame %r dropped %d flowable(s) that did not fit.",
                frame.id,
                len(story),
            )


_ctr: int = 1


class PmlImageReader:  # TODO We need a factory here, returning either a class for java or a class for PIL
    """Wraps up either PIL or Java to get data from bitmaps."""

    _cache: ClassVar[dict] = {}
    # Experimental features, disabled by default
    use_cache: bool = False
    use_lazy_loader: bool = False
    process_internal_files: bool = False

    @classmethod
    def _clear_cache(cls) -> None:
        cls._cache.clear()

    @staticmethod
    def _open(fileName) -> tuple[BytesIO | StringIO, bool]:
        """
        Open ``fileName``, falling back to xhtml2pdf's own fetcher.

        reportlab 5 changed ``rl_config.trustedHosts=None`` from "every host is
        trusted" to "no host is trusted", so ``open_for_read`` now refuses every
        URL and ``data:`` URI by default. That default is deliberate SSRF
        hardening and must not be reverted from a library, so remote resources
        are routed through ``xhtml2pdf.files`` instead, which applies this
        project's own network policy (timeouts, retries, redirect budget).

        Local paths are unaffected: ``open_for_read`` tries a plain ``open()``
        first. Returns ``(stream, used_fallback)``.
        """
        try:
            return open_for_read(fileName, "b"), False
        except OSError:
            if not isinstance(fileName, str) or not fileName.startswith(
                ("data:", "http://", "https://")
            ):
                raise
            log.debug("open_for_read refused %r, using xhtml2pdf.files", fileName[:80])
            stream = pisaFileObject(fileName).getBytesIO()
            if stream is None:
                msg = f"Cannot open resource {fileName[:80]!r}"
                raise OSError(msg) from None
            return stream, True

    def __init__(self, fileName: PmlImage | Image | str) -> None:
        if isinstance(fileName, PmlImage):
            self.__dict__ = fileName.__dict__  # borgize
            return
            # start with lots of null private fields, to be populated by
        # the relevant engine.
        self.fileName: PmlImage | Image | str = fileName or f"PILIMAGE_{id(self)}"
        self._image: Image = None
        self._width: int | None = None
        self._height: int | None = None
        self._transparent = None
        self._data: bytes | str | None = None
        self._dataA: PmlImageReader | None = None
        self.fp: BytesIO | StringIO | None = None
        if Image and isinstance(fileName, Image):
            self._image = fileName
            self.fp = getattr(fileName, "fp", None)
        else:
            try:
                self.fp, used_fallback = self._open(fileName)
                if self.process_internal_files and isinstance(self.fp, StringIO):
                    data: str = self.fp.read()
                    with contextlib.suppress(Exception):
                        self.fp.close()
                    if self.use_cache:
                        if not self._cache:
                            # a bound method, not dict.clear: reportlab wraps
                            # the callback in a WeakMethod, which rejects
                            # builtin methods
                            register_reset(type(self)._clear_cache)
                        cache_key = md5(data.encode("utf8")).digest()
                        data = self._cache.setdefault(cache_key, data)
                    self.fp = StringIO(data)
                elif (
                    self.use_lazy_loader
                    and isinstance(fileName, str)
                    and not used_fallback
                ):
                    # try Ralf Schmitt's re-opening technique of avoiding too many open files
                    # NB: skipped for the fallback below -- LazyImageReader
                    # re-opens by name via open_for_read on every redraw, which
                    # is exactly the call that failed in the first place.
                    self.fp.close()
                    del self.fp  # will become a property in the next statement
                    self.__class__ = LazyImageReader
                if haveImages:
                    # detect which library we are using and open the image
                    if not self._image:
                        self._image = self._read_image(self.fp)
                    if getattr(self._image, "format", None) == "JPEG":
                        self.jpeg_fh = self._jpeg_fh
                else:
                    from reportlab.pdfbase.pdfutils import readJPEGInfo

                    try:
                        self._width, self._height, c = readJPEGInfo(self.fp)
                    except Exception as e:
                        msg = (
                            "Imaging Library not available, unable to import bitmaps"
                            " only jpegs"
                        )
                        raise ImageWarning(msg) from e
                    self.jpeg_fh = self._jpeg_fh
                    self._data = self.fp.read()
                    self.fp.seek(0)
            # Catch all errors that are known and don't need the stack trace
            except UnidentifiedImageError as e:
                msg = "Cannot identify image file"
                raise ImageWarning(msg) from e

    @staticmethod
    def _read_image(fp) -> Image:
        if sys.platform[:4] == "java":
            from java.io import ByteArrayInputStream
            from javax.imageio import ImageIO

            input_stream = ByteArrayInputStream(fp.read())
            return ImageIO.read(input_stream)
        return PILImage.open(fp)

    def _jpeg_fh(self) -> BytesIO | StringIO | None:
        fp = self.fp
        if isinstance(fp, BytesIO | StringIO):
            fp.seek(0)
        return fp

    def jpeg_fh(self) -> BytesIO | StringIO | None:  # noqa: PLR6301
        """Might be replaced with _jpeg_fh in some cases"""
        return None

    def getSize(self) -> tuple[int, int]:
        if self._width is None or self._height is None:
            if sys.platform[:4] == "java":
                self._width = self._image.getWidth()
                self._height = self._image.getHeight()
            else:
                self._width, self._height = self._image.size
            if TYPE_CHECKING:
                assert self._width is not None and self._height is not None
        return self._width, self._height

    def getRGBData(self) -> bytes | str:
        """Return byte array of RGB data as string."""
        if self._data is None:
            self._dataA = None
            if sys.platform[:4] == "java":
                import jarray  # TODO: Move to top.
                from java.awt.image import PixelGrabber

                width, height = self.getSize()
                buffer = jarray.zeros(width * height, "i")
                pg: PixelGrabber = PixelGrabber(
                    self._image, 0, 0, width, height, buffer, 0, width
                )
                pg.grabPixels()
                # there must be a way to do this with a cast not a byte-level loop,
                # I just haven't found it yet...
                pixels: list[str] = []
                a = pixels.append
                for rgb in buffer:
                    a(chr((rgb >> 16) & 0xFF))
                    a(chr((rgb >> 8) & 0xFF))
                    a(chr(rgb & 0xFF))
                self._data = "".join(pixels)
                self.mode = "RGB"
            else:
                im = self._image
                mode = self.mode = im.mode
                if mode == "RGBA":
                    im.load()
                    self._dataA = PmlImageReader(im.split()[3])
                    im = im.convert("RGB")
                    self.mode = "RGB"
                elif mode not in {"L", "RGB", "CMYK"}:
                    im = im.convert("RGB")
                    self.mode = "RGB"
                self._data = im.tobytes() if hasattr(im, "tobytes") else im.tostring()
        return self._data

    def getImageData(self):
        width, height = self.getSize()
        return width, height, self.getRGBData()

    def getTransparent(self):
        if sys.platform[:4] == "java":
            return None
        if "transparency" in self._image.info:
            transparency = self._image.info["transparency"] * 3
            palette = self._image.palette
            if hasattr(palette, "palette"):
                palette = palette.palette
            elif hasattr(palette, "data"):
                palette = palette.data
            else:
                return None

            # 8-bit PNGs could give an empty string as transparency value, so
            # we have to be careful here.
            try:
                return list(palette[transparency : transparency + 3])
            except Exception as e:
                log.debug(str(e), exc_info=e)
                return None
        else:
            return None

    def __str__(self) -> str:
        if isinstance(self.fileName, PmlImage | Image | BytesIO):
            fn = self.fileName.read() or id(self)
            return f"PmlImageObject_{hash(fn)}"
        return str(self.fileName or id(self))


class PmlImage(Flowable, PmlMaxHeightMixIn):
    def __init__(
        self,
        data: pisaFileObject | pisaTempFile | bytes,
        src: str | None = None,
        width: int | None = None,
        height: int | None = None,
        mask: str = "auto",
        mimetype: str | None = None,
        **kw: dict,
    ) -> None:
        self.kw: dict = kw
        self.hAlign: str = "CENTER"
        self._mask: str = mask
        self._imgdata: bytes = b""
        if isinstance(data, bytes):
            self._imgdata = data
        elif isinstance(data, pisaTempFile):
            self._imgdata = data.getvalue()
        elif isinstance(data, pisaFileObject):
            self._imgdata = data.getData() or b""
        self.src: str | None = src
        # print "###", repr(data)
        self.mimetype: str | None = mimetype

        # Resolve size
        drawing = self.getDrawing()
        self.imageWidth: float = 0.0
        self.imageHeight: float = 0.0
        if drawing:
            _, _, self.imageWidth, self.imageHeight = drawing.getBounds() or (
                0,
                0,
                0,
                0,
            )
        else:
            img = self.getImage()
            if img:
                self.imageWidth, self.imageHeight = img.getSize()

        self.drawWidth: float = width or self.imageWidth
        self.drawHeight: float = height or self.imageHeight

    def wrap(self, availWidth, availHeight):
        """
        Resize the image if necessary.

        This can be called more than once! Do not overwrite important data like drawWidth.
        """
        availHeight = self.setMaxHeight(availHeight)
        # print "image wrap", id(self), availWidth, availHeight, self.drawWidth, self.drawHeight
        width = min(self.drawWidth, availWidth)
        wfactor = float(width) / self.drawWidth
        height = min(self.drawHeight, availHeight * MAX_IMAGE_RATIO)
        hfactor = float(height) / self.drawHeight
        factor = min(wfactor, hfactor)
        self.dWidth = self.drawWidth * factor
        self.dHeight = self.drawHeight * factor
        # print "image result", factor, self.dWidth, self.dHeight
        return self.dWidth, self.dHeight

    def getDrawing(
        self, width: float | None = None, height: float | None = None
    ) -> Drawing | None:
        """If this image is a vector image and the library is available, returns a ReportLab Drawing."""
        if svg2rlg:
            try:
                drawing = svg2rlg(BytesIO(self._imgdata))
            except Exception:
                return None
            if drawing:
                # Apply size
                scale_x = 1
                scale_y = 1
                try:
                    if getattr(self, "drawWidth", None) is not None:
                        if width is None:
                            width = self.drawWidth
                        scale_x = width / drawing.width
                    if getattr(self, "drawHeight", None) is not None:
                        if height is None:
                            height = self.drawHeight
                        scale_y = height / drawing.height
                    if scale_x != 1 or scale_y != 1:
                        drawing.scale(scale_x, scale_y)
                except ZeroDivisionError:
                    log.warning(
                        "SVG drawing could not be resized: %r",
                        self.src or self._imgdata[:50],
                    )
                return drawing
        return None

    def getDrawingRaster(self) -> BytesIO | None:
        """If this image is a vector image and the libraries are available, returns a PNG raster."""
        if svg2rlg and renderPM:
            svg: Drawing = self.getDrawing()
            if svg:
                imgdata = BytesIO()
                renderPM.drawToFile(svg, imgdata, fmt="PNG")
                return imgdata
        return None

    def getImage(self) -> PmlImageReader:
        """Return a raster image."""
        vectorRaster = self.getDrawingRaster()
        imgdata = vectorRaster or BytesIO(self._imgdata)
        return PmlImageReader(imgdata)

    def draw(self) -> None:
        # TODO this code should work, but untested
        # drawing = self.getDrawing(self.dWidth, self.dHeight)
        # if drawing and renderPDF:
        #     renderPDF.draw(drawing, self.canv, 0, 0)
        # else:
        img = self.getImage()
        self.canv.drawImage(img, 0, 0, self.dWidth, self.dHeight, mask=self._mask)

    def identity(self, maxLen=None):
        return Flowable.identity(self, maxLen)


class PmlParagraphAndImage(ParagraphAndImage, PmlMaxHeightMixIn):
    def wrap(self, availWidth, availHeight):
        self.I.canv = self.canv
        result = ParagraphAndImage.wrap(self, availWidth, availHeight)
        del self.I.canv
        return result

    def split(self, availWidth, availHeight):
        # print "# split", id(self)
        if not hasattr(self, "wI"):
            self.wI, self.hI = self.I.wrap(
                availWidth, availHeight
            )  # drawWidth, self.I.drawHeight
        return ParagraphAndImage.split(self, availWidth, availHeight)


class PmlParagraph(Paragraph, PmlMaxHeightMixIn):
    def _calcImageMaxSizes(self, availWidth, availHeight):
        self.hasImages = False
        for frag in self.frags:
            if hasattr(frag, "cbDefn") and frag.cbDefn.kind == "img":
                img = frag.cbDefn
                if img.width > 0 and img.height > 0:
                    self.hasImages = True
                    width = min(img.width, availWidth)
                    wfactor = float(width) / img.width
                    height = min(
                        img.height, availHeight * MAX_IMAGE_RATIO
                    )  # XXX 99% because 100% do not work...
                    hfactor = float(height) / img.height
                    factor = min(wfactor, hfactor)
                    img.height *= factor
                    img.width *= factor

    def wrap(self, availWidth, availHeight):
        availHeight = self.setMaxHeight(availHeight)

        style = self.style

        # A border only takes up room when its style says it is drawn; see
        # util.getBorderWidth.
        self.borderWidthLeft = getBorderWidth(
            style.borderLeftStyle, style.borderLeftWidth
        )
        self.borderWidthRight = getBorderWidth(
            style.borderRightStyle, style.borderRightWidth
        )
        self.borderWidthTop = getBorderWidth(style.borderTopStyle, style.borderTopWidth)
        self.borderWidthBottom = getBorderWidth(
            style.borderBottomStyle, style.borderBottomWidth
        )

        self.deltaWidth = (
            style.paddingLeft
            + style.paddingRight
            + self.borderWidthLeft
            + self.borderWidthRight
        )
        self.deltaHeight = (
            style.paddingTop
            + style.paddingBottom
            + self.borderWidthTop
            + self.borderWidthBottom
        )

        # reduce the available width & height by the padding so the wrapping
        # will use the correct size
        availWidth -= self.deltaWidth
        availHeight -= self.deltaHeight

        # Modify maximum image sizes
        self._calcImageMaxSizes(availWidth, availHeight)

        # call the base class to do wrapping and calculate the size
        Paragraph.wrap(self, availWidth, availHeight)

        # self.height = max(1, self.height)
        # self.width = max(1, self.width)

        # increase the calculated size by the padding
        self.width += self.deltaWidth
        self.height += self.deltaHeight

        return self.width, self.height

    def split(self, availWidth, availHeight):
        if len(self.frags) <= 0:
            return []

        # the split information is all inside self.blPara
        if not hasattr(self, "deltaWidth"):
            self.wrap(availWidth, availHeight)

        availWidth -= self.deltaWidth
        availHeight -= self.deltaHeight

        return Paragraph.split(self, availWidth, availHeight)

    def draw(self):
        # Create outline
        if getattr(self, "outline", False):
            # Check level and add all levels
            last = getattr(self.canv, "outlineLast", -1) + 1
            while last < self.outlineLevel:
                # print "(OUTLINE",  last, self.text
                key = uuid4().hex
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(self.text, key, last, not self.outlineOpen)
                last += 1
            self.canv.outlineLast = self.outlineLevel

            key = uuid4().hex

            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(
                self.text, key, self.outlineLevel, not self.outlineOpen
            )
            last += 1

        # Draw the background and borders here before passing control on to
        # ReportLab. This is because ReportLab can't handle the individual
        # components of the border independently. This will also let us
        # support more border styles eventually.
        canvas = self.canv
        style = self.style
        bg = style.backColor
        leftIndent = style.leftIndent
        bp = 0  # style.borderPadding

        x = leftIndent - bp
        y = -bp
        w = self.width - (leftIndent + style.rightIndent) + 2 * bp
        h = self.height + 2 * bp

        if bg:
            # draw a filled rectangle (with no stroke) using bg color
            canvas.saveState()
            canvas.setFillColor(bg)
            canvas.rect(x, y, w, h, fill=1, stroke=0)
            canvas.restoreState()

        # CSS 2.1 14.2: the image goes over the colour and under the content.
        # Before this, background-image existed only on @page; on an element
        # the property was parsed, cascaded and then dropped.
        background_image = getattr(style, "backgroundImage", None)
        if background_image is not None:
            reader = getBackgroundImageReader(background_image)
            if reader is not None:
                drawBackgroundImage(
                    canvas,
                    reader,
                    x,
                    y,
                    w,
                    h,
                    natural=getBackgroundImageSize(reader),
                    repeat=getattr(style, "backgroundRepeat", "repeat"),
                    position=getattr(style, "backgroundPosition", "0% 0%"),
                    font_size=style.fontSize,
                )

        # we need to hide the bg color (if any) so Paragraph won't try to draw it again
        style.backColor = None

        # offset the origin to compensate for the padding
        canvas.saveState()
        canvas.translate(
            (style.paddingLeft + getattr(self, "borderWidthLeft", 0)),
            -1 * (style.paddingTop + getattr(self, "borderWidthTop", 0)),
        )  # + (style.leading / 4)))

        # Call the base class draw method to finish up
        Paragraph.draw(self)
        canvas.restoreState()

        # Reset color because we need it again if we run 2-PASS like we
        # do when using TOC
        style.backColor = bg

        canvas.saveState()

        def _drawBorderLine(bstyle, width, color, x1, y1, x2, y2):
            # If no color for border is given, the text color is used (like
            # defined by W3C)
            if color is None:
                color = style.textColor
            drawBorderLine(canvas, bstyle, width, color, x1, y1, x2, y2)

        _drawBorderLine(
            style.borderLeftStyle,
            style.borderLeftWidth,
            style.borderLeftColor,
            x,
            y,
            x,
            y + h,
        )
        _drawBorderLine(
            style.borderRightStyle,
            style.borderRightWidth,
            style.borderRightColor,
            x + w,
            y,
            x + w,
            y + h,
        )
        _drawBorderLine(
            style.borderTopStyle,
            style.borderTopWidth,
            style.borderTopColor,
            x,
            y + h,
            x + w,
            y + h,
        )
        _drawBorderLine(
            style.borderBottomStyle,
            style.borderBottomWidth,
            style.borderBottomColor,
            x,
            y,
            x + w,
            y,
        )

        canvas.restoreState()


class PmlKeepInFrame(KeepInFrame, PmlMaxHeightMixIn):
    def wrap(self, availWidth, availHeight):
        availWidth = max(availWidth, 1.0)
        availHeight = max(availHeight, 1.0)
        self.maxWidth = availWidth
        self.maxHeight = self.setMaxHeight(availHeight)
        return KeepInFrame.wrap(self, availWidth, availHeight)


class PmlTable(Table, PmlMaxHeightMixIn):
    @staticmethod
    def _normWidth(w, maxw):
        """Normalize width when using percentages."""
        if isinstance(w, str):
            w = (maxw / 100.0) * float(w[:-1])
        elif (w is None) or (w == "*"):
            w = maxw
        return min(w, maxw)

    def _listCellGeom(self, V, w, s, W=None, H=None, aH=72000):
        # print "#", self.availHeightValue
        if aH == 72000:
            aH = self.getMaxHeight() or aH
        return Table._listCellGeom(self, V, w, s, W=W, H=H, aH=aH)

    def wrap(self, availWidth, availHeight):
        self.setMaxHeight(availHeight)

        # Strange bug, sometime the totalWidth is not set !?
        if not hasattr(self, "totalWidth"):
            self.totalWidth = availWidth

        # Prepare values
        totalWidth = self._normWidth(self.totalWidth, availWidth)
        remainingWidth = totalWidth
        remainingCols = 0
        newColWidths = self._colWidths

        # Calculate widths that are fix
        # IMPORTANT!!! We can not substitute the private value
        # self._colWidths therefore we have to modify list in place
        for i, colWidth in enumerate(newColWidths):
            if colWidth is not None:
                newColWidth = self._normWidth(colWidth, totalWidth)
                remainingWidth -= newColWidth
            else:
                remainingCols += 1
                newColWidth = None
            newColWidths[i] = newColWidth

        # Distribute remaining space
        minCellWidth = totalWidth * 0.01
        if remainingCols > 0:
            for i, colWidth in enumerate(newColWidths):
                if colWidth is None:
                    newColWidths[i] = max(
                        minCellWidth, remainingWidth / remainingCols
                    )  # - 0.1

        # Bigger than totalWidth? Lets reduce the fix entries propotionally

        if sum(newColWidths) > totalWidth:
            quotient = totalWidth / sum(newColWidths)
            for i in range(len(newColWidths)):
                newColWidths[i] *= quotient

        # To avoid rounding errors adjust one col with the difference
        diff = sum(newColWidths) - totalWidth
        if diff > 0:
            newColWidths[0] -= diff

        return Table.wrap(self, availWidth, availHeight)


class PmlPageCount(IndexingFlowable):
    def __init__(self) -> None:
        super().__init__()
        self.second_round = False

    def isSatisfied(self):
        s = self.second_round
        self.second_round = True
        return s

    def drawOn(self, canvas, x, y, _sW=0):
        pass


class PmlTableOfContents(TableOfContents):
    def wrap(self, availWidth, availHeight):
        """All table properties should be known by now."""
        widths = (availWidth - self.rightColumnWidth, self.rightColumnWidth)

        # makes an internal table which does all the work.
        # we draw the LAST RUN's entries!  If there are
        # none, we make some dummy data to keep the table
        # from complaining
        if len(self._lastEntries) == 0:
            _tempEntries = [(0, "Placeholder for table of contents", 0)]
        else:
            _tempEntries = self._lastEntries

        lastMargin = 0
        tableData = []
        tableStyle = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]
        for i, entry in enumerate(_tempEntries):
            level, text, pageNum = entry[:3]
            leftColStyle = self.levelStyles[level]
            if i:  # Not for first element
                tableStyle.append(
                    (
                        "TOPPADDING",
                        (0, i),
                        (-1, i),
                        max(lastMargin, leftColStyle.spaceBefore),
                    )
                )
                # print leftColStyle.leftIndent
            lastMargin = leftColStyle.spaceAfter
            # right col style is right aligned
            rightColStyle = ParagraphStyle(
                name="leftColLevel%d" % level,
                parent=leftColStyle,
                leftIndent=0,
                alignment=TA_RIGHT,
            )
            leftPara = Paragraph(text, leftColStyle)
            rightPara = Paragraph(str(pageNum), rightColStyle)
            tableData.append([leftPara, rightPara])

        self._table = Table(tableData, colWidths=widths, style=TableStyle(tableStyle))

        self.width, self.height = self._table.wrapOn(self.canv, availWidth, availHeight)
        return self.width, self.height


class PmlRightPageBreak(CondPageBreak):
    def __init__(self) -> None:
        pass

    def wrap(self, availWidth, availHeight):
        if not self.canv.getPageNumber() % 2:
            self.width = availWidth
            self.height = availHeight
            return availWidth, availHeight
        self.width = self.height = 0
        return 0, 0


class PmlLeftPageBreak(CondPageBreak):
    def __init__(self) -> None:
        pass

    def wrap(self, availWidth, availHeight):
        if self.canv.getPageNumber() % 2:
            self.width = availWidth
            self.height = availHeight
            return availWidth, availHeight
        self.width = self.height = 0
        return 0, 0


# --- Pdf Form


class PmlDrawing(Drawing):
    """
    A drawing that keeps to the box it was given, and to the frame.

    reportlab's Drawing is a fixed-size flowable holding contents of an
    unrelated size: a chart asked to be 400 points wide inside a 200 point
    canvas simply draws past it, over whatever sits alongside, and nothing
    clips or warns. And a canvas wider than the frame it lands in overflows
    the same way.

    wrap() already multiplies by renderScale and renderScaledDrawing applies
    it when the drawing is rendered, so fitting the width is a matter of
    choosing the scale.
    """

    # Declared, not assigned: reportlab carries these on Drawing through its
    # own _attrMap, which is untyped, so mypy would otherwise infer them from
    # the self-referential assignments in fit_contents and give up.
    width: float
    height: float
    renderScale: float

    def wrap(self, availWidth: float, availHeight: float):
        if availWidth > 0 and self.width > availWidth:
            self.renderScale = availWidth / self.width
        return super().wrap(availWidth, availHeight)

    def fit_contents(self, description: str = "drawing") -> None:
        """
        Grow the box to hold whatever ended up in it, and say so.

        Growing rather than clipping: the point is that the layout reserves
        the room the chart actually takes, so the flowable after it is not
        drawn over.
        """
        try:
            x1, y1, x2, y2 = self.getBounds()
        except (ValueError, AttributeError):  # an empty drawing has no bounds
            return

        if x1 < 0 or y1 < 0:
            self.shift(max(-x1, 0), max(-y1, 0))
            x2 += max(-x1, 0)
            y2 += max(-y1, 0)

        if x2 > self.width or y2 > self.height:
            log.warning(
                "The contents of a %s do not fit in its %gx%g box and need"
                " %gx%g; making room for them",
                description,
                self.width,
                self.height,
                x2,
                y2,
            )
            self.width = max(self.width, x2)
            self.height = max(self.height, y2)


class PmlInput(Flowable):
    def __init__(
        self,
        name,
        input_type="text",
        width=10,
        height=10,
        default="",
        options=None,
        multiline=0,
    ) -> None:
        self.width = width
        self.height = height
        self.type = input_type
        self.name = name
        self.default = default
        self.options = options if options is not None else []
        self.multiline = multiline

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        c = self.canv

        c.saveState()
        c.setFont("Helvetica", 10)
        if self.type == "text":
            pdfform.textFieldRelative(
                c,
                self.name,
                0,
                0,
                self.width,
                self.height,
                # The value the markup gave the field. It was never passed on,
                # so <input value="x"> and the contents of a <textarea> came
                # out as empty fields.
                value=self.default or "",
                multiline=self.multiline,
            )
            c.rect(0, 0, self.width, self.height)
        elif self.type == "hidden":
            # A field with no size: it holds its value and takes no room,
            # which is what a hidden input is for. Nothing was drawn at all
            # before, so the value never reached the form.
            pdfform.textFieldRelative(
                c, self.name, 0, 0, 0, 0, value=self.default or ""
            )
        elif self.type == "radio":
            c.rect(0, 0, self.width, self.height)
        elif self.type == "checkbox":
            if self.default:
                pdfform.buttonFieldRelative(c, self.name, "Yes", 0, 0)
            else:
                pdfform.buttonFieldRelative(c, self.name, "Off", 0, 0)
            c.rect(0, 0, self.width, self.height)
        elif self.type == "select":
            pdfform.selectFieldRelative(
                c, self.name, self.default, self.options, 0, 0, self.width, self.height
            )
            c.rect(0, 0, self.width, self.height)

        c.restoreState()
