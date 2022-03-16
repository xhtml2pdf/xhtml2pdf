from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.widgets.markers import makeMarker


class BaseChart:

    def load_extra_data(self):
        pass


class HorizontalBar(HorizontalBarChart, BaseChart):

    def __init__(self):
        super().__init__()
        self.barLabelFormat = '%2.0f'

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

    def load_extra_data(self):
        for x in range(len(self.data)):
            self.lines[x].symbol = makeMarker('FilledCircle')


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
