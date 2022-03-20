import PyPDF3

from xhtml2pdf.files import pisaTempFile


class WaterMarks:
    @staticmethod
    def get_watermark( context):
        for bgouter in context.pisaBackgroundList:
            if bgouter and not bgouter.notFound():
                if bgouter.getMimeType() == "application/pdf":
                    yield bgouter

    @staticmethod
    def process_doc(context, istream, output):
        pdfoutput = PyPDF3.PdfFileWriter()
        input1 = PyPDF3.PdfFileReader(istream)
        has_bg=False
        for bgouter in WaterMarks.get_watermark(context):
            bginput = PyPDF3.PdfFileReader(bgouter.getBytesIO())
            pagebg = bginput.getPage(0)
            for ctr in range(input1.numPages):
                page = input1.getPage(ctr)
                page.mergePage(pagebg)
                pdfoutput.addPage(page)
                has_bg=True
        if has_bg:
            pdfoutput.write(output)

        return output, has_bg
