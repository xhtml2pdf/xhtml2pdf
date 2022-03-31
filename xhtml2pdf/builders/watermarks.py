import PyPDF3
from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf.files import pisaFileObject, getFile


class WaterMarks:
    @staticmethod
    def get_size_location(img, context, pagesize, is_portrait):
        object_position = context.get('object_position', None)
        cssheight = context.get('height', None)
        csswidth = context.get('width', None)
        iw, ih = img.getSize()
        pw, ph = pagesize
        width = pw  # min(iw, pw) # max
        wfactor = float(width) / iw
        height = ph  # min(ih, ph) # max
        hfactor = float(height) / ih
        factor_min = min(wfactor, hfactor)
        factor_max = max(wfactor, hfactor)
        if is_portrait:
            height = ih * factor_min
            width = iw * factor_min
        else:
            height = ih * factor_max
            width = iw * factor_min

        if object_position:
            # x, y, width=None, height=None
            x, y = object_position
        else:
            if is_portrait:

                x, y = 0, ph-height
            else:
                x, y = 0, 0
        if csswidth:
            width=csswidth
        if cssheight:
            height=cssheight

        return x, y, width, height

    @staticmethod
    def get_img_with_opacity(pisafile, context):
        opacity = context.get('opacity', None)
        if opacity:
            name = pisafile.getNamedFile()
            img=Image.open(name)
            img = img.convert('RGBA')
            img.putalpha(int(255*opacity))
            img.save(name,"PNG")
            return getFile(name).getBytesIO()
        return pisafile.getBytesIO()

    @staticmethod
    def generate_pdf_background(pisafile, pagesize, is_portrait, context={}):
        """
        PyPDF3 requires pdf as background so convert image to pdf in temporary file with same page dimensions
        :param pisafile:  Image File
        :param pagesize:  Page size for the new pdf
        :return: pisaFileObject as tempfile
        """
        # don't move up, we are preventing circular import
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader
        output = pisaFileObject(None, "application/pdf") # build temporary file
        img = PmlImageReader(
            WaterMarks.get_img_with_opacity(pisafile, context)
        )
        x, y, width, height = WaterMarks.get_size_location(img, context, pagesize, is_portrait)

        canvas = Canvas(output.getNamedFile(), pagesize=pagesize)
        canvas.drawImage(img, x, y, width, height, mask='auto')

        """
        iw, ih = img.getSize()
        pw, ph = pagesize

        width = pw  # min(iw, pw) # max
        wfactor = float(width) / iw
        height = ph  # min(ih, ph) # max
        hfactor = float(height) / ih
        factor_min = min(wfactor, hfactor)
        factor_max = max(wfactor, hfactor)
        
        if is_portrait:
            w = iw * factor_min
            h = ih * factor_min
            canvas.drawImage(img, 0, ph - h, w, h)
        else:
            h = ih * factor_max
            w = iw * factor_min
            canvas.drawImage(img, 0, 0, w, h)
        """
        canvas.save()

        return output

    @staticmethod
    def get_watermark(context, max_numpage):
        if context.pisaBackgroundList:
            pages = list(map(lambda x: x[0], context.pisaBackgroundList))+[max_numpage+1]
            pages.pop(0)
            counter=0
            for page, bgfile, pgcontext in context.pisaBackgroundList:
                if not bgfile.notFound():
                    yield range(page, pages[counter]), bgfile, int(pgcontext['step'])
                counter+=1

    @staticmethod
    def process_doc(context, istream, output):
        pdfoutput = PyPDF3.PdfFileWriter()
        input1 = PyPDF3.PdfFileReader(istream)
        has_bg=False
        for pages, bgouter, step in WaterMarks.get_watermark(context, input1.numPages):
            bginput = PyPDF3.PdfFileReader(bgouter.getBytesIO())

            for index, ctr in enumerate(pages):
                pagebg = bginput.getPage(0)
                page = input1.getPage(ctr-1)
                if index%step == 0:
                    page.mergePage(pagebg)
                pdfoutput.addPage(page)
                has_bg=True
        if has_bg:
            pdfoutput.write(output)

        return output, has_bg
