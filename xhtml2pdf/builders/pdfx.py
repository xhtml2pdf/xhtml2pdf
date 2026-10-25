"""
PDF/X-4 output (ISO 15930-7) for a print shop.

The finished document is read back with pypdf and given what PDF/X-4 asks
of a file beyond its content:

- an output intent naming the printing condition, with its CMYK ICC
  profile embedded;
- XMP metadata with the PDF/X version, matching the Info dictionary;
- a TrimBox on every page;
- DefaultRGB set to sRGB, so that the RGB colours and images of the page are
  colour-managed rather than device-dependent;
- neutral RGB colours (red = green = blue) drawn as DeviceGray, which the
  CMYK press prints on the black plate alone: through the profile, black
  text would come out as a four-ink black, and small type in four inks
  blurs with the slightest misregistration;
- no annotations on the page and no interactive form, which a print file
  has no use for;
- PDF 1.6.

Fonts must be embedded: the fonts that are only selected without drawing a
glyph are taken out, and text set in a font that is not embedded is an
error, as no conforming file can be made of it. Transparency is allowed in
PDF/X-4 and is kept.

The result is built to the standard; it is not validated against it. A
preflight (Acrobat, callas pdfToolbox) or the print shop confirms it.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import pypdf
from pypdf.generic import (
    ArrayObject,
    ContentStream,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from xhtml2pdf.builders.preflight import (
    MAX_FORM_DEPTH,
    drop_idle_fonts,
    replace_stream_data,
    resolve,
    scan,
    unembedded_text_fonts,
    warn,
)

log = logging.getLogger(__name__)

PDFX_VERSION = "PDF/X-4"

#: The annotations PDF/X allows on a page.
PRINT_ANNOTATIONS = frozenset({"/PrinterMark", "/TrapNet"})


@dataclass
class PDFXOptions:
    """
    How to describe the printing condition.

    ``profile`` is the CMYK output profile of the press, as a path or the
    bytes of the ICC file (FOGRA39, GRACoL, SWOP... from the print shop).
    ``condition`` is the identifier of the printing condition, preferably as
    registered at the ICC (`FOGRA39`, `CGATS TR 006`); ``info`` describes it
    for a person.
    """

    profile: bytes
    condition: str
    info: str = ""
    registry: str = "http://www.color.org"

    @classmethod
    def from_argument(cls, value) -> PDFXOptions:
        """Read the ``pdfx`` argument of pisaDocument."""
        if isinstance(value, PDFXOptions):
            return value
        if not isinstance(value, dict) or "profile" not in value:
            msg = (
                "pdfx takes a dict with at least 'profile', the CMYK ICC profile"
                " of the printing condition: pdfx={'profile': 'FOGRA39.icc',"
                " 'condition': 'FOGRA39'}"
            )
            raise ValueError(msg)
        profile = value["profile"]
        if not isinstance(profile, bytes):
            profile = Path(profile).read_bytes()
        check_profile(profile)
        condition = value.get("condition") or profile_description(profile)
        if not condition:
            msg = "pdfx needs a 'condition' naming the printing condition"
            raise ValueError(msg)
        return cls(
            profile=profile,
            condition=condition,
            info=value.get("info", ""),
            registry=value.get("registry", cls.registry),
        )


def check_profile(profile: bytes) -> None:
    """Refuse a profile PDF/X cannot use as the output intent of a CMYK press."""
    min_header = 128
    if len(profile) < min_header or profile[36:40] != b"acsp":
        msg = "the pdfx profile is not an ICC profile"
        raise ValueError(msg)
    if profile[16:20] != b"CMYK":
        space = profile[16:20].decode("latin-1").strip()
        msg = f"the pdfx profile must describe a CMYK press; this one is {space}"
        raise ValueError(msg)
    if profile[12:16] != b"prtr":
        msg = "the pdfx profile must be an output (printer) profile"
        raise ValueError(msg)


def profile_description(profile: bytes) -> str:
    """The description stored in an ICC profile, or "" if it cannot be read."""
    try:
        from PIL import ImageCms

        return ImageCms.getProfileDescription(
            ImageCms.ImageCmsProfile(io.BytesIO(profile))
        ).strip()
    except Exception:
        return ""


def srgb_profile() -> bytes:
    from PIL import ImageCms

    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _icc_stream(writer: pypdf.PdfWriter, profile: bytes, components: int):
    # pypdf has no public way to add an indirect object to a writer.
    stream = DecodedStreamObject()
    stream.set_data(profile)
    stream[NameObject("/N")] = NumberObject(components)
    stream = stream.flate_encode()
    return writer._add_object(stream)


def _pdf_date_to_xmp(value: str | None) -> str:
    """D:YYYYMMDDHHmmSS+hh'mm' as XMP's ISO 8601, or now if it is missing."""
    match = re.match(
        r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:([+-])(\d{2})'?(\d{2}))?",
        str(value or ""),
    )
    if not match:
        return datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    year, month, day, hour, minute, second, sign, tzh, tzm = match.groups()
    zone = f"{sign}{tzh}:{tzm}" if sign else "Z"
    return f"{year}-{month}-{day}T{hour}:{minute}:{second}{zone}"


