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

__reversion__ = "$Revision: 247 $"
__author__ = "$Author: holtwick $"
__date__ = "$Date: 2008-08-15 13:37:57 +0200 (Fr, 15 Aug 2008) $"
__version__ = VERSION = "VERSION{3.0.33}VERSION"[8:-8]
__build__ = BUILD = "BUILD{2010-06-16}BUILD"[6:-6]

VERSION_STR = """XHTML2PDF/pisa %s (Build %s)
http://www.xhtml2pdf.com

Copyright 2010 Dirk Holtwick, holtwick.it

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.""" % (
    VERSION,
    BUILD,
)
