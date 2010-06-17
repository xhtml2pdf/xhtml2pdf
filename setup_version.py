# -*- coding: ISO-8859-1 -*-

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

"""
Updates the version infos
"""

import time
import re
import cgi

VERSION = open("VERSION.txt", "r").read().strip()
BUILD = time.strftime("%Y-%m-%d")
FILES = [
    "setup.py",
    "setup_exe.py",
    # "setup_egg.py",
    "sx/pisa3/pisa_version.py",
    "doc/pisa-en.html",
    ]
try:
    HELP = cgi.escape(open("HELP.txt", "r").read(), 1)
except:
    HELP = ""
HELP = "<!--HELP--><pre>" + HELP + "</pre><!--HELP-->"

rxversion = re.compile("VERSION{.*?}VERSION", re.MULTILINE|re.IGNORECASE|re.DOTALL)
rxbuild = re.compile("BUILD{.*?}BUILD", re.MULTILINE|re.IGNORECASE|re.DOTALL)
rxversionhtml = re.compile("\<\!--VERSION--\>.*?\<\!--VERSION--\>", re.MULTILINE|re.IGNORECASE|re.DOTALL)
rxhelphtml = re.compile("\<\!--HELP--\>.*?\<\!--HELP--\>", re.MULTILINE|re.IGNORECASE|re.DOTALL)

for fname in FILES:
    print "Update", fname, "..."
    data = open(fname, "rb").read()
    data = rxversion.sub("VERSION{" + VERSION + "}VERSION", data)
    data = rxversionhtml.sub("<!--VERSION-->" + VERSION + "<!--VERSION-->", data)
    data = rxbuild.sub("BUILD{" + BUILD + "}BUILD", data)
    data = rxhelphtml.sub(HELP, data)
    open(fname, "wb").write(data)

