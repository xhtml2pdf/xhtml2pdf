import PyPDF3
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf.files import pisaFileObject


class WaterMarks:

    @staticmethod
    def generate_pdf_background(pisafile, pagesize, is_portrait):
        """
        PyPDF3 requires pdf as background so convert image to pdf in temporary file with same page dimensions
        :param pisafile:  Image File
        :param pagesize:  Page size for the new pdf
        :return: pisaFileObject as tempfile
        """
        # don't move up, we are preventing circular import
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader
        output = pisaFileObject(None, "application/pdf") # build temporary file
        img = PmlImageReader(pisafile.getBytesIO())
        iw, ih = img.getSize()
        pw, ph = pagesize

        width = pw  # min(iw, pw) # max
        wfactor = float(width) / iw
        height = ph  # min(ih, ph) # max
        hfactor = float(height) / ih
        factor_min = min(wfactor, hfactor)
        factor_max = max(wfactor, hfactor)
        canvas = Canvas(output.getNamedFile(), pagesize=pagesize)
        if is_portrait:
            w = iw * factor_min
            h = ih * factor_min
            canvas.drawImage(img, 0, ph - h, w, h)
        else:
            h = ih * factor_max
            w = iw * factor_min
            canvas.drawImage(img, 0, 0, w, h)

        canvas.save()

        return output

    @staticmethod
    def get_watermark(context, max_numpage):
        if context.pisaBackgroundList:
            pages = list(map(lambda x: x[0], context.pisaBackgroundList))+[max_numpage+1]
            pages.pop(0)
            counter=0
            for page, bgfile in context.pisaBackgroundList:
                if not bgfile.notFound():
                    yield range(page, pages[counter]), bgfile
                counter+=1

    @staticmethod
    def process_doc(context, istream, output):
        pdfoutput = PyPDF3.PdfFileWriter()
        input1 = PyPDF3.PdfFileReader(istream)
        has_bg=False
        for pages, bgouter in WaterMarks.get_watermark(context, input1.numPages):
            bginput = PyPDF3.PdfFileReader(bgouter.getBytesIO())

            for ctr in pages:
                pagebg = bginput.getPage(0)
                page = input1.getPage(ctr-1)
                pagebg.mergePage(page)
                pdfoutput.addPage(pagebg)
                has_bg=True
        if has_bg:
            pdfoutput.write(output)

        return output, has_bg
