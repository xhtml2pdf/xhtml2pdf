"""
<pdf:insertpdf>: the pages of another PDF, inside the document.

The tag reserves one page of the layout per page it inserts (PdfInsertPage),
so they are numbered and counted like the others. Once the document is built,
whatever was drawn on each reserved page is cleared and the source page is
merged onto it. The page object itself stays, so links, outline entries and
the table of contents that point at it still do.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import TYPE_CHECKING

import pypdf
from pypdf.generic import DictionaryObject, NameObject, NumberObject, RectangleObject

from xhtml2pdf.config.resources import ResourceAccessError, current_policy
from xhtml2pdf.files import InlineDataURI, NetworkFileUri

if TYPE_CHECKING:
    from xhtml2pdf.files import pisaFileObject
    from xhtml2pdf.xhtml2pdf_reportlab import PmlBaseDoc

log = logging.getLogger(__name__)

#: One item of a pages="..." list: a page, or a range with either end open.
_PAGE_ITEM = re.compile(r"^(\d*)\s*(-)?\s*(\d*)$")

#: The page boxes a reserved page takes over from its source page.
_BOXES = ("/CropBox", "/BleedBox", "/TrimBox", "/ArtBox")


def read_source(src: pisaFileObject | None) -> tuple[bytes, int] | None:
    """
    The bytes of the PDF `src` names and how many pages it has.

    None, with a warning, when there is nothing to insert: no src, a file
    that cannot be read or is not a PDF, an encrypted one, or one the
    resource policy does not allow.
    """
    if src is None:
        log.warning("Ignoring <pdf:insertpdf> with no src")
        return None
    name = str(src.getAbsPath() or src.uri)[:120]
    if not current_policy().allow_remote_pdf_backgrounds and isinstance(
        src.instance, NetworkFileUri | InlineDataURI
    ):
        log.warning(
            "Blocked by the resource policy: a PDF to insert fetched or inline"
            " (%s) is not allowed",
            name,
        )
        return None
    try:
        data = src.getData()
    except ResourceAccessError as e:
        log.warning("Blocked by the resource policy: %s", e)
        return None
    if not data:
        log.warning("Ignoring <pdf:insertpdf>: cannot read %r", name)
        return None
    try:
        reader = pypdf.PdfReader(BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            log.warning("Ignoring <pdf:insertpdf>: %r is encrypted", name)
            return None
        count = len(reader.pages)
    except Exception:
        # A PDF named by the document is its author's input, and pypdf raises
        # whatever the malformed part of it leads to.
        log.warning("Ignoring <pdf:insertpdf>: cannot read %r", name, exc_info=True)
        return None
    return data, count


def parse_pages(spec: str | None, count: int) -> list[int]:
    """
    The 0-based indexes of the pages `spec` names, in its order.

    `spec` lists 1-based pages and ranges, "1-3, 5, 8-" ("-2" is the first
    two); empty, it is every page. A page the PDF does not have is left out
    with a warning, and so is an item that is not a page or a range.
    """
    if not spec or not spec.strip():
        return list(range(count))
    indexes: list[int] = []
    for item in spec.split(","):
        match = _PAGE_ITEM.match(item.strip())
        if match is None or not any(match.groups()):
            log.warning("Ignoring %r in the pages of <pdf:insertpdf>", item.strip())
            continue
        first, dash, last = match.groups()
        start = int(first) if first else 1
        end = (int(last) if last else count) if dash else start
        if start < 1 or end > count or start > end:
            log.warning(
                "Ignoring %r in the pages of <pdf:insertpdf>: the PDF has %d pages",
                item.strip(),
                count,
            )
            continue
        indexes.extend(range(start - 1, end))
    return indexes


def inserted_pages(doc: PmlBaseDoc) -> set[int]:
    """The 1-based numbers of the pages that hold an inserted page."""
    return {page for page, _source, _index in getattr(doc, "pdfInserts", [])}


def insert_pages(doc: PmlBaseDoc, istream: BytesIO) -> BytesIO | None:
    """
    The built document with the inserted pages in place, or None if it has
    none, in which case it is not read back at all.
    """
    inserts = getattr(doc, "pdfInserts", [])
    if not inserts:
        return None
    if getattr(doc, "encrypt", None) is not None:
        # Read back and written again by pypdf, the document would come out
        # unencrypted with an owner password, and not at all with a user one.
        msg = (
            "<pdf:insertpdf> cannot be used with encrypt: the pages are"
            " inserted after the document is built, and the encrypted document"
            " cannot be written again with its encryption."
        )
        raise ValueError(msg)
    writer = pypdf.PdfWriter(clone_from=istream)

    readers: dict[int, pypdf.PdfReader] = {}
    for number, source, index in inserts:
        reader = readers.get(id(source))
        if reader is None:
            reader = readers[id(source)] = pypdf.PdfReader(BytesIO(source))
            if reader.is_encrypted:
                reader.decrypt("")
        page = writer.pages[number - 1]
        insert = reader.pages[index]
        for key in ("/Contents", "/Annots", *_BOXES):
            if key in page:
                del page[key]
        page[NameObject("/Resources")] = DictionaryObject()
        page.mediabox = insert.mediabox
        for key in _BOXES:
            if key in insert:
                page[NameObject(key)] = RectangleObject(insert[key])
        page[NameObject("/Rotate")] = NumberObject(insert.rotation)
        page.merge_page(insert)

    output = BytesIO()
    writer.write(output)
    return output
