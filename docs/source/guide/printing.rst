======================
Printing (print shops)
======================

A PDF for a commercial printer differs from one for the screen. The printer
cuts the paper, so the page needs a trim size, a bleed and crop marks. The
press prints with cyan, magenta, yellow and black inks, so colours are best
named in CMYK, or at least tied to a colour profile. Every font has to be in
the file, and images need enough pixels for the size they are printed at.
xhtml2pdf covers these with the CSS below and with a PDF/X-4 mode.

Bleed and crop marks
--------------------

.. code:: html

   <style>
   @page {
       size: a5;
       margin: 15mm;
       bleed: 3mm;
       marks: crop cross;
   }
   body { background-color: #f4e9d8; }
   </style>

``size`` is the trim size: the size of the sheet after it is cut, and the
area the layout fills. ``bleed`` (CSS Paged Media) grows the PDF page around
it. The page background, the background propagated from ``<body>`` and an
``@page`` ``background-image`` all reach into the bleed, so a slightly-off
cut leaves no white edge. ``marks`` adds a 12 mm margin outside the bleed,
the slug, with:

- ``crop``: crop marks at the corners of the trim;
- ``cross``: registration targets in the middle of each side.

The marks are drawn in registration colour, so they show on every plate.
``bleed: auto``, the default, is 6pt with marks and none without them.

Every page with bleed or marks gets a ``TrimBox`` and a ``BleedBox``, which
is how the printer's software knows where to cut. Each ``@page`` has its own
values, so a cover can bleed while the inside pages do not.

CMYK colours
------------

.. code:: css

   h1 { color: device-cmyk(0 1 1 0); }               /* CSS Color 5 */
   .band { background-color: cmyk(100%, 0, 0, 0); }
   .tint { color: device-cmyk(0 0 0 1 / 0.5); }      /* with alpha */

``device-cmyk()`` and ``cmyk()`` take four inks, each a number from 0 to 1
or a percentage, separated by spaces or commas, and an optional alpha after
a slash. They are written to the PDF in DeviceCMYK, exactly as given. They
work in HTML colour attributes too: ``<font color="cmyk(0,0,1,0)">``.

RGB colours and images stay RGB. The printer converts them with its
profile, or, in PDF/X mode, they are tagged as sRGB (see below). For text,
plain black is best given as ``device-cmyk(0 0 0 1)``: the black plate
alone.

Images
------

Images are embedded as they are: JPEGs byte for byte, so a CMYK JPEG stays
CMYK, and other formats without loss. Nothing is resampled. The resolution
an image prints at is its pixel count divided by the size it is drawn at,
and print wants 300 pixels per inch: a photo 60 mm wide needs about 709
pixels across. SVG images are drawn as vectors.

A document with bleed or marks, or made PDF/X, logs each image drawn under
300 ppi, with the pixel size it would need.

Fonts
-----

A print file must embed its fonts. The built-in Helvetica, Times and
Courier, and every family name that falls back to them, are **never
embedded**: give the text a face of its own with ``@font-face`` and a
TrueType, OpenType or WOFF file. See :doc:`fonts`. A document with bleed or marks logs text set
in a font that is not embedded; in PDF/X mode it is an error.

PDF/X-4
-------

PDF/X is the standard a print shop asks for. PDF/X-4 keeps transparency,
which xhtml2pdf draws for ``rgba()`` colours and images with an alpha
channel, so it is the level xhtml2pdf writes.

.. code:: python

   from xhtml2pdf import pisa

   pisa.CreatePDF(
       html,
       dest=output,
       pdfx={
           "profile": "ISOcoated_v2_eci.icc",  # path or bytes
           "condition": "FOGRA39",
           "info": "Offset, coated paper (ISO 12647-2:2004)",
       },
   )

.. code:: shell

   xhtml2pdf --pdfx-profile ISOcoated_v2_eci.icc --pdfx-condition FOGRA39 \
       brochure.html brochure.pdf

``profile`` is the CMYK output profile of the printing condition, from the
print shop or the ECI (FOGRA39 for coated paper in Europe, GRACoL or SWOP in
America). It has to be a CMYK printer profile. ``condition`` is the
identifier of the printing condition, as registered at the ICC; it defaults
to the profile's description. ``info`` describes it for a person.

The document is then:

- given an output intent with the profile embedded, XMP metadata and the
  ``GTS_PDFXVersion`` entries, and written as PDF 1.6;
- given a ``TrimBox`` on every page, the page itself when it has no bleed;
- colour-managed: RGB colours and images are tagged as sRGB, and neutral
  RGB colours -- black, greys -- are drawn as gray, which prints on the
  black plate alone instead of as a four-ink mix;
- stripped of links and form fields, which a print file has no use for.

It cannot be combined with ``encrypt``, as PDF/X forbids encryption, nor
with ``signature``, which adds the form field and annotation a PDF/X file
leaves out. Give the document a ``<title>``: a preflight reports a PDF/X
file without one, and xhtml2pdf logs a warning.

The file is built to the standard, not validated against it. Check it with
a preflight (Acrobat Pro, callas pdfToolbox) or ask the print shop to.

What is not covered
-------------------

- Converting RGB colours and images to CMYK. In PDF/X mode the press's
  profile does that at output; without it, the printer does.
- Spot colours (Pantone and other named inks), overprint and trapping.
- PDF/X-1a and PDF/X-3, which forbid transparency: transparency is kept
  as it is drawn.
