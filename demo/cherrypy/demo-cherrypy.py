#!/usr/local/bin/python
# -*- coding: utf-8 -*-
#############################################
## (C)opyright by Dirk Holtwick, 2008      ##
## All rights reserved                     ##
#############################################

import cherrypy as cp
import sx.pisa3 as pisa
import cStringIO as StringIO

try:
    import kid
except:
    kid = None

class PDFDemo(object):

    """
    Simple demo showing a form where you can enter some HTML code.
    After sending PISA is used to convert HTML to PDF and publish
    it directly.
    """

    @cp.expose
    def index(self):
        if kid:
            return file("demo-cherrypy.html","r").read()

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

    @cp.expose
    def download(self, data):

        if kid:
            data = """<?xml version="1.0" encoding="utf-8"?>
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
                  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
                <html xmlns="http://www.w3.org/1999/xhtml"
                      xmlns:py="http://purl.org/kid/ns#">
                  <head>
                    <title>PDF Demo</title>
                  </head>
                  <body>%s</body>
                </html>""" % data
            test = kid.Template(source=data)
            data = test.serialize(output='xhtml')

        result = StringIO.StringIO()
        pdf = pisa.CreatePDF(
            StringIO.StringIO(data),
            result
            )
        if pdf.err:
            return "We had some errors in HTML"
        else:
            cp.response.headers["content-type"] = "application/pdf"
            return result.getvalue()

cp.tree.mount(PDFDemo())

if __name__ == '__main__':
    import os.path
    cp.config.update(os.path.join(__file__.replace(".py", ".conf")))
    cp.server.quickstart()
    cp.engine.start()
