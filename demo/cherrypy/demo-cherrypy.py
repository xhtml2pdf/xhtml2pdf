#!/usr/bin/env python3
"""
#############################################
## (C)opyright by Dirk Holtwick, 2008      ##
## All rights reserved                     ##
#############################################
"""

import cherrypy
import cStringIO as StringIO
import sx.pisa3 as pisa

try:
    import kid
except ImportError:
    kid = None


class PDFDemo:
    """
    Simple demo showing a form where you can enter some HTML code.
    After sending PISA is used to convert HTML to PDF and publish
    it directly.
    """

    @cherrypy.expose  # type: ignore[attr-defined]
    @staticmethod
    def index():
        if kid:
            with open("demo-cherrypy.html", encoding="utf-8") as file:
                return file.read()

        return """
        <html><body>
            Please enter some HTML code:
            <form action="download" method="post" enctype="multipart/form-data">
            <textarea name="data">Hello <strong>World</strong></textarea>
            <br />
            <input type="submit" value="Convert HTML to PDF" />
            </form>
        </body></html>
        """

    @cherrypy.expose  # type: ignore[attr-defined]
    @staticmethod
    def download(data):
        if kid:
            data = (
                """<?xml version="1.0" encoding="utf-8"?>
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
                  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
                <html xmlns="http://www.w3.org/1999/xhtml"
                      xmlns:py="http://purl.org/kid/ns#">
                  <head>
                    <title>PDF Demo</title>
                  </head>
                  <body>%s</body>
                </html>"""
                % data
            )
            test = kid.Template(source=data)
            data = test.serialize(output="xhtml")

        result = StringIO.StringIO()
        pdf = pisa.CreatePDF(StringIO.StringIO(data), result)
        if pdf.err:
            return "We had some errors in HTML"
        cherrypy.response.headers["content-type"] = "application/pdf"
        return result.getvalue()


cherrypy.tree.mount(PDFDemo())  # type: ignore[attr-defined]

if __name__ == "__main__":
    import os.path

    cherrypy.config.update(os.path.join(__file__.replace(".py", ".conf")))  # type: ignore[attr-defined]
    cherrypy.server.quickstart()  # type: ignore[attr-defined]
    cherrypy.engine.start()  # type: ignore[attr-defined]
