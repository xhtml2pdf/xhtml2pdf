from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.widgets.markers import makeMarker

from util import getColor


class Props:

    def __init__(self, instance):
        self.prop_map = [("y", int), ("width", int), ("height", int), ("data", lambda x: x),
                         ("labels", lambda x: instance.assign_labels(x))]

    def add_prop(self, data):
        self.prop_map += data


class BaseChart:

    def load_extra_data(self):
        pass

    def set_properties(self, data, props=None):

        if props is None:
            props = Props(self)

        for key, fnc in props.prop_map:
            if key in data:
                try:
                    value = fnc(data[key])

                    if value is not None:
                        self.__setattr__(key, value)
                except:
                    continue

class HorizontalBar(HorizontalBarChart, BaseChart):

    def __init__(self):
        super().__init__()
        self.barLabelFormat = '%2.0f'

    def set_properties(self, data, props=None):
        props = Props(self)
        props.add_prop([("x", int)])
        super().set_properties(data, props=props)

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels


class VerticalBar(VerticalBarChart, BaseChart):

    def __init__(self):
        super().__init__()
        self.barLabelFormat = '%2.0f'

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels

class HorizontalLine(HorizontalLineChart, BaseChart):

    def __init__(self):
        super().__init__()
        self.lineLabelFormat = '%2.0f'

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels


    def set_properties(self, data, props=None):
        props = Props(self)
        props.add_prop([("fillColor", getColor)])
        props.add_prop([("marker", self.fill_marker)])
        super().set_properties(data, props=props)

    def fill_marker(self, fill_type):

        for x in range(len(self.data)):
            self.lines[x].symbol = makeMarker(fill_type)


class PieChart(Pie, BaseChart):

    def __init__(self):
        super().__init__()
        self.sideLabels = 1

    def assign_labels(self, labels):
        self.labels = labels


class DoughnutChart(Doughnut, BaseChart):

    def __init__(self):
        super().__init__()

    def assign_labels(self, labels):
        self.labels = labels
