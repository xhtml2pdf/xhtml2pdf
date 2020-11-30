class UtilityCalcValues:

    def get_col_width(self, index, name=None):
        parent_width = self.doc_width
        if name:
            name = int(name)
            parent_width = self.cols_width[name - 1]
        result = self.cols.get(index)
        result = (parent_width * result) / 100
        self.cols_width.append(result)
        return result

    def get_max(self, lista):
        list_max = []
        mx_tuple = None
        maxss = 0
        for values in lista:
            if isinstance(values, list):
                maxss = 0
                for value in values:
                    if maxss < value[1]:
                        maxss = value[1]
                        mx_tuple = value
                list_max.append(mx_tuple[1])
            else:
                list_max.append(self.next_frame)
        self.set_max(lista, list_max)

    def set_max(self, lista, list_max):
        for i in range(len(list_max)):
            if isinstance(lista[i], list):
                lista[i].append(list_max[i])
        return lista

    def cols_increment(self, parent, parent_column, cols_values, cols_child, cols):
        if parent_column:
            cols_child = cols_child + int(cols_values.get('colSize'))
        if parent:
            cols = cols + int(cols_values.get('colSize'))
        if not parent_column and not parent:
            cols = cols + int(cols_values.get('colSize'))
        cols_result = {
            'cols_child': cols_child,
            'cols': cols,
        }
        return cols_result

    def get_num_child(self, index):
        list = self.children
        cont = 0
        for value in list:
            if value == index:
                cont = cont + 1
        return cont