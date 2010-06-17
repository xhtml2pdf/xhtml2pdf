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

__version__ = "$Revision: 194 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-04-18 18:59:53 +0200 (Fr, 18 Apr 2008) $"

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
from reportlab.platypus import Frame

import ho.pisa as pisa

def test(filename):

    # Convert HTML to "Reportlab Story" structure
    story = pisa.pisaStory("""
    <h1>Sample</h1>
    <p>Hello <b>World</b>!</p>
    """ * 20).story

    # Draw to Canvas
    c = Canvas(filename)
    f = Frame(inch, inch, 6*inch, 9*inch, showBoundary=1)
    f.addFromList(story,c)
    c.save()

    # Show PDF
    pisa.startViewer(filename)

if __name__=="__main__":
    test('story2canvas.pdf')
