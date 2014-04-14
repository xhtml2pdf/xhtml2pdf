# -*- coding: utf-8 -*-
import logging

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

__reversion__ = "$Revision: 238 $"
__author__ = "$Author: holtwick $"
__date__ = "$Date: 2008-06-26 20:06:02 +0200 (Do, 26 Jun 2008) $"

REQUIRED_INFO = """
****************************************************
IMPORT ERROR!
%s
****************************************************

The following Python packages are required for PISA:
- Reportlab Toolkit >= 2.2 <http://www.reportlab.org/>
- HTML5lib >= 0.11.1 <http://code.google.com/p/html5lib/>

Optional packages:
- PyPDF2 <https://pypi.python.org/pypi/PyPDF2>
- PIL <http://www.pythonware.com/products/pil/>

""".lstrip()

log = logging.getLogger(__name__)

try:
    from xhtml2pdf.util import REPORTLAB22

    if not REPORTLAB22:
        raise ImportError("Reportlab Toolkit Version 2.2 or higher needed")
except ImportError as e:
    import sys

    sys.stderr.write(REQUIRED_INFO % e)
    log.error(REQUIRED_INFO % e)
    raise

from xhtml2pdf.version import VERSION


__version__ = VERSION
