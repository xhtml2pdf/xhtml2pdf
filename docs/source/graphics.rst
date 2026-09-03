Graphs in canvas
################

Canvas in xhtml2pdf have different types of printings, when you have to build graphs you have to
set `type="graph"`, also it's important set width and height.

Canvas tag allows create, customize, and add charts to the story context that PDF receive for its creation.
It needs to be a graph type canvas, also width and height properties can be changed.

Charts available are:

- Vertical Bar `verticalbar`
- Horizontal Bar `horizontalbar`
- Horizontal Line `horizontalline`
- Pie `pie`
- Legend Pie `legendedPie`
- Doughnut  `doughnut`

It's necessary received a json inside the canvas with the following fields:

Required data:

- type
- data
- labels

Optional data:

- title
- legend
- x position
- y position
- background

Please read reportlab documentation to know how object need to be created.

Size and position
=================

The ``width`` and ``height`` of the canvas are the box the chart is given, in
points, and CSS ``width`` and ``height`` are read too and take precedence over
the attributes. A chart that says nothing about its own geometry fills that
box; one that sets any of ``x``, ``y``, ``width`` or ``height`` is left exactly
where it puts itself.

Whatever is drawn outside the box -- a legend positioned past the right edge,
say -- still gets its room reserved: the drawing grows to hold it and a warning
says so, rather than painting over whatever comes next on the page.

A canvas wider than the frame it lands in is scaled down to fit instead of
overflowing it.

There is no background behind a chart unless one is asked for, with the
``background`` key and reportlab's own property names:

.. code:: html

    <canvas type="graph" width="350" height="150">
          {
                "type": "pie",
                "data": [[10, 20, 30]],
                "labels": ["a", "b", "c"],
                "background": {"fillColor": "#f8fce8", "strokeColor": "#868686",
                               "strokeWidth": 1}
          }
    </canvas>

.. code:: html

    <canvas type="graph" width="350" height="180">
    Json Object Here
    </canvas>

For example:

.. code:: html

    <canvas type="graph" width="350" height="150">
          {
                "data": [[10, 20, 30, 40, 50, 60]],
                "labels": ["a", "b", "c", "d", "e", "f"],
                "title": {"_text": "Horizontal Bar Chart(1 Group)", "x": 290, "y": 155},
                "type": "horizontalbar",
                "x": 150, "y": 50,
                "barLabelFormat": "%2.0f",
                "bars": {"strokeColor": "#f01f34"},
                "barLabels": {"nudge": 5},
                "categoryAxis": {"strokeColor": "#f01f34"}
          }
    </canvas>

See more in examples.

Demonstration
=============

.. include:: /_generated/graphics.rst
