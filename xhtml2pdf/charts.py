from collections.abc import Callable
from contextvars import ContextVar

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import LegendedPie, Pie
from reportlab.graphics.widgets.markers import makeMarker

from xhtml2pdf.util import getColor

#: Turns the fontName a chart's JSON gives into a face ReportLab registered.
#: A font-family as the stylesheet names it -- "Noto Sans" -- is registered as
#: "noto sans_00", and only the <canvas> tag, which has the document's fonts,
#: can tell; it sets this while it reads the JSON.
font_resolver: ContextVar[Callable[[object], str]] = ContextVar(
    "font_resolver", default=str
)


def set_properties(obj, data, prop_map):
    for key, fnc in prop_map:
        if key in data:
            try:
                value = fnc(data[key])

                if value is not None:
                    setattr(obj, key, value)
            except Exception:
                continue


def _color_name_pairs(pairs) -> list:
    """A legend's [colour, name] pairs from JSON, the colours read as colours."""
    return [(getColor(color), str(name)) for color, name in pairs]


class Props:
    def __init__(self, instance) -> None:
        font = font_resolver.get()
        self.prop_map = [
            ("x", int),
            ("y", int),
            ("width", int),
            ("height", int),
            ("data", lambda x: x),
            ("labels", instance.assign_labels),
        ]
        self.prop_map_title = [("x", int), ("y", int), ("_text", str)]
        self.prop_map_legend = [
            ("x", int),
            ("y", int),
            ("deltax", int),
            ("alignment", str),
            ("boxAnchor", str),
            ("fontSize", int),
            ("strokeWidth", int),
            ("dy", int),
            ("dx", int),
            ("dxTextSpace", int),
            ("deltay", int),
            ("columnMaximum", int),
            ("variColumn", int),
            ("deltax", int),
            ("fontName", font),
            ("colorNamePairs", _color_name_pairs),
        ]
        self.prop_map_legend1 = [("x", int), ("y", int)]
        self.prop_map_bars = [("strokeWidth", int)]
        self.prop_map_barLabels = [
            ("nudge", int),
            ("fontSize", int),
            ("fontName", font),
        ]
        self.prop_map_categoryAxis = [
            ("visibleTicks", int),
            ("strokeWidth", int),
            ("tickShift", int),
            ("labelAxisMode", str),
        ]
        self.prop_map_categoryAxis_labels = [
            ("angle", int),
            ("dy", int),
            ("fontSize", int),
            ("boxAnchor", str),
            ("fontName", font),
            ("textAnchor", str),
        ]
        self.prop_map_valueAxis = [
            ("valueMin", float),
            ("valueMax", float),
            ("valueStep", float),
            ("forceZero", bool),
            ("visible", bool),
            ("visibleTicks", bool),
            ("visibleGrid", bool),
            ("gridStrokeWidth", float),
            ("gridStrokeColor", getColor),
            ("strokeWidth", float),
            ("strokeColor", getColor),
            ("labelTextFormat", str),
        ]
        self.prop_map_valueAxis_labels = [
            ("angle", int),
            ("dx", int),
            ("dy", int),
            ("fontSize", int),
            ("fontName", font),
            ("fillColor", getColor),
            ("boxAnchor", str),
            ("textAnchor", str),
        ]
        self.prop_map_slices = [
            ("strokeWidth", int),
            ("labelRadius", float),
            ("poput", int),
            ("fontName", font),
            ("fontSize", int),
            ("strokeDashArray", str),
        ]

    @staticmethod
    def add_prop(prop_map, data):
        prop_map += data


