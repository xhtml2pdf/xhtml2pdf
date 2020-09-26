import os
import sys
from xhtml2pdf import pisa

filename = ('../tests/samples/adobe_asian_lenguage_pack.html')
output_dir = ('../tests/samples')


def render_pdf(filename, output_dir):
    basename = os.path.basename(filename)
    outname = '%s.pdf' % os.path.splitext(basename)[0]
    out_path = os.path.join(output_dir, outname)
    input_file = open(filename, 'rb')
    output_file = open(out_path, 'wb')

    result = pisa.pisaDocument(input_file, output_file, path=filename)

    input_file.close()
    output_file.close()

    if result.err:
        print('Error rendering %s: %s' % (filename, result.err))
        sys.exit(1)
    return out_path


render_pdf(filename, output_dir)
