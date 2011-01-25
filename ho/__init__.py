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

__version__ = "$Revision: 128 $"
__author__  = "$Author: holtwick $"
__date__    = "$Date: 2008-01-10 21:26:42 +0100 (Do, 10 Jan 2008) $"
__svnid__   = "$Id: __init__.py 128 2008-01-10 20:26:42Z holtwick $"

# Also look in other packages with the same name

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