class BaseChart:
    # Every concrete chart mixes this class in with a reportlab widget, and
    # the widget is what carries the geometry. Declared, not assigned: the
    # widget's own attributes are left alone, and a caller holding a
    # BaseChart can still place and size one.
    x: float
    y: float
    width: float
    height: float

    def set_legend(self, data, legend, props=None):
        if props is None:
            props = Props(self)
        set_properties(legend, data, props.prop_map_legend)
        return legend

    def load_data_legend(self, data, legend):
        if isinstance(data.get("legend"), dict) and data["legend"].get(
            "colorNamePairs"
        ):
            # The author's own entries, which set_legend has read.
            return
        series = self.series_legend(data)
        if series is not None:
            legend.colorNamePairs = series
            return
        legend.colorNamePairs = []
        color = self.get_colors()

        for x, obj in enumerate(data["data"]):
            if isinstance(obj, list):
                for y, value in enumerate(obj):
                    if color:
                        if data["type"] == "doughnut":
                            legend.colorNamePairs.append(
                                (color[x], (data["labels"][y], " ", str(value)))
                            )
                        else:
                            legend.colorNamePairs.append(
                                (color[y], (data["labels"][y], " ", str(value)))
                            )
            elif color:
                legend.colorNamePairs.append(
                    (color[x], (data["labels"][x], " ", str(obj)))
                )

    #: The collection that styles each series of a bar or line chart, and
    #: the attribute of an entry that is the series' colour. A pie or a
    #: doughnut colours by slice and has none.
    SERIES_STYLES: str | None = None
    SERIES_COLOR: str = "fillColor"

    def series_styles(self):
        """The collection whose entries style each series, or None."""
        return getattr(self, self.SERIES_STYLES) if self.SERIES_STYLES else None

    def series_legend(self, data) -> list | None:
        """
        One legend entry per series, for a chart that colours by series.

        None for a pie or a doughnut, which colour by slice.
        """
        if self.series_styles() is None:
            return None
        return self._series_legend(data)

    def set_series(self, data) -> None:
        """
        Colour each series as `seriesColors` says.

        ReportLab has three series styles and picks one with the series
        number modulo how many there are, so a fourth series came out red
        again; each colour given here is a style of its own.
        """
        styles = self.series_styles()
        colors = data.get("seriesColors")
        if styles is None or not isinstance(colors, list):
            return
        attribute = self.SERIES_COLOR
        for index, color in enumerate(colors):
            value = getColor(color, None)
            if value is not None:
                setattr(styles[index], attribute, value)

    def _series_legend(self, data) -> list:
        styles = self.series_styles()
        rows = [row for row in data.get("data", []) if isinstance(row, list)]
        names = data.get("seriesNames")
        if not isinstance(names, list):
            names = []
        pairs = []
        for index in range(len(rows)):
            style = styles[index % len(styles)]
            name = str(names[index]) if index < len(names) else f"Series {index + 1}"
            pairs.append((getattr(style, self.SERIES_COLOR), name))
        return pairs

    def set_title_properties(self, data, title, props=None):
        if props is None:
            props = Props(self)
        set_properties(title, data, props.prop_map_title)
        return title

    def set_properties(self, data, props=None):
        if props is None:
            props = Props(self)
        set_properties(self, data, props.prop_map)

    def set_valueAxis(self, data, props=None):
        """
        The value axis of a bar or line chart: its range, ticks and grid.

        Left alone, ReportLab scales the axis from the smallest value, so a
        bar chart whose data does not reach zero is drawn with a truncated
        axis and bars whose lengths do not compare.
        """
        if props is None:
            props = Props(self)
        set_properties(self.valueAxis, data, props.prop_map_valueAxis)
        if isinstance(data.get("labels"), dict):
            set_properties(
                self.valueAxis.labels, data["labels"], props.prop_map_valueAxis_labels
            )

    @staticmethod
    def get_colors():
        return []


class BaseBarChart(BaseChart):
    def __init__(self) -> None:
        super().__init__()

    def set_properties(self, data, props=None):
        props = Props(self)
        # Lengths: as strings they passed here and broke the drawing, which
        # adds them to numbers.
        props.add_prop(props.prop_map, [("barWidth", float)])
        props.add_prop(props.prop_map, [("barSpacing", float)])
        props.add_prop(props.prop_map, [("barLabelFormat", str)])
        props.add_prop(props.prop_map, [("strokeColor", getColor)])
        props.add_prop(props.prop_map, [("groupSpacing", int)])
        super().set_properties(data, props=props)

        if "bars" in data:
            self.set_bars(data["bars"], props=props)

        if "barLabels" in data:
            self.set_barLabels(data["barLabels"], props=props)

        self.set_series(data)

        if isinstance(data.get("valueAxis"), dict):
            self.set_valueAxis(data["valueAxis"], props=props)

        if "categoryAxis" in data:
            self.set_categoryAxis(data["categoryAxis"], props=props)

            if "labels" in data["categoryAxis"]:
                self.set_categoryAxis_labels(
                    data["categoryAxis"]["labels"], props=props
                )

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels

    SERIES_STYLES = "bars"

    def set_bars(self, data, props=None):
        if props is None:
            props = Props(self)
        props.add_prop(props.prop_map_bars, [("strokeColor", getColor)])
        set_properties(self.bars, data, props.prop_map_bars)

    def set_barLabels(self, data, props=None):
        if props is None:
            props = Props(self)
        set_properties(self.barLabels, data, props.prop_map_barLabels)

    def set_categoryAxis(self, data, props=None):
        if props is None:
            props = Props(self)
        props.add_prop(props.prop_map_categoryAxis, [("strokeColor", getColor)])
        set_properties(self.categoryAxis, data, props.prop_map_categoryAxis)

    def set_categoryAxis_labels(self, data, props=None):
        if props is None:
            props = Props(self)
        props.add_prop(props.prop_map_categoryAxis_labels, [("fillColor", getColor)])
        set_properties(
            self.categoryAxis.labels, data, props.prop_map_categoryAxis_labels
        )


