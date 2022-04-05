
class GridBuilder:
    def __init__(self, width, heigth, columns=12, prefix='col'):
        self.width=width
        self.heigth=heigth
        self.columns=columns
        self.prefix = prefix
        self.blocks=[]
        self.print=''

    def build(self):

        size = self.width/self.columns


        for x in range(0, self.columns+1):
            for y in range(0, self.columns+1):
                if y-x<0:
                    continue
                self.print+="\n.%(prefix)s-%(x)s%(y)s { %(rules)s }"%{
                'prefix': self.prefix,
                'x': x, 'y': "-"+str(y) if x!=y else '', 'rules': self.get_props( x, y, size)
                }
        return self.print


    def get_props(self, x, y, size):
        return """
left: %f;
width: %f;   
        """%(x*size, (y+1)*size-x*size if x!=y else size)
