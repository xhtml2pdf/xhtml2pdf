import os
import sys
from xhtml2pdf import pisa

filename = ('../tests/samples/ttf_file_metadata_same_name.html')
output_dir = ('../tests/samples')

def render_pdf(filename, output_dir):
    basename = os.path.basename(filename)
    outname = '%s.pdf' % os.path.splitext(basename)[0]
    outfile = os.path.join(output_dir, outname)
    input = open(filename, 'rb')
    output = open(outfile, 'wb')

    result = pisa.pisaDocument(input, output, path=filename)

    input.close()
    output.close()

    if result.err:
        print('Error rendering %s: %s' % (filename, result.err))
        sys.exit(1)
    return outfile

render_pdf(filename,output_dir)