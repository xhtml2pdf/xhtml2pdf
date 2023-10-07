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


Please read reportlab documentation to know how object need to be created.

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
