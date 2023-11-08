#############
Release Notes
#############

***************
Versions >= 0.2
***************


..
    This is a template: Please copy it and then remove indentation!

    X.X.X
    ====================

    Released: YYYY-MM-DD

    **🎉 New**

    * Note: for new, great features
    *

    **💪🏼 Improvements**

    * Note: for smaller improvements
    *

    **🐛 Bug-Fixes**

    * Note: Please reference GitHub issues with :issue:`999` and pull requests with :pr:`999`
    *

    **⚠️ Deprecation**

    * Note: For any dropped Python versions, ReportLab versions, xhtml2pdf arguments etc.
    *

    **📘 Documentation**

    *
    *

    **🧹 Cleanup**

    *
    *

    | Thanks to the following people on GitHub for contributing to this release:
    | *GitHub-Name-1*, *GitHub-Name-2* and *GitHub-Name-3* (Note: mention all the merged pull requests since last release here!)

    --------------------------------------------

0.2.12
======

Released: 2023-11-08

**🐛 Bug-Fixes**

* Fix page number & page count (:issue:`106`) (:pr:`695`)
* Fix ``ZeroDivisionError`` on broken image files (:pr:`723`)

**📘 Documentation**

* Update README (:pr:`707`)
* Modernize Sphinx configuration (:pr:`711`)

**🧹 Cleanup**

* Change print statement to log.exception (:pr:`700`)
* Remove Python2 compatibility (:pr:`706`)
* Depend on ``html5lib >= 1.1`` (:issue:`705`) (:pr:`709`)
* Depend on ``reportlab >= 4.0.4`` (:issue:`699`) (:pr:`708`)
* Use black code style (:pr:`714`)
* Enforce consistent file formatting (:pr:`715`)
* Add ruff code linter (:pr:`716`)
* Start using type hints & validate them via mypy (:pr:`717`)
* Drop support for Python 3.7 (reached end of life on 2023-06-27) (:pr:`718`)
* Add support for Python 3.12 (released on 2023-10-02) (:pr:`719`)

| Thanks to the following people on GitHub for contributing to this release:
| *JanEgner*, *lucasgadams*, *a-detiste*, *holtwick*, *stefan6419846*, *timobrembeck*

--------------------------------------------


0.2.11
=======

Released: 2023-06-07

This release only aims to fix issues with pycairo and xhtml2pdf dependencies with reportlab.

**🐛 Bug-Fixes**

* Fix setup.py and requirements dependency to set reportlab>=3.5.53,<4 :issue:`688` in :pr:`690`

| Thanks to the following people on GitHub for contributing to this release:
| *gaurab-10*, *jorenham*

--------------------------------------------

0.2.10
======

Released: 2023-04-20

**🐛 Bug-Fixes**

* Fix canvas graph issue :issue:`614` in :pr:`619`

**🧹 Cleanup**

* Remove duplicate pypdf entry from `setup.py` in :pr:`619`

| Thanks to the following people on GitHub for contributing to this release:
| *brandonlake-semaphore*, *sunpoet*

--------------------------------------------


0.2.9
=====

Released: 2023-01-30

**Important notes**

* Text RTL has new implementation but I am not sure if works as required, more works need so use it, for text and let me know if it's works.

**🎉 New**

* OL tag allow start counter
* Div, P, And Body allows dir attribute (rtl and ltr) to provide text direction

**💪🏼 Improvements**

* Page counter and Page number are now available as simple text inside paragraphs
* New regex for strip up to curly bracket
* Change pyPDF3 to pypdf.

| Thanks to the following people on GitHub for contributing to this release:
| *BergLucas*, *matllubos*, *timobrembeck*, *MartinThoma*, *charludo*, *jorenham*

--------------------------------------------


0.2.8
=====

Released: 2022-06-16


**🐛 Bug-Fixes**

* Fix background-image issues with :issue:`614` and pull requests with :pr:`619`
* Fix CSSParseError for minified @font-face definitions  :pr:`609`
* Fixed a few typos and grammar mistakes in usage.rst documentation. :pr:`610`


| Thanks to the following people on GitHub for contributing to this release:
| *MuhammedNihad*, *timobrembeck*, *flash716*

--------------------------------------------

0.2.7
=====

Released: 2022-03-31

**🎉 New**

* Add encryption and password protection
* New WaterMark management system with new options
* Add Graphic builder
* Add signing pdfs (simple and pades)


