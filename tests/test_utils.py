#-*- coding: utf-8 -*-
from reportlab.lib.colors import Color
from unittest import TestCase
from xhtml2pdf.util import getCoords, getColor, getSize

class UtilsCoordTestCase(TestCase):
    
    def test_getCoords_simple(self):
        
        res = getCoords(1, 1, 10, 10, (10,10))
        self.assertEqual(res, (1, -1, 10, 10))
        
        # A second time - it's memoized!
        res = getCoords(1, 1, 10, 10, (10,10))
        self.assertEqual(res, (1, -1, 10, 10))
        
    def test_getCoords_x_lt_0(self):
        res = getCoords(-1, 1, 10, 10, (10,10))
        self.assertEqual(res, (9, -1, 10, 10))
        
    def test_getCoords_y_lt_0(self):
        res = getCoords(1, -1, 10, 10, (10,10))
        self.assertEqual(res, (1, -9, 10, 10))
        
    def test_getCoords_w_and_h_none(self):
        res = getCoords(1, 1, None, None, (10,10))
        self.assertEqual(res, (1, 9))
        
    def test_getCoords_w_lt_0(self):
        res = getCoords(1, 1, -1, 10, (10,10))
        self.assertEqual(res, (1, -1, 8, 10))
        
    def test_getCoords_h_lt_0(self):
        res = getCoords(1, 1, 10, -1, (10,10))
        self.assertEqual(res, (1, 1, 10, 8))

class UtilsColorTestCase(TestCase):
    
    def test_get_color_simple(self):
        res = getColor('red')
        self.assertEqual(res, Color(1,0,0,1))
        
        # Testing it being memoized properly
        res = getColor('red')
        self.assertEqual(res, Color(1,0,0,1))
        
    def test_get_color_from_color(self):
        # Noop if argument is already a color
        res = getColor(Color(1,0,0,1))
        self.assertEqual(res, Color(1,0,0,1))
        
    def test_get_transparent_color(self):
        res = getColor('transparent', default='TOKEN')
        self.assertEqual(res, 'TOKEN')
        
        res = getColor('none', default='TOKEN')
        self.assertEqual(res, 'TOKEN')
        
    def test_get_color_for_none(self):
        res = getColor(None, default='TOKEN')
        self.assertEqual(res, 'TOKEN')
        
    def test_get_color_for_RGB(self):
        res = getColor('#FF0000')
        self.assertEqual(res, Color(1,0,0,1))
    
    def test_get_color_for_RGB_with_len_4(self):
        res = getColor('#F00')
        self.assertEqual(res, Color(1,0,0,1))
    
    def test_get_color_for_CSS_RGB_function(self):
        # It's regexp based, let's try common cases.
        res = getColor('rgb(255,0,0)')
        self.assertEqual(res, Color(1,0,0,1))
        
        res = getColor('<css function: rgb(255,0,0)>')
        self.assertEqual(res, Color(1,0,0,1))
        
class UtilsGetSizeTestCase(TestCase):
    
    def test_get_size_simple(self):
        res = getSize('12pt')
        self.assertEqual(res, 12.00)
        
        # Memoized...
        res = getSize('12pt')
        self.assertEqual(res, 12.00)
    
    def test_get_size_for_none(self):
        res = getSize(None, relative='TOKEN')
        self.assertEqual(res, 'TOKEN')
        
    def test_get_size_for_float(self):
        res = getSize(12.00)
        self.assertEqual(res, 12.00)
        
    def test_get_size_for_tuple(self):
        # TODO: This is a really strange case. Probably should not work this way.
        res = getSize(("12", ".12"))
        self.assertEqual(res, 12.12)
        
    def test_get_size_for_cm(self):
        res = getSize("1cm")
        self.assertEqual(res, 28.346456692913385)
        
    def test_get_size_for_mm(self):
        res = getSize("1mm")
        self.assertEqual(res, 2.8346456692913385)
        
    def test_get_size_for_i(self):
        res = getSize("1i")
        self.assertEqual(res, 72.00)
        
    def test_get_size_for_in(self):
        res = getSize("1in")
        self.assertEqual(res, 72.00)
        
    def test_get_size_for_inch(self):
        res = getSize("1in")
        self.assertEqual(res, 72.00)
        
    def test_get_size_for_pc(self):
        res = getSize("1pc")
        self.assertEqual(res, 12.00)
        
    def test_get_size_for_none_str(self):
        res = getSize("none")
        self.assertEqual(res, 0.0)
        res = getSize("0")
        self.assertEqual(res, 0.0)
        res = getSize("auto") # Really?
        self.assertEqual(res, 0.0)