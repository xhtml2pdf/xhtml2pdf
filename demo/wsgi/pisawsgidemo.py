#!/bin/python
# -*- coding: utf-8 -*-

# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


__version__ = "$Revision: 103 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2007-10-31 17:08:54 +0100 (Mi, 31 Okt 2007) $"
__svnid__   = "$Id: pisa.py 103 2007-10-31 16:08:54Z holtwick $"

from wsgiref.simple_server import make_server
import logging

from xhtml2pdf import wsgi

def SimpleApp(environ, start_response):

    # That's the magic!
    #
    # Set the environment variable "pisa.topdf" to the filename
    # you would like to have for the resulting PDF
    environ["pisa.topdf"] = "index.pdf"

    # Simple Hello World example
    start_response(
        '200 OK', [
        ('content-type', "text/html"),
        ])
    return ["Hello <strong>World</strong>"]

if __name__ == '__main__':

    HOST = ''
    PORT = 8080
    logging.basicConfig(level=logging.DEBUG)

    app = SimpleApp

    # Add PISA WSGI Middleware
    app = wsgi.PisaMiddleware(app)

    httpd = make_server(HOST, PORT, app)
    print "Serving HTTP on port %d..." % PORT
    httpd.serve_forever()
