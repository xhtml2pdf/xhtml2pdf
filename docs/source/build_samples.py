from xhtml2pdf import pisa
from pathlib import Path
import os
import sys

dir_temp = "/"


def convert_to_pdf_file(
    inputfile, outputfile, link_callback=None, encrypt=None, signature=None
):
    with open(outputfile, "wb") as arch:
        with open(inputfile, "r", encoding="utf-8", errors="ignore") as source:
            pdfcontext = pisa.CreatePDF(
                source,
                arch,
                encrypt=encrypt,
                link_callback=link_callback,
                signature=signature,
                show_error_as_pdf=True,
            )
            return pdfcontext


def link_callback(uri, rel):
    link = Path("./_static/html_samples") / uri
    return str(link.absolute().resolve())


def build_resources():
    rst_path = Path("./").absolute().resolve()
    source_path = Path("./_static/html_samples").absolute().resolve()
    pdf_path = Path("./_static/pdf_samples").absolute().resolve()
    text = """
Examples
################

    """
    for path, dirc, files in os.walk(source_path):
        for name in files:
            if name.endswith(".html"):
                filename = name.replace(".html", ".pdf")
                pdfcontext = convert_to_pdf_file(
                    source_path / name, pdf_path / filename, link_callback=link_callback
                )
                text += """
%s
%s

.. literalinclude:: _static/html_samples/%s
   :language: html

:pdfembed:`src:_static/pdf_samples/%s, height:600, width:600, align:middle`
                    """ % (
                    pdfcontext.meta["title"],
                    "-" * (len(pdfcontext.meta["title"]) + 2),
                    name,
                    filename,
                )
    with open(rst_path / "examples.rst", "w") as arch:
        arch.write(text)


if __name__ == "__main__":
    build_resources()
