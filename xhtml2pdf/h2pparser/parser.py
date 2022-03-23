import logging

import cssselect2
from html5lib import treebuilders
from html5lib.html5parser import HTMLParser
from . import tags
import logging

from .CSSparser import CSSParser

logger = logging.getLogger('xhtml2pdf')

class Xhtml2pdfParser:
    root = None
    tags = {}
    csstree = None

    def __init__(self, src, context={}, link_callback=None, default_css=None):
        self.src = src
        self.nodes = {}
        self.context = context
        self.css_tree={}
        self.css_parser = CSSParser(
            self.css_tree,
            link_callback=link_callback)
        if default_css:
            self.css_parser.get_css_class(default_css)

    def get_tag(self, node):
        tagname = node.tag.replace('{%s}'%node.nsmap[node.prefix], '')
        klass=None
        if tagname in self.tags:
            return self.tags[tagname]
        try:
            klass = getattr(tags, tagname.title())
            self.tags[tagname]=klass
        except AttributeError as e:
            logger.error(str(e))
        return klass

    def get_tag_by_id(self, tagid):
        return self.nodes.get(tagid)

    def create_node(self, node, parent=None):  # do css html magic
        tag = self.get_tag(node)
        if tag is None:
            return
        if parent is None:
            self.root=node

        #setattr(node, 'xhtml2pdf_node', tag(node, parent, self.csstree))
        instance = tag(node, parent, self.css_parser, self.context)
        setattr(instance, 'get_tag_by_id', self.get_tag_by_id)
        instance.pre_start()

        node_id = instance.get_id()
        #if not instance.can_delete():
        node.set('xhtml2pdf_node', node_id)
        self.nodes[node_id]=instance

        for child in node:
            childinstance=self.create_node(child, parent=node)

        instance.pre_end()
        return instance

    def build_pdf_structure(self, node): # do reportlab magic
        nodeid = node.get('xhtml2pdf_node')
        if nodeid:
            pdfnode=self.nodes[nodeid]
            pdfnode.process_css()
            pdfnode.post_start()
            for child in node:
                self.build_pdf_structure(child)
            pdfnode.post_end()

    def get_root(self, src, **parser_kwargs):
        parser = HTMLParser(tree=treebuilders.getTreeBuilder('lxml', remove_blank_text=True))
        return parser.parse(
                src, **parser_kwargs
            ).getroot()

    def print_xml(self, node, output):
        tag = self.get_tag_by_id(node.get('xhtml2pdf_node'))
        if tag:
            output.write(tag.show_xml())
        for child in node:
            self.print_xml(child, output)
        if tag:
            output.write('</%s>'%(tag.tagname))

    def parse(self, show_xml=None):
        root = self.get_root(self.src)
        pdfroot=self.create_node(root)
        data = self.build_pdf_structure(root)
        if show_xml is not None:
            self.print_xml(root, show_xml)
        return data


