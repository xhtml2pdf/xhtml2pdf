Graphs in canvas
##########################

Canvas in xhtml2pdf have different types of printings, when you have to build graphs you have to
set `type="graph"`, also it's important set width and height.

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