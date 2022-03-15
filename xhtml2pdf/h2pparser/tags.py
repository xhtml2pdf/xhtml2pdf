import uuid


class BaseTag:
    def __init__(self, node, parent, csstree, context):
        self.node = node
        self.parent = parent
        self.csstree = csstree
        self.context = context

    def get_id(self):
        """
        Unique identify of tag
        """
        return str(uuid.uuid4())

    def pre_start(self):
        pass

    def pre_end(self):
        pass

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
    pass

class Meta(BaseTag):
    pass

class Div(BaseTag):
    def pre_end(self):
        self.cssnode=self.csstree.get_node(self.node.html_id())

    def post_start(self):
        #build = buildermanager.get_builder(self.cssnode.getDivType())
        pass

