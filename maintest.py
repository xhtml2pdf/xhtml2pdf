from pathlib import Path

from xhtml2pdf.h2pparser.parser import Xhtml2pdfParser

if __name__ == '__main__':
    #with open(Path('manual_test/test_style.html')) as arch:
    with open(Path('manual_test/test-all.html')) as arch:
        parser = Xhtml2pdfParser(arch)
        with open('result.xml', 'w') as r:
            parser.parse(show_xml=r)