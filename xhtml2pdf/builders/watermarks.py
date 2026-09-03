from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, cast

import pypdf
from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf.files import pisaFileObject

if TYPE_CHECKING:
    from collections.abc import Iterator
    from tempfile import _TemporaryFileWrapper

    from xhtml2pdf.xhtml2pdf_reportlab import PmlBaseDoc


class WaterMarks:
    @staticmethod
    def get_size_location(
        img, context: dict, pagesize: tuple[int, int], *, is_portrait: bool
    ) -> tuple[int, int, int, int]:
        object_position: tuple[int, int] | None = context.get("object_position")
        cssheight: int | None = cast("int", context.get("height"))
        csswidth: int = cast("int", context.get("width"))
        iw, ih = img.getSize()
        pw, ph = pagesize
        width: int = pw  # min(iw, pw) # max
        wfactor: float = float(width) / iw
        height: int = ph  # min(ih, ph) # max
        hfactor: float = float(height) / ih
        factor_min: float = min(wfactor, hfactor)
        factor_max: float = max(wfactor, hfactor)
        if is_portrait:
            height = ih * factor_min
            width = iw * factor_min
        else:
            height = ih * factor_max
            width = iw * factor_min

        if object_position:
            # x, y, width=None, height=None
            x, y = object_position
        elif is_portrait:
            x, y = 0, ph - height
        else:
            x, y = 0, 0
        if csswidth:
            width = csswidth
        if cssheight:
            height = cssheight

        return x, y, width, height

    @staticmethod
    def get_img_with_opacity(pisafile: pisaFileObject, context: dict) -> BytesIO:
        opacity: float | None = context.get("opacity")
        if opacity:
            file: BytesIO | _TemporaryFileWrapper | None = pisafile.getFile()
            img: Image.Image = Image.open(file)
            img = img.convert("RGBA")
            # Scale the alpha channel that is there rather than replacing it.
            # putalpha with a single number overwrites the whole channel, so
            # the fully transparent pixels of a cut-out PNG -- black, as a
            # rule -- became half opaque and the page came out with a grey
            # rectangle on it instead of the faded figure.
            img.putalpha(img.getchannel("A").point(lambda a: int(a * opacity)))
            iobuff = BytesIO()
            img.save(iobuff, "PNG")
            return iobuff
        return pisafile.getBytesIO()

    @staticmethod
    def generate_pdf_background(
        pisafile: pisaFileObject,
        pagesize: tuple[int, int],
        *,
        is_portrait: bool,
        context: dict | None = None,
    ) -> pisaFileObject:
        """
        Pypdf requires pdf as background so convert image to pdf in temporary file with same page dimensions
        :param pisafile:  Image File
        :param pagesize:  Page size for the new pdf
        """
        # don't move up, we are preventing circular import
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader

        if context is None:
            context = {}

        output: pisaFileObject = pisaFileObject(
            None, "application/pdf"
        )  # build temporary file
        img: PmlImageReader = PmlImageReader(
            WaterMarks.get_img_with_opacity(pisafile, context)
        )
        x, y, width, height = WaterMarks.get_size_location(
            img, context, pagesize, is_portrait=is_portrait
        )

        canvas = Canvas(output.getNamedFile(), pagesize=pagesize)
        canvas.drawImage(img, x, y, width, height, mask="auto")

        canvas.save()

        return output

    @staticmethod
    def get_watermark(doc: PmlBaseDoc, max_numpage: int) -> Iterator:
        if doc.pisaTemplateList:
            pages = [x[0] for x in doc.pisaTemplateList] + [max_numpage + 1]
            pages.pop(0)
            for counter, (page, pagetemplate) in enumerate(doc.pisaTemplateList):
                bgfile = pagetemplate.pisaBackground

                if bgfile is not None and not bgfile.notFound():
                    pgcontext = pagetemplate.backgroundContext
                    if bgfile.getMimeType().startswith("image/"):
                        # The background is an image, we need to generate a PDF backdrop for this
                        # image.
                        bgfile = WaterMarks.generate_pdf_background(
                            bgfile,
                            pagetemplate.pagesize,
                            is_portrait=pagetemplate.isPortrait(),
                            context=pagetemplate.backgroundContext,
                        )

                    yield range(page, pages[counter]), bgfile, int(pgcontext["step"])

    @staticmethod
    def has_backgrounds(doc: PmlBaseDoc) -> bool:
        """Whether any page template of this document asks for a background."""
        return any(
            template.pisaBackground is not None
            and not template.pisaBackground.notFound()
            for _, template in getattr(doc, "pisaTemplateList", [])
        )

    @staticmethod
    def process_doc(
        doc: PmlBaseDoc, istream: bytes, output: bytes
    ) -> tuple[bytes, bool]:
        if not WaterMarks.has_backgrounds(doc):
            # Nothing to merge, so the document is not read back at all. It
            # used to be cloned through pypdf whatever it held, and a document
            # encrypted with a user password cannot be read without it: the
            # documented encrypt="password" aborted the conversion here with
            # FileNotDecryptedError.
            return output, False

        try:
            pdfoutput: pypdf.PdfWriter = pypdf.PdfWriter(clone_from=istream)
        except pypdf.errors.FileNotDecryptedError as exc:
            msg = (
                "a background image cannot be merged into a document encrypted"
                " with a user password: the background is applied after the"
                " document is built, and the encrypted document cannot be read"
                " back. Encrypt with an owner password only, or drop the"
                " background."
            )
            raise ValueError(msg) from exc

        has_bg: bool = False
        for pages, bgouter, step in WaterMarks.get_watermark(doc, len(pdfoutput.pages)):
            bginput: pypdf.PdfReader = pypdf.PdfReader(bgouter.getBytesIO())
            pagebg: pypdf.PageObject = bginput.pages[0]
            for index, ctr in enumerate(pages):
                page: pypdf.PageObject = pdfoutput.pages[ctr - 1]
                if index % step == 0:
                    page.merge_page(pagebg, over=False)
                has_bg = True
        if has_bg:
            pdfoutput.write(output)

        return output, has_bg
