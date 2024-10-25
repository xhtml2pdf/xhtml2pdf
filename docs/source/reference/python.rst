==========
Python API
==========

.. py:module:: xhtml2pdf.pisa

The main function of xhtml2pdf is :py:func:`CreatePDF`.

.. py:function:: CreatePDF(src, dest=None, dest_bytes=False, path="", link_callback=None, debug=0, default_css=None, xhtml=False, encoding=None, xml_output=None, raise_exception=True, capacity=100 * 1024, context_meta=None, encrypt=None, signature=None, **_kwargs)

   Create PDF.

   :param str|io.BufferedIOBase src:
      The source to be parsed.

   :param io.BufferedIOBase dest:
      The destination for the resulting PDF. This has to be a file object which
      **will not be closed** afterwards.

   :param bool dest_bytes:
      If true, will return the data written to the file.

   :param str path:
      The original file path or URL. This is needed to calculate the relative
      paths of images and stylesheets.

   :param typing.Callable[str|pathlib.Path|None, str|None] link_callback:
      Handler for special file paths (see below).

   :param int debug:
      :deprecated: this parameter is unused

   :param str default_css:
      The default CSS definition. If ``None``, the predefined CSS of xhtml2pdf
      is used.

   :param bool xhtml:
      Force parsing the source as HTML. If omitted, the parser will try to guess
      this.

      :deprecated: XHTML parsing will be removed in v0.2.8

   :param str encoding:
      The source encoding. If omitted, this will be guessed by the HTML5 parser.
      This is helpful if the HTML file does not have ``<meta charset>``.

   :param io.BufferedIOBase xml_output:
      If given, the XML output of the document tree (not the document itself!)
      will be written to this file/buffer.

   :param bool raise_exception:
      :deprecated: this parameter is unused

   :param int capacity:
      The capacity of the internal buffer, in bytes. If the document is bigger
      than the buffer, it will be managed in a temporary file rather than
      in-memory

   :param dict[str, str | tuple[float, float]] context_meta:
      Metadata for the PDF document. May include fields: ``author``, ``title``,
      ``subject``, ``keywords``, and ``pagesize``.

   :param str|reportlab.lib.pdfencrypt.StandardEncryption encrypt:
       Either a password to protect the PDF with or a pre-built instance of
       encryption parameters.

   :param dict[str, typing.Any] signature:
       Signature parameters. Should contain at least ``engine`` with the values
       of ``"pkcs12"``, ``"pkcs11"``, or ``"simple"``.

   :return:
   :rtype: xhtml2pdf.document.pisaStory|bytes

Link callback
^^^^^^^^^^^^^

Images, backgrounds, and stylesheets are loaded from the HTML document. Normally,
``xhtml2pdf`` expects these files to be found on the local drive. They may also
be referenced relative to the original document. You might, however, want to
reference these objects from somewhere else, like a Web page or a database.
Therefore, you may define a ``link_callback`` that handles these requests.

The link callback accepts two parameters:

1. ``uri`` --- the URI that needs to be transformed
2. (optionally) ``basepath`` --- the path of the resource where the URI
   originates from (useful for relative path calculations)