#: The characters XML 1.0 does not allow, even escaped.
XML_FORBIDDEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _xmp(info: dict, document_id: str) -> bytes:
    def text(key: str) -> str:
        return escape(XML_FORBIDDEN.sub("", str(info.get(key, "") or "")))

    created = _pdf_date_to_xmp(info.get("/CreationDate"))
    modified = _pdf_date_to_xmp(info.get("/ModDate") or info.get("/CreationDate"))
    title = text("/Title")
    author = text("/Author")
    creator = (
        f"\n   <dc:creator><rdf:Seq><rdf:li>{author}</rdf:li></rdf:Seq></dc:creator>"
        if author
        else ""
    )
    packet = f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>{creator}
   <xmp:CreateDate>{created}</xmp:CreateDate>
   <xmp:ModifyDate>{modified}</xmp:ModifyDate>
   <xmp:MetadataDate>{modified}</xmp:MetadataDate>
   <xmp:CreatorTool>{text("/Creator")}</xmp:CreatorTool>
   <pdf:Producer>{text("/Producer")}</pdf:Producer>
   <pdf:Trapped>False</pdf:Trapped>
   <xmpMM:DocumentID>uuid:{document_id}</xmpMM:DocumentID>
   <xmpMM:InstanceID>uuid:{document_id}</xmpMM:InstanceID>
   <xmpMM:VersionID>1</xmpMM:VersionID>
   <xmpMM:RenditionClass>default</xmpMM:RenditionClass>
   <pdfxid:GTS_PDFXVersion>{PDFX_VERSION}</pdfxid:GTS_PDFXVersion>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return packet.encode("utf-8")


def _set_default_rgb(resources, srgb, depth: int = 0) -> None:
    """Make DeviceRGB mean sRGB in these resources and in the forms they hold."""
    resources = resolve(resources)
    if resources is None:
        return
    spaces = resolve(resources.get("/ColorSpace"))
    if spaces is None:
        spaces = DictionaryObject()
        resources[NameObject("/ColorSpace")] = spaces
    spaces[NameObject("/DefaultRGB")] = ArrayObject([NameObject("/ICCBased"), srgb])
    for xobj in (resolve(resources.get("/XObject")) or {}).values():
        xobj = resolve(xobj)
        # A form without resources of its own uses the page's.
        if (
            xobj.get("/Subtype") == "/Form"
            and "/Resources" in xobj
            and depth < MAX_FORM_DEPTH
        ):
            _set_default_rgb(xobj["/Resources"], srgb, depth + 1)


GRAY_FOR_RGB = {b"rg": b"g", b"RG": b"G"}


def _neutral_to_gray(content, pdf):
    """The stream with its neutral RGB colours set as gray, or None if it has none."""
    stream = ContentStream(content, pdf)
    changed = False
    operations = []
    for operands, operator in stream.operations:
        if operator in GRAY_FOR_RGB and len(operands) == 3:
            red, green, blue = (float(value) for value in operands)
            if red == green == blue:
                operands = [FloatObject(red)]
                operator = GRAY_FOR_RGB[operator]
                changed = True
        operations.append((operands, operator))
    if not changed:
        return None
    stream.operations = operations
    return stream


