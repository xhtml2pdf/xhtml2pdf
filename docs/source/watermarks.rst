How To Use Watermarks
========================

.. note::
    WaterMarks use other pdf as background, so images build new pdf automatically


WaterMark in all pages
-------------------------
To add a watermark to the PDF, use the `background-image` property to specify a background image

.. code:: html

    @page  {
	   size: a3;
	   background-image: url('img/mybackground.pdf');
    }


WaterMark in various pages
----------------------------

.. note::
    If you use images as background, try to use an image with the same size of the page, otherwise image will be scaled

You can use page name to separate backgrounds. All pages cover by the page name use the same background.

.. code:: html

    @page page1 {
	   size: a4;
	   background-image: url('img/mybackground.png');
    }

    @page page2 {
	   size: a4;
	   background-image: url('img/otherbackground.pdf');
    }

Some available configurations when you use images:

- **background-opacity:** a number from 0 to 1, example 0.5
- **background-object-position:** position of the image in the page, set as left bottom   ej. 500px 300px;
- **background-height:**  height of the image ej 50px
- **background-width:** width of the image ej 20px
- **background-page-step:** Use when you want to step pages without watermark, default 1