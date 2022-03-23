# encoding: utf-8


'''
Created on 25/11/2016

@author: luisza
'''
from __future__ import unicode_literals

from tinycss.css21 import PageRule, RuleSet
from tinycss.page3 import CSSPage3Parser, MarginRule
from tinycss.parsing import ParseError, strip_whitespace

from xhtml2pdf.files import getFile
import logging
log = logging.getLogger("xhtml2pdf")


class TinyCssParser(CSSPage3Parser):

    PAGE_FRAME = [
        "@page",
        "@frame",
    ]
    PAGE_MARGIN_AT_KEYWORDS = [

        "-pdf-next-page",
        "-pdf-page-break",
        "page-break-before",
        "-pdf-frame-break",
        "page-break-after",
        "-pdf-keep-with-next",
        "-pdf-outline",
        "-pdf-outline-level",
        "-pdf-outline-open",
        "-pdf-word-wrap",
        "-pdf-keep-in-frame-mode",
        "-pdf-keep-in-frame-max-width",
        "-pdf-keep-in-frame-max-height",
    ]


# parse_declaration(

#     def parse_at_rule(self, rule, previous_rules, errors, context):
#         print(rule.at_keyword)
#         return super(CSSPage3Parser, self).parse_at_rule(
#             rule, previous_rules, errors, context)

    def test_page(self, rule, previous_rules, errors, context):
        if context not in ['stylesheet', '@page']:
            raise ParseError(
                rule, '@page rule not allowed in ' + context)
        if rule.body is None:
            raise ParseError(
                rule, 'invalid {0} rule: missing block'.format(
                    rule.at_keyword))

    def parse_at_rule(self, rule, previous_rules, errors, context):
        if rule.at_keyword in self.PAGE_FRAME:
            #    print(rule.at_keyword, repr(rule.body), repr(context))

            if rule.at_keyword == '@page':
                declarations, at_rules, rule_errors = \
                    self.parse_declarations_and_at_rules(
                        rule.body, rule.at_keyword)
                errors.extend(rule_errors)
                return PageRule(
                    (rule.at_keyword.replace("@", ""), 'unknow'),
                    (0, 0, 0), declarations, at_rules,
                    rule.line, rule.column)

            elif rule.at_keyword == '@frame':
                self.test_page(rule, previous_rules, errors, context)
                declarations, body_errors = self.parse_declaration_list(
                    rule.body)
                errors.extend(body_errors)
                #print(rule.head, "--- ", declarations)
                selector = self.parse_frame_selector(rule.head)
                rule_set = RuleSet(
                    selector, declarations, rule.line, rule.column)
                rule_set.at_keyword = "frame"
                return rule_set

        if rule.at_keyword in self.PAGE_MARGIN_AT_KEYWORDS:
            if context not in ['@page', '@frame']:
                raise ParseError(
                    rule, '{0} rule not allowed in {1}'.format(
                        rule.at_keyword, context))
            if rule.head:
                raise ParseError(
                    rule.head[0],
                    'unexpected {0} token in {1} rule header'.format(
                        rule.head[0].type, rule.at_keyword))
            declarations, body_errors = self.parse_declaration_list(rule.body)
            errors.extend(body_errors)
            return MarginRule(
                rule.at_keyword, declarations, rule.line, rule.column)
        return super(CSSPage3Parser, self).parse_at_rule(
            rule, previous_rules, errors, context)

    def parse_frame_selector(self, head):
        """Parse an @page selector.

        :param head:
            The ``head`` attribute of an unparsed :class:`AtRule`.
        :returns:
            A page selector. For CSS 2.1, this is 'first', 'left', 'right'
            or None. 'blank' is added by GCPM.
        :raises:
            :class`~parsing.ParseError` on invalid selectors

        """
        if not head:
            return (None, None), (0, 0, 0)
        if head[0].type == 'IDENT':
            name = head.pop(0).value
            return (name, None), (1, 0, 0)


class CSSNode(object):

    def __init__(self, name, attrs):
        self.name = name
        self.attrs = attrs

    def update_attrs(self, attrs):
        self.attrs.update(attrs)

    def get_rules(self):
        return self.attrs

    def __str__(self):
        return "Style = " + repr(self.attrs)

    def __len__(self):
        return len(self.attrs)


class CSSParser:

    def __init__(self, tree, link_callback=None):
        self.tree = tree
        self.parser = TinyCssParser()
        self.link_callback = link_callback

    def parse_link(self, url):
        log.debug('parse_link', url)
        pisafile = getFile(url, callback=self.link_callback)
        data = pisafile.getData()
        if data:
            self.get_css_class(data)

    def get_css_class(self, css, name=None):
        stylesheet = self.parser.parse_stylesheet(css)
        # print(stylesheet.rules)
        css_names = []
        for rule in stylesheet.rules:
            if type(rule.selector) is tuple:
                attrs = dict([(d.name, d.value.as_css())
                              for d in rule.declarations])
                attrs['frames'] = {}
                for rul in rule.at_rules:
                    attrs['frames'][rul.selector[0][0]] = dict(
                        [(d.name, d.value.as_css()) for d in rul.declarations])

                self.tree["@page"] = CSSNode(
                    "page",
                    attrs)
                continue

            name = name if rule.selector.as_css(
            ) is None else rule.selector.as_css()

            attrs = dict([(d.name, d.value.as_css())
                          for d in rule.declarations])
            if name in self.tree:
                self.tree[name].update_attrs(attrs)
            else:
                self.tree[name] = CSSNode(
                    name,
                    attrs)
            css_names.append(name)
        return css_names

    def process_tag_css(self, tag, attrs, active_node):
        if 'class' in attrs:
            classes = attrs['class'].split(" ")
            for cls in classes:
                if "." + cls not in self.tree:
                    self.tree["." + cls] = CSSNode("." + cls, {})

                active_node.set_css("." + cls)

        if 'style' in attrs:
            #css = self.css_parser.get_css_class(attrs['style'])
            css = self.get_css_class(
                attrs['style'], name="#" + active_node.get_html_id())

        if tag not in self.tree:
            self.tree[tag] = CSSNode(tag, {})

        active_node.set_css("#" + attrs['id'])
        active_node.set_css(tag)

    def clean_css(self, tagname, css_list):
        css = []
        for rule in css_list:
            if rule == "@page" and tagname != '@page':
                continue
            if rule in self.tree:
                if rule not in css:
                    if len(self.tree[rule]):
                        if " " in rule:
                            if rule.split(" ")[1] == tagname:
                                css.append(rule)
                        else:
                            css.append(rule)
                    else:
                        del self.tree[rule]
        return css

    def find_in_tree(self, name):
        if name in self.tree:
            if len(self.tree[name]):
                return [name]
        return []