def _gray_neutrals(writer: pypdf.PdfWriter) -> None:
    def forms(resources, depth=0):
        for xobj in (
            resolve((resolve(resources) or {}).get("/XObject")) or {}
        ).values():
            xobj = resolve(xobj)
            if xobj.get("/Subtype") == "/Form" and depth < MAX_FORM_DEPTH:
                yield xobj
                yield from forms(xobj.get("/Resources"), depth + 1)

    done = set()
    for page in writer.pages:
        contents = page.get_contents()
        if contents is not None:
            rewritten = _neutral_to_gray(contents, writer)
            if rewritten is not None:
                page.replace_contents(rewritten)
        for form in forms(page.get("/Resources")):
            if id(form) in done:
                continue
            done.add(id(form))
            rewritten = _neutral_to_gray(form, writer)
            if rewritten is not None:
                replace_stream_data(form, rewritten.get_data())


def _drop_annotations(writer: pypdf.PdfWriter) -> int:
    dropped = 0
    for page in writer.pages:
        annotations = resolve(page.get("/Annots"))
        if not annotations:
            continue
        kept = ArrayObject(
            annotation
            for annotation in annotations
            if resolve(annotation).get("/Subtype") in PRINT_ANNOTATIONS
        )
        dropped += len(annotations) - len(kept)
        if kept:
            page[NameObject("/Annots")] = kept
        else:
            del page[NameObject("/Annots")]
    root = writer.root_object
    if "/AcroForm" in root:
        del root[NameObject("/AcroForm")]
    return dropped


def make_pdfx(data: bytes, options: PDFXOptions) -> bytes:
    """Return `data`, a finished PDF, made into PDF/X-4."""
    writer = pypdf.PdfWriter(clone_from=io.BytesIO(data))

    dropped_fonts = drop_idle_fonts(writer)
    if dropped_fonts:
        log.debug("PDF/X: took out fonts that draw no text: %s", dropped_fonts)
    reports = scan(writer)
    missing = unembedded_text_fonts(reports)
    if missing:
        msg = (
            "PDF/X needs every font embedded, and text is set in fonts that are"
            f" not: {', '.join(missing)}. Give those elements a font-family"
            " loaded with @font-face (a TrueType file); the built-in Helvetica,"
            " Times and Courier are never embedded."
        )
        raise ValueError(msg)
    warn(reports)

    _gray_neutrals(writer)
    srgb = _icc_stream(writer, srgb_profile(), 3)
    for page in writer.pages:
        if "/TrimBox" not in page and "/ArtBox" not in page:
            page.trimbox = page.cropbox
        if "/Resources" not in page:
            page[NameObject("/Resources")] = DictionaryObject()
        _set_default_rgb(page["/Resources"], srgb)

    dropped = _drop_annotations(writer)
    if dropped:
        log.info(
            "PDF/X: left out %d link annotation(s) a print file cannot hold", dropped
        )

    root = writer.root_object
    intent = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/OutputIntent"),
            NameObject("/S"): NameObject("/GTS_PDFX"),
            NameObject("/OutputConditionIdentifier"): TextStringObject(
                options.condition
            ),
            NameObject("/OutputCondition"): TextStringObject(
                options.info or options.condition
            ),
            NameObject("/Info"): TextStringObject(options.info or options.condition),
            NameObject("/RegistryName"): TextStringObject(options.registry),
            NameObject("/DestOutputProfile"): _icc_stream(writer, options.profile, 4),
        }
    )
    root[NameObject("/OutputIntents")] = ArrayObject([writer._add_object(intent)])

    # reportlab writes /Trapped /False, CreationDate and ModDate, which the
    # XMP below repeats.
    writer.add_metadata({"/GTS_PDFXVersion": PDFX_VERSION})
    info = dict(writer.metadata or {})
    if not str(info.get("/Title") or "").strip():
        log.warning(
            "The PDF/X document has no title, which a preflight reports. Give"
            " it one with <title>."
        )
    document_id = uuid.UUID(
        bytes=hashlib.md5(data, usedforsecurity=False).digest(), version=4
    )
    metadata = DecodedStreamObject()
    metadata.set_data(_xmp(info, str(document_id)))
    metadata[NameObject("/Type")] = NameObject("/Metadata")
    metadata[NameObject("/Subtype")] = NameObject("/XML")
    root[NameObject("/Metadata")] = writer._add_object(metadata)

    writer.pdf_header = b"%PDF-1.6"
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
