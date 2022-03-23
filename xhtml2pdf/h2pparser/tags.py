import uuid

class BaseTag:
    def __init__(self, node, parent, cssparser, context):
        self.node = node
        self.parent = parent
        self.css_parser = cssparser
        self.context = context
        self.css_list=[]
        self.data = ""
        self._id=None
        self._css = None
        self.attrs = dict(node.attrib)
        self.tagname = self.__class__.__name__.lower()
        self.css = {}

    def get_id(self):
        """
        Unique identify of tag
        """
        if self._id is None:
            self._id=str(uuid.uuid4())
        return self._id

    def __str__(self):
        self.get_css_properties()
        dev = self.tagname +" (#%s)"%self.get_id() +" = [" + ",".join(self.css) + "]"
        return dev

    def get_html_id(self):
        if 'id' in self.node.attrib:
            return self.node.attrib['id']
        return self.get_id()

    def get_parent(self):
        if self.parent is not None:
            tagparent=self.parent.get('xhtml2pdf_node')
            if tagparent:
                return getattr(self, 'get_tag_by_id')(tagparent)

    def set_css(self, key):
        self.css_list.append(key)

    def set_data(self, data):
        self.data = data

    def get_css(self):
        """
        order
            - parent
            - parent class tag
            - parent tag
            - tag
            - class
            - id
        """
        if self._css:
            return self._css

        css_id = []
        parent = self.get_parent()

        if parent:
            # parent
            css_id += parent.get_css()
            # parent class tag
            if 'class' in parent.attrs:
                for cls in parent.attrs['class'].split(" "):
                    css_id += self.css_parser.find_in_tree("." + cls + " " + self.tagname)

            # parent tag
            if 'id' in parent.attrs:
                css_id += self.css_parser.find_in_tree("#" + parent.attrs['id'] +
                                            " " + self.tagname)

        css_id += self.css_parser.find_in_tree(self.tagname)
        # class
        if 'class' in self.attrs:
            for cls in self.attrs['class'].split(" "):
                css_id += self.css_parser.find_in_tree("." + cls)
        # id
        if 'id' in self.attrs:
            css_id += self.css_parser.find_in_tree("#" + self.attrs['id'])

        self.css_list = self.css_parser.clean_css(self.tagname, css_id)
        self._css = self.css_list
        return self.css

    def get_css_properties(self):
        if len(self.css)>0:
            return self.css
        css = self.get_css()
        for name in css:
            rules = self.css_parser.tree[name].get_rules()
            self.css.update(rules)
        return self.css

    def show_xml(self):
        style=''
        for x, y in self.get_css_properties().items():
            if type(y) is str:
                style += x + " : " + y + ";"
            elif type(y) is dict:
                for i, j in y.items():
                    style += i + " {"
                    style += "; ".join([z + " : " + w
                                      for z, w in j.items()])
                    style += "}"
        return '\n<%s id="%s" class="%s" style="%s">%s' % (self.tagname, self.get_html_id(),
                                                       ", ".join(self.get_css()), style, self.data)

    def pre_start(self):
        pass

    def pre_end(self):
        pass

    def process_css(self):
        self.get_css_properties()

    def post_start(self):
        pass

    def post_end(self):
        pass

    def set_text(self, text):
        pass

    def render(self):
        pass

    def can_delete(self):
        return False

class Head(BaseTag):
    def can_delete(self):
        return True

class Html(BaseTag):
    props = {
        'font': 'Helveltica'
    }

    def pre_end(self):
        #self.cssnode=self.csstree.get_node(self.node.html_id())
        pass

class Body(BaseTag):
    pass

class Title(BaseTag):
    pass


class Style(BaseTag):
    def can_delete(self):
        return True

    def pre_start(self):
        self.css_parser.get_css_class(self.node.text)

class Link(BaseTag):
    def can_delete(self):
        return True

    def pre_start(self):
        if 'rel' in self.attrs and (self.attrs['rel'] == 'stylesheet' or
                               'type' in self.attrs and self.attrs['type'] == 'text/css'):
            if 'href' in self.attrs:
                self.css_parser.parse_link(self.attrs['href'])

class Meta(BaseTag):
    pass

class Div(BaseTag):
    def pre_end(self):
        #self.cssnode=self.csstree.get_node(self.node.html_id())
        pass
    def post_start(self):
        #build = buildermanager.get_builder(self.cssnode.getDivType())
        pass

class P(BaseTag):
    def pre_start(self):
        self.set_data(self.node.text)

class Span(BaseTag):
    def pre_start(self):
        self.set_data(self.node.text)