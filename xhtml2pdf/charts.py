from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.widgets.markers import makeMarker


class BaseChart:
    prop_map = None

    def __init__(self):
        self.prop_map = [("x", int), ("y", int), ("width", int), ("height", int), ("data", lambda x: x), ("labels", lambda x: self.assign_labels(x))]

    def load_extra_data(self):
        pass

    def set_properties(self, data):

        for key, fnc in self.prop_map:
            if key in data:
                try:
                    self.__setattr__(key, fnc(data[key]))
                except:
                    continue

class HorizontalBar(HorizontalBarChart, BaseChart):

    def __init__(self):
        BaseChart.__init__(self)
        super().__init__()
        self.barLabelFormat = '%2.0f'


    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels


class VerticalBar(VerticalBarChart, BaseChart):

    def __init__(self):
        super(BaseChart, self).__init__()
        super().__init__()
        self.barLabelFormat = '%2.0f'

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels

class HorizontalLine(HorizontalLineChart, BaseChart):

    def __init__(self):
        super(BaseChart, self).__init__()
        super().__init__()
        self.lineLabelFormat = '%2.0f'

    def assign_labels(self, labels):
        self.categoryAxis.categoryNames = labels

    def load_extra_data(self):
        #if 'filledcircle' in self.json and self.json['filledcircle']:
        for x in range(len(self.data)):
            self.lines[x].symbol = makeMarker('FilledCircle')


class PieChart(Pie, BaseChart):

    def __init__(self):
        super(BaseChart, self).__init__()
        super().__init__()
        self.sideLabels = 1

    def assign_labels(self, labels):
        self.labels = labels


class DoughnutChart(Doughnut, BaseChart):

    def __init__(self):
        super(BaseChart, self).__init__()
        super().__init__()

    def assign_labels(self, labels):
        self.labels = labels