**🐛 Bug-Fixes**

* Remove import cycle between utils and default
* Fixed link_callback construction of path
* Fixed path when is relative to current path

**⚠️ Deprecation**

*  `xhtml` in pisa.CreatePDF support will removed on next release
*  `XML2PDF` and `XHTML2PDF` will be removed on next release use `HTML2PDF` instead

**📘 Documentation**

* Add render pdf on documentation and add some html example.
* Include graphics examples


| Thanks to the following people on GitHub for contributing to this release:
| *marcelagz* for graphics support :)

--------------------------------------------


0.2.6
=====

Released: 2022-03-11

**🎉 New**

* Set timeout in https options
* Add new file manager approach using factory method, now new classes deal with different types of data B64InlineURI, LocalProtocolURI, NetworkFileUri, LocalFileURI, BytesFileUri
* rtl languages reversed lines added as a ParaFrag (note: not fully supported yet)
* Check if Paragraph has 'rtl' attribute (note: not fully supported yet)
* Add SVG support

**💪🏼 Improvements**

* Update packages dependencies
* Now getColor return None when None is passed ignoring default value, but return default if bool(data) == false
* Change test for github workflow using only Linux
* Add Python 3.9, 3.10
* Switch from PyPDF2 to PyPDF3
* Allow call tests using make.

**🐛 Bug-Fixes**

* Fix UnboundLocalError in reportlab_paragraph (:issue:`585`) (:pr:`586`)

**📘 Documentation**

* Created this release notes section.
* Updated the Sphinx version and the sphinx-rtd-theme version
* Update package information.

**🧹 Cleanup**

