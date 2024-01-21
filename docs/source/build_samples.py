import os
from pathlib import Path

from xhtml2pdf import pisa

dir_temp = "/"


def convert_to_pdf_file(
    inputfile, outputfile, link_callback=None, encrypt=None, signature=None
):
    with open(outputfile, "wb") as arch, open(
        inputfile, encoding="utf-8", errors="ignore"
    ) as source:
        return pisa.CreatePDF(
            source,
            arch,
            encrypt=encrypt,
            link_callback=link_callback,
            signature=signature,
            show_error_as_pdf=True,
        )


def link_callback(uri, _rel):
    link = Path("./_static/html_samples") / uri
    return str(link.absolute().resolve())


def build_resources() -> None:
    rst_path = Path("./").absolute().resolve()
    source_path = Path("./_static/html_samples").absolute().resolve()
    pdf_path = Path("./_static/pdf_samples").absolute().resolve()
    text = """
Examples
################

    """
    for _path, _dirc, files in os.walk(source_path):
        for name in files:
            if name.endswith(".html"):
                filename = name.replace(".html", ".pdf")
                pdfcontext = convert_to_pdf_file(
                    source_path / name, pdf_path / filename, link_callback=link_callback
                )
                text += """
{}
{}

.. literalinclude:: _static/html_samples/{}
   :language: html

:pdfembed:`src:_static/pdf_samples/{}, height:600, width:600, align:middle`
                    """.format(
                    pdfcontext.meta["title"],
                    "-" * (len(pdfcontext.meta["title"]) + 2),
                    name,
                    filename,
                )
    with open(rst_path / "examples.rst", "w", encoding="utf-8") as arch:
        arch.write(text)


if __name__ == "__main__":
    build_resources()