class HorizontalBar(HorizontalBarChart, BaseBarChart):
    pass


class VerticalBar(VerticalBarChart, BaseBarChart):
    pass


class HorizontalLine(HorizontalLineChart, BaseChart):
    def __init__(self) -> None:
        super().__init__()

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels

    def set_properties(self, data, props=None):
        props = Props(self)
        props.add_prop(props.prop_map, [("fillColor", getColor)])
        props.add_prop(props.prop_map, [("lineLabelFormat", str)])
        props.add_prop(props.prop_map, [("strokeColor", getColor)])
        props.add_prop(props.prop_map, [("joinedLines", int)])
        props.add_prop(props.prop_map, [("marker", self.fill_marker)])
        super().set_properties(data, props=props)
        self.set_series(data)

        if isinstance(data.get("valueAxis"), dict):
            self.set_valueAxis(data["valueAxis"], props=props)

    SERIES_STYLES = "lines"
    SERIES_COLOR = "strokeColor"

    def fill_marker(self, fill_type):
        for x in range(len(self.data)):
            self.lines[x].symbol = makeMarker(fill_type)

    @staticmethod
    def get_colors():
        return []


class PieChart(Pie, BaseChart):
    def __init__(self) -> None:
        super().__init__()

    def set_properties(self, data, props=None):
        props = Props(self)
        props.add_prop(props.prop_map, [("sideLabels", int)])
        props.add_prop(props.prop_map, [("simpleLabels", int)])
        props.add_prop(props.prop_map, [("sideLabelsOffset", int)])
        props.add_prop(props.prop_map, [("startAngle", int)])
        props.add_prop(props.prop_map, [("orderMode", str)])
        props.add_prop(props.prop_map, [("direction", str)])
        super().set_properties(data, props=props)

        if "slices" in data:
            self.set_slices(data["slices"], props=props)

    def assign_labels(self, labels):
        self.labels = labels

    def set_slices(self, data, props=None):
        if props is None:
            props = Props(self)
        props.add_prop(props.prop_map_slices, [("strokeColor", getColor)])
        props.add_prop(props.prop_map_slices, [("fillColor", getColor)])
        set_properties(self.slices, data, props.prop_map_slices)

    def get_colors(self):
        colors_list = []
        for x, _obj in enumerate(self.data):
            colors_list.append(self.slices[x].fillColor)
        return colors_list


class LegendedPieChart(LegendedPie, BaseChart):
    def __init__(self) -> None:
        super().__init__()
        self.legend1.x = 350
        self.legend1.y = 150

    def set_properties(self, data, props=None):
        props = Props(self)
        props.add_prop(props.prop_map, [("legend_data", list)])
        super().set_properties(data, props=props)

        if "legend1" in data:
            self.set_legend1(self.legend1, data["legend1"], props=props)

    def set_legend1(self, obj, data, props=None):
        if props is None:
            props = Props(self)
        set_properties(obj, data, props.prop_map_legend1)

    def assign_labels(self, labels):
        self.legend_names = labels


class DoughnutChart(Doughnut, BaseChart):
    def __init__(self) -> None:
        super().__init__()

    def assign_labels(self, labels):
        self.labels = labels

    def get_colors(self):
        colors = []
        for x, _obj in enumerate(self.data):
            colors.append(self.slices[x].fillColor)
        return colors