* Drop python 2 support.
* Remove most of python 2 code and cleanup
* Remove six dependency and update Readme
* Remove usage of getStringIO (#590) removed form reportlab

| Thanks to the following people on GitHub for contributing to this release:
| *Roman914*, *LeonardoBein*, *myu20*, *myu20*, *captn3m0*, *audoh-tickitto*, *Momoumar*,
| *timobrembeck*, *fbernhart*,*mgodkowicz*, *anze3db * and *luisza*

--------------------------------------------


0.2.5
=====

Released: 2020-10-08

**🎉 New**

* Added Asian fonts support (Simplified Chinese, Traditional Chinese, Japanese & Korean) :issue:`353`
* Added support for right-to-left writings like Arabic, Hebrew, Persian, Pashto, Urdu and Sindhi. Simply include for example ``<pdf:language name="arabic"/>`` :issue:`494`

**💪🏼 Improvements**

* CSS property ``letter-spacing`` now supports float values and relative & absolute units like ``cm``, ``in``, ``em``, ``%`` etc. :issue:`490`
* Added unit tests for Asian and right-to-left fonts. :pr:`520`

**🐛 Bug-Fixes**

* ``@frame`` properties like ``width``, ``right``, ``bottom`` etc. are now correctly calculated depending on the page orientation and size :issue:`499`
* Fixed support for multiple fonts and unicode :issue:`492`
* Fixed an encoding issue with html5lib :issue:`468`
* Fixed a problem with the ``border`` property in ``h1`` to ``h6`` heading tags :issue:`466` :issue:`495`
* Fixed compability with ReportLab 3.5.X :issue:`404` :issue:`463`
* Removed default background-image when no background-image is defined :issue:`484`
* Fixed an issue with different font type that have the same name :issue:`381`
* Fixed a bug that prevented support for Python 3.X :issue:`513`
* testrender test: fixed transparences and included new reference files, (now all tests pass in Travis CI without --failed parameter)  :pr:`502`
* ``0.0`` as value for a CSS property now acts the same way as ``0`` and ``None`` :pr:`516`

**⚠️ Deprecation**

* Removed ``i`` and ``inch`` as unofficial synonyms for the ``in`` unit  :pr:`516`

**📘 Documentation**

* Added new section about Asian font support :pr:`505` :pr:`520`
* Added new section about support for right-to-left writings :pr:`520`
* Readme.rst file was updated  :pr:`507` :pr:`512`
* Added missing changelog entries for earlier releases :issue:`478`

**🧹 Cleanup**

* Replaced deprecated ``base64.encodestring`` with ``base64.encodebytes`` :issue:`472`
* Replaced deprecated ``log.warn()`` with ``log.warning()`` :pr:`509`
* Dropped dependency of nose (outdated & unmaintained) in favor of unittest, which is included in the Python standard library :pr:`520`
* Removed the old nose tests and replaced them with unittest :pr:`520`
* Removed unlicensed .tff font files in our tests folder and replaced them with open source fonts :pr:`520`
* Travis CI and AppVeyor are now testing both against the same ReportLab versions (3.3 to 3.5.X) :pr:`520`

| Thanks to the following people on GitHub for contributing to this release:
| *ezawadzki*, *fbernhart*, *KirilNN*, *luisza*, *Mark-Hetherington*, *parthjoshi2007*, *pedroszg*, *silvio-dp*, *sj175*, *tirkarthi* and *z4c*

--------------------------------------------

0.2.4
=====

Released: 2020-01-18

**🎉 New**

* Add ``em`` unit support

**💪🏼 Improvements**

* Added testing for Python 3.7 and 3.8
* Added support for urllib in Python 2 and Python 3

**🐛 Bug-Fixes**

* Fixed cgi escape util on setup version
* Fixed width assignation on fragments
* Repaired base64 unscaped string
* Fixed urlparse when urls has parameters
* Fixed i_rgbcolor support

**📘 Documentation**

* Updated ``link_callback`` documentation
* Stylized code lines in documentation

--------------------------------------------

0.2.3
=====

Released: 2018-09-14

Changes were not documented

--------------------------------------------

0.2.2
=====

Released: 2018-04-16

Changes were not documented

--------------------------------------------

0.2.1
=====

Released: 2018-02-16

**🎉 New**

* Added support for Python 3.8

**💪🏼 Improvements**

* Improved table tests

**🐛 Bug-Fixes**

* Forced html5lib to 1.0.1 (old versions of html5lib are not in pip)
* Allow for URI-escaped strings in base64 data

**🧹 Cleanup**

* Removed the dependency on httplib2

--------------------------------------------

0.2
===

Released: 2018-02-15

**🎉 New**

* Support for a new ``@page`` property: ``background-image``

**💪🏼 Improvements**

* Improved Python 3 support
* Included new ``httplib`` options

**🐛 Bug-Fixes**

* Fix for transparent images in Python 3

**⚠️ Deprecation**

* Removed support for Python 2.3

**📘 Documentation**

* Readthedocs integration
* Updated Django demo site

**🧹 Cleanup**

* PEP8 improvements and code cleanups
* Dropped the ``turbogears`` module

| Thanks to the following people on GitHub for contributing to this release:
| *andreyfedoseev*, *browniebroke*, *flupzor* and *luisza*

--------------------------------------------

0.2beta1
========

Released: 2016-11-30

Changes were not documented

--------------------------------------------


**********************
Versions >= 0.1, < 0.2
**********************

0.1beta3
========

Released: 2016-08-16

Changes were not documented

--------------------------------------------

0.1beta2
========

Released: 2016-08-01

Changes were not documented

--------------------------------------------

0.1beta1
====================

Released: 2016-06-05

Changes were not documented

--------------------------------------------

0.1alpha4
=========

Released: 2016-05-18

* Removed PyPy support
* Avoid exceptions likely to occur systematic to how narrow a text column is #309 - thanks *jkDesignDE*
* Improved tests for tables :pr:`305` - thanks *taddeimania*
* Fix broken empty PDFs in Python2 :pr:`301` - thanks *citizen-stig*
* Unknown page sizes now raise an exception :pr:`71` - thanks *benjaoming*
* Unorderable types caused by duplicate CSS selectors / rules :pr:`69` - thanks *benjaoming*
* Allow empty page definition with no space after @page - :pr:`88` - thanks *benjaoming*
* Error when in addFromFile using file-like object :pr:`245` - thanks *benjaoming*
* Python 3: Bad table formatting with empty columns :pr:`279` - thanks *citizen-stig and benjaoming*
* Removed paragraph2.py, unused ghost file since the beginning of the project :pr:`289` - thanks *citizen-stig*
* Catch-all exceptions removed in a lot of places, not quite done :pr:`290` - thanks *benjaoming*


--------------------------------------------

0.1alpha3
=========

Released: 2016-05-01

* Improved six usage, simplifies codebase :pr:`288` - thanks *citizen-stig*
* Removed mutable types as default args :pr:`287` - thanks *citizen-stig*
* Fix "hangs forever on simple input" :pr:`209`
* Base64 inline <img> works now :pr:`281`

--------------------------------------------

0.1alpha2
=========

Released: 2016-04-14

* Fixed: AttributeError: 'bytes' object has no attribute 'encode' :pr:`265`
* Improved tests, added code coverage

--------------------------------------------

0.1alpha1
=========

Released: 2016-01-20

This major version bump signals that we have added Python 3 support. Other than
that, the project remains largely unchanged.

* Python 3 support
* Cleaning up codebase
* Github and documentation modernizations

--------------------------------------------


**************
Versions < 0.1
**************

0.0.6
=====

Released: 2014-04-27

* get css backgrounds and fonts relative to the css file path
* fix CSS parser breaking on "@media screen and ..." (:issue:`132`)

--------------------------------------------

0.0.5
=====

Released: 2013-03-25

* Switched dependency to Pillow instead of PIL.
* Converted the docs to rst (thanks tomscytale!)
* Huge performance improvements (thanks Andrea Bravetti!)
* Bugfixes.

--------------------------------------------

0.0.4
=====

Released: 2012-05-23

* Added a <pdf:pagecount/> tag to write the total number of pages.
* The <pdf:barcode/> tag now accepts a fontsize argument for the human-readable font.
* Various bugfixes and enhancements

--------------------------------------------

0.0.3
=====

Released: 2011-06-19

Changes were not documented

--------------------------------------------


0.0.2
=====

Released: 2011-05-27

Changes were not documented

--------------------------------------------


0.0.1
=====

Released: 2011-05-20

Changes were not documented

--------------------------------------------


0.0.0
=====

Released: 2011-05-19

Changes were not documented

--------------------------------------------


***************
Legacy Versions
***************

The following changelog entries were relevant before the maintainer change.

"I would like to thank the people mentioned in brackets in this change log
very much for their help and support!" - Dirk


Version 3.0.33, 2010-06-16

- NEW: Changed license to Apache License 2.0, now completely Open Source without any charging. Feel free to continue or for this project.
- FIX: Empty cells now collapse

Version 3.0.32, 2009-05-08

- NEW: New command line option '--base' to specify base path if input comes via STDIN
- FIX: The 'keep in frame' feature for tables did not work inside of static frames (Arun Shanker Prasad)
- FIX: Small typos

Version 3.0.31, 2009-05-04

- NEW: Support for Style "list-style-image", also supports "zoom"
- NEW: Temporary files internally are written to disk if they exceed a certain size
- NEW: Font names can now also read from external URL
- UPD: Modified pdfjoiner.py demo
- FIX: Custom font image problem still appeared
- FIX: Single image in a block issue
- FIX: Randomly used wrong images is fixed using a workaround for the bug in Reportlab _digester routine
- FIX: Empty tables error (Davide Moro)
- FIX: Fallback to urllib2 if httpdlib fails

Version 3.0.30, 2009-03-27

- NEW: Default CSS now hides content of <noscript>
- UPD: Better whitespace handling in RL Paragraph
- FIX: Fixed RL Paragraph.split to work with autoleading and images
- FIX: Small bug fix for show_error_as_pdf
- FIX: Demos used os.startfile which is not supported on non Windows OSes
- FIX: Table available height threw exceptions
- FIX: Switched from urllib2 to httplib for loading external sources
- FIX: Correct homepage and download page in setup.py
- FIX: Paragraphs in lists repeated the bullet
- FIX: Tables now support -pdf-keep-with-next
- FIX: TOC bug fixed
- FIX: Add missing table columns to avoid error in Reportlab table
- FIX: Fix for background images sizing
- FIX: Empty documents now create one blank page
- FIX: Imported fonts caused an error if used together with images

Version 3.0.29, 2008-12-01

- NEW: Warning if Reportlab 2.2 is not installed
- UPD: Better support for named colors
- UPD: Modifed frame handling to better support relative values
- FIX: Splitting paragraph threw errors some times; also had problems with line breaks on the second page, fix for RL 2.2 paragraph was needed
- FIX: Added margins to <blockquote> default CSS
- FIX: Inline images in static frames did not work
- FIX: Link anchors and non internal fonts caused a strange error

Version 3.0.28, 2008-11-21

- NEW: Requires Reportlab 2.2 now!
- NEW: Background colors for inline elements like <span>
- NEW: Inline images and left and right aligned images implemented
- NEW: Possibility to handle table cells that are to large via CSS option -pdf-keep-in-frame-mode
- NEW: Option "--system" for command line tool to dump system version infos
- NEW: CSS attribute -pdf-line-spacing for fix space between lines
- NEW: Creation and handling of data URI with base64 encoding (others to come)
- NEW: New general file loader that is also able to load remote data and data URI
- NEW: PDF Joiner to concatenate many PDF and pisa documents
- NEW: Page backgrounds can now be images or PDF
- NEW: Visual Unittests based on ImageMagick and TortoiseIDiff (for Windows)
- NEW: Pisa raises execptions now if errors occure; with pisaDocument(..., raise_execeptions=False) you can turn them off
- UPD: Paragraphs now use the maximum leading to avoid overlapping text
- UPD: Removed "Keep with next" from H1 to H6
- FIX: Sizing of images is now handled better; should better work with PIL
- FIX: Border handling of paragraphs optimized and fixed
- FIX: Images that are higher than the page frame are scaled down to fit
- FIX: Paragraphs only containing &nbsp; are rendered
- FIX: Problem regarding the order of border style definitions
- FIX: Single <br> between two blocks now creates a new line
- FIX: Set table attribute "repeat" to "0"
- FIX: Some <font> attributes did not work as expected
- FIX: Font sizes reworked to behave like browser implmentations
- FIX: Like in most HTML browser table cells now have "valign=middle" and table headers have font weight bold
- FIX: Little fix in CSS parsing
- FIX: Default of <link media=""> was "screen", changed to "all"
- FIX: Command line tools did not install with "easy_install"

Version 3.0.27, 2008-10-04

- INF: License changed from Qt to GPLv2
- INF: Not yet completely combatible with Reportlab 2.2 (&nbsp; errors and borders)
- NEW: Command line tool called "xhtml" ("pisa" still available but will be deprecated with pisa 3.1)
- NEW: EGG for Python 2.6
- NEW: Basic support for Data URI
- NEW: New style -pdf-keep-with-next (does not work with pdf:toc for now)
- UPD: Setup now exclusively works with SetupTools

Version 3.0.26, 2008-08-28

- FIX: Python <2.5 didn't work because of a syntax error

Version 3.0.25, 2008-08-15

- UPD: Made imports more explicit to avoid import recursions
- FIX: <pdf:pagenumber/> didn't work in tables (Roman Lisagor)
- FIX: Images without suffixes have been ignored by pisa (Henning von Bargen)
- INF: Preparations for support of HTML FORM using INPUT, TEXTAREA, SELECT

Version 3.0.24, 2008-07-14

- NEW: Support for separate borders on each side of a paragraph has been added (Robin Dunn)
- NEW: Support for font tag (color, face, size)
- UPD: Handling of margin and padding in paragraphs is improved (Robin Dunn)
- UPD: Updated documentation (CreatePDF, Images)
- FIX: A typo in margin-left has been fixed (Robin Dunn)

Version 3.0.23, 2008-06-26

- UPD: getColor() now understands colors like rgb(255,0,0) (Darryl Dixon)
- FIX: c.warning threw errors if no arguments where passed (Searle)
- FIX: pisa now works with html5lib 0.11.1

Version 3.0.22, 2008-06-06

- UPD: Updated documentation
- UPD: Speed optimizations by removing copy.deepcopy (Darryl Dixon)
- FIX: Small fix in CSS parser

Version 3.0.21, 2008-06-05

- FIX: Used a parameter for html5lib that was not supported by html5lib 0.10
- FIX: Now tested against the latest third party packages: ReportLab 2.1, html5lib 0.10, pyPdf 1.11

Version 3.0.20, 2008-06-02

- NEW: New parameter "encoding" to explicitly set an encoding for the source data
- UPD: Added a programming example to documentation
- FIX: If a Unicode string is passed it will automatically be converted to UTF8
- FIX: Fixes for Google AppEngine support
- FIX: If possible cStringIO will be used instead of StringIO
- FIX: An exception in psaDocument was not handled the right way because a context object was expected

Version 3.0.19, 2008-05-31

- NEW: Support for Google AppEngine
- NEW: Support for page break before and after [not yet tested] (Luka Frelih)
- UPD: Reworked parts of the documentation but not yet completed
- UPD: Optimized the command line tool "pisa"
- FIX: TOC bugs regarding entities and additional tags inside the TOC entry definitions (Luka Frelih)
- FIX: Default logging didn't work with Python<2.5 (Anders J. Munch)
- FIX: StringIO is used instead of cStringIO to avoid encoding problems like the ones we had with GoogleAppEngine

Version 3.0.18, 2008-04-19

- WIN: Updated the windows command line version
- NEW: WSGI support and demo
- NEW: Added simple ASPN Cookbook example
- UPD: Unified setup.py and setup_egg.py (Andreas Gabriel)
- UPD: Better handling of XML and HTML parsing
- UPD: Cleanup of Django sample
- UPD: Cleanup of command line tool options
- UPD: Command line tool doesn't stop batch if error occurred any more
- FIX: 'style' attribute was not evaluated!
- FIX: If a string was passed to pisaDocument it had been converted to StringIO, which was not necessary
- FIX: c.addPara(force=True) works again e.g. for forcing empty pages
- FIX: Better handling of CDATA and Comments
- FIX: Better handling of &nbsp;
- FIX: Removed rsplit() for backward compatibility with Python 2.3
- FIX: Handling of inconsistent HTML anchors
- FIX: TurboGears Demo

Version 3.0.17, 2008-03-23

- NEW: Added CSS support for TOC and updated documentation (Jean Baltus)
- UPD: Added "render_to_pdf" to Django demo (Diego Firmenich)
- UPD: Did some refactoring to make CSS parsing more flexible
- UPD: Removed log.exception for warnings
- FIX: Empty entries in TOC (Jean Baltus)
- FIX: Use correct font for <li> now (reported by Gabor Farkas)

Version 3.0.16, 2008-03-16

- Did some researches about support for languages like Farsi, Arabic and Asian
  languages. The dir='rtl' feature seems to be quite time intensive to be
  implemented, maybe I will do it in a later version or on request
- Switched back to HTML parsing by default, but use of XHTML is recommended. Use
  the option "xhtml" in pisaDocument or "-x" in the command line tool
- Added a decorator for use in Turbogears and CherryPy
- Completely switched to Python logging system
- Created a separate download for the fonts in the "test" directory to
  reduce the size of the package
- Just use multiBuild if needed e.g. using pdf:toc
- Bugfix: @font-face threw always a warning about font-weight
- Bugfix: List points have to be always in "Helvetica" (Gabor Farkas)
- Bugfix: Obligatory attributes for tag had not been handle the right way
- Bugfix: Marked some old tag based functionalities like pdf:font, pdf:frame and pdf:template as deprecated

Version 3.0.15, 2008-03-13

- Added new package and namespace "ho". With pisa 3.1. we will move away form "sx"
- Added version testing (2.1) for Reportlab Toolkit (Diego Firmenich)
- Added new command <pdf:toc> for support of table of contents, stiling per CSS has not been implemented yet (Jean Baltus)
- Added simple barcode support via command <pdf:barcode> (Diego Firmenich)
- Added Python logging. Name of logger "ho.pisa" and "ho.css". Set debugging level in command line tool by using "-d" for debugging and "-w" for warnings
- Added complete support for CSS "font"
- Modified the version handling and setup system for pisa distributions (had to do with the import errors that where not thrown, reported by Schmitte)
- Updated documentation and added a CSS for HTML version
- Bugfix: CSS "background" URL handling was broken (Luis Bruno)
- Bugfix: CSS "border" now works more standard conform
- Bugfix for compatibility problems with Python 2.3 because of reversed() function
- Bugfix: No exception was thrown if a third party module was missing (Kai Schmitte)
- Bugfix: Changed HTML5 parser from HTMLParser to XHTMLParser so that the custom tags of the "pdf" namespace are handled like expected
- Bugfix: Switched from urllib to urllib2 because status errors (like 404) where not handled (Kees Hink)
- A lot of smaller bugfixes and testings

Version 3.0.14, 2008-02-13

- Added a sample for Unicode support in exotic languages like "farsi" using DejaSans font (Adam Hyde)
- Command line tool generation integrated into setup.py (Andreas Gabriel)
- Bugfix if no path had been set to pisaDocument()
- Bugfix for calculating @frame dimensions
- Bugfix: CSS comments like "//" where allowed (Andreas Gabriel)

Version 3.0.13, 2008-01-22

- Added a demo using cherrypy web server and kid
- Added a demo using django framework
- Modified test-background.html to work with CSS
- Added suport for bold and italic TTF fonts to the @font-face CSS section (Robert Klep)
- Added suport for bold and italic Postscript fonts to the @font-face CSS section
- The @-rules are not need a trailing space after ident any more (Robert Klep)
- Fixed the Windows standalone version to work
- Made the 'sx' folder more sharable by modifying __init__.py
- Changed font-weight so that only values starting with '400'are considered 'bold' (Robert Klep)
- Added "text-indent" style (Robert Klep)
- Added "-pdf-keep-with-next" style to avoid page break between certain elements (Robert Klep)
- Added "-pdf-outline", "-pdf-outline-level" and "-pdf-outline-open" styles to create PDF bookmarks. Per default this is defined for the tags H1 to H6 (Robert Klep)
- New option to overwrite the default CSS definitions of pisa
- New command line options --css
- New command line options --css-dump to get the default CSS definitions. A dump of the recent CSS default may also be found in test/default.css
- Fixed setup.py
- Added EGG installation file support

Version 3.0.12, 2008-01-09

- Moved SVN repository to Holtwick
- Modified copyright notes and links to ``http://www.htmltopdf.org``
- Added new table attributes "border", "bordercolor", "cellpadding"
- Added support for &nbsp;

Version 3.0.11, 2007-11-13

- New example for loading a page form the web via Python
- New example "test-invoice.html"
- Added support for "align" attribute to <td> and <th>
- Fixed that more than one static frame can use the same named element
- Added -pdf-next-page to specify next page template
- Added -pdf-frame-break: after, before
- Fixed bug for @page without declarations
- Added option for output of errors as PDF (e.g. useful in web applications)
- Set "producer" to "pisa"
- Set author, subject and keywords with <meta>

Version 3.0.10, 2007-11-02

- Fixed some problems with wrong @page and @frame definitions
- New property -pdf-frame-box
- Implemented a pre parser for CSS that cleans up the code with some regular expression, like stripping illegal url ``http://...``
- Improved online demo
- First release of binary Windows command line version or pisa
- Fixed some issues with named anchors
- Empty documents are now delivered correctly
- Fixed error on list types
- Fixed problem with debugging infos

Version 3.0.9, 2007-10-31

- Modified setup.py for Chesse Shop
- Added bdist_wininst to setup
- Moved w3c into sx package and added license text
- Modified simple.py demo script
- Clean up for first public release

Version 3.0.8, 2007-10-31

- Added <a name> and a bugfix for ReportLab anchors
- Added <a href>
- More documentation about fonts and new font aliases
- Fixed some bugs in tables
- <hr> now uses ReportLabs implementation
- Margin collapse by using spaceBefore and spaceAfter
- Renamed -pdf-page-size to size (CSS3)

Version 3.0.7, 2007-10-30

- Static frames in @frame
- Wrote layout section in documentation
- Updated the documentation CSS
- Renamed @box to @frame
- Added -pdf-page-size and -pdf-page-orientation
- Added @page and @box
- Fixed some problems with font definitions and Unicode
- Font "Times" does not exist, changed default to "Times-Roman"
- Margins, paddings and borders are only applied in display:block elements

Version 3.0.6, 2007-10-29

- Implemented @font-face
- "font-family" can now handle comma separated font names
- Implemented <pdf:font> for embedding TTF and PS fonts
- <link> looks for rel="stylesheet"
- Style "white-space" and support for PRE
- Nested lists and ordered lists, Style "list-style-type"
- Prepared parser for @page and @box

Version 3.0.5, 2007-10-25

- Initial implementation of @font-face
- Warnings are only shown if flag -w is set
- Relative @import implementations
- Workaround for styles beginning with asterics like "* font: small"
- Support for color=transparent (threw Exceptions before)
- For @import with now media, is now set media=all
- Fixed the .1 CSS parser problem
- Removed cssutils again because of problems with @import
- Ignore CDATA in style definitions
- New method c.debug and command line option --debug
- Better URL support
- CSS attributes may now start with hyphen for vendor specific styles e.g. "-pdf-page-break"
- Implemented @import
- Implemented @media
- Images are now recalculated to 96DPI too
- 1px = 1/96inch (96dpi) instead of 1px = 1pt = 1/72inch
- Added some new tests like test-css-media.html

Version 3.0.0

- Initial versions of pisa rewrite
