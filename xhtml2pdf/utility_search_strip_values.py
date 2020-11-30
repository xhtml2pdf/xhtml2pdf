from reportlab.platypus import Paragraph
import re


class UtilitySearchStrip:

    def search_strip_str(self, flowable):
        if isinstance(flowable, Paragraph):
            text = flowable.text
        else:
            text = flowable.get('text')
        result = re.search(r'[\w.-]+#[\w.-]+', text)
        text = text.lstrip(result.group())
        text = text.lstrip()
        return text

    def searching_index(self, flowable):
        if isinstance(flowable, Paragraph):
            index = re.search(r'-\w+', flowable.text)
        else:
            index = re.search(r'-\w+', flowable.get('text'))
        index = index.group()
        index = index.lstrip('-')
        return index

    def clean_text_flowables(self):
        cleans_flowables = []
        for flow in self.flowElements:
            if isinstance(flow, Paragraph):
                text = self.search_strip_str(flow)
                nf = Paragraph(text, self.style)
                cleans_flowables.append(nf)
            if isinstance(flow, dict):
                text = self.search_strip_str(flow)
                flow['text'] = text
                cleans_flowables.append(flow)
        self.flowElements = cleans_flowables

    def clean_text_flowable(self, flow):
        text = self.search_strip_str(flow)
        nf = Paragraph(text, self.style)
        return nf