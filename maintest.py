from pathlib import Path

from xhtml2pdf.h2pparser.parser import Xhtml2pdfParser

if __name__ == '__main__':
    with open(Path('manual_test/test_form_input.html')) as arch:
        parser = Xhtml2pdfParser(arch)
        parser.parse()