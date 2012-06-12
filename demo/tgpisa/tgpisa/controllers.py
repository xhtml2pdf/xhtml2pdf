from turbogears import controllers, expose, flash
# from tgpisa import model
import pkg_resources
try:
    pkg_resources.require("SQLObject>=0.8,<=0.10.0")
except pkg_resources.DistributionNotFound:
    import sys
    print >> sys.stderr, """You are required to install SQLObject but appear not to have done so.
Please run your projects setup.py or run `easy_install SQLObject`.

"""
    sys.exit(1)
# import logging
# log = logging.getLogger("tgpisa.controllers")

from turbogears.decorator import weak_signature_decorator
import sx.pisa3 as pisa
import cStringIO as StringIO
import cherrypy

def pdf(filename=None, content_type="application/pdf"):
    def entangle(func):
        def decorated(func, *args, **kw):
            def kwpop(default, *names):
                for name in names:
                    if name in kw:
                        return kw.pop(name)
                return default

            # get the output from the decorated function
            output = func(*args, **kw)

            dst = StringIO.StringIO()
            result = pisa.CreatePDF(
                StringIO.StringIO(output),
                dst
                )

            # print cherrypy.url("index.html")
            if not result.err:
                cherrypy.response.headers["Content-Type"] = content_type
                if filename:
                    cherrypy.response.headers["Content-Disposition"] = "attachment; filename=" + filename
                output = dst.getvalue()

            return output
        return decorated
    return weak_signature_decorator(entangle)

class Root(controllers.RootController):

    @expose()
    def index(self):
        import time
        return """<a href="pdf">Open PDF...</a>"""

    @pdf(filename="test.pdf")
    @expose(template="tgpisa.templates.welcome")
    def pdf(self):
        import time
        # log.debug("Happy TurboGears Controller Responding For Duty")
        flash("Your application is now running")
        return dict(now=time.ctime())
