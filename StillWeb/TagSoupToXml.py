# -*- coding: utf-8 -*-
# TagSoupToXml.py - Loose-syntax HTML parser
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

import html.parser
import html.entities
import re
from xml.dom import minidom

# TagSoupToXml - Based on phpTagSoup-0.2/TagSoup/ToXML.php (which I wrote)

class TagSoupToXml(html.parser.HTMLParser):
    # Elements that are always empty, according to the HTML4 spec:
    #  http://www.w3.org/TR/html4/index/elements.html
    forbidden_endtags = set((
        'area', 'base', 'basefont', 'br', 'col', 'frame', 'hr', 'img',
        'input', 'isindex', 'link', 'meta', 'param'))

    # Elements that should not be their own parents.
    # There are probably bugs here.
    forbidden_parents = set(('p', 'option', 'col', 'colgroup'))

    # Elements that should have specific parents (note that this does not
    # actually guarantee that these elements will have one of the
    # specified parents).
    # There are probably bugs here.
    mandatory_parents = {
        'li': set(('ul', 'ol')),
        'td': set(('tr', 'table')),
        'th': set(('tr', 'table')),
        'tr': set(('table', 'tbody', 'thead', 'tfoot')),
        'dd': set(('dl')),
        'dt': set(('dl')),
    };

    def __init__(self, omit_comments=False):
        super().__init__()
        self.omit_comments = omit_comments

    def reset(self):
        super().reset()

        self.tagstack = []

        self.output_buffer = None
        self.prologue = "";
        self.html_tag = None
        self.head_tag = None
        self.head_content = None
        self.body_tag = None
        self.body_content = None

    def close(self):
        super().close()
        self.handle_finish()

    def add_output(self, text):
        if self.output_buffer is not None:
            self.output_buffer.append(text)
        elif self.body_content is None:
            if self.head_content is None:
                self.head_content = []
            self.head_content.append(text)
        else:
            self.body_content.append(text)

    def handle_data(self, data):
        self.add_output(html.escape(data))

    def handle_charref(self, name):
        if name.lower().startswith("x"):
            c = int(name[1:], 16)
        else:
            c = int(name)
        self.add_output("&#x%X;" % (c,))

    def handle_entityref(self, name):
        c = html.entities.name2codepoint[name]
        self.add_output("&#x%X;" % (c,))

    def handle_starttag(self, tagname, attributes=None):
        # Lowercase the tag name
        tagname = tagname.lower()

        # Lowercase and sort the attribute names
        attr_list = []
        if attributes:
            for (k, v) in attributes:
                attr_list.append((k, v))
            attr_list.sort()

        # Ignore duplicate HTML, HEAD, and BODY tags
        if ((tagname == "html" and self.html_tag is not None) or
                (tagname == "head" and self.head_tag is not None) or
                (tagname == "body" and self.body_tag is not None)):
            return

        # Handle elements that shouldn't be parents of themselves
        if tagname in self.forbidden_parents and self.tagstack and self.tagstack[-1] == tagname:
            tn = self.tagstack.pop()
            self.add_output("</%s>" % (tn,))

        # Handle tags that should have specific parents
        for (child, parents) in self.mandatory_parents.items():
            if tagname != child:    # li should have ul or ol as a parent
                continue
            for i in range(len(self.tagstack)-1, -1, -1):
                if self.tagstack[i] not in parents:
                    continue
                for j in range(len(self.tagstack)-i-1):
                    tn = self.tagstack.pop()
                    self.add_output("</%s>" % (tn,))
                break
            break

        if tagname in ("html", "head"):
            self.output_buffer = []
        elif tagname == "body":
            self.handle_endtag("head")
            self.output_buffer = []

        self.add_output("<%s" % (tagname,))
        for (k, v) in attr_list:
            self.add_output(' %s="%s"' % (k, html.escape(v, quote=True)))
        if tagname in self.forbidden_endtags:
            self.add_output(" />")  # self-closing tag
        else:
            self.add_output(">")
            if tagname not in ("html", "head", "body"):
                self.tagstack.append(tagname)

        if tagname == "html":
            self.html_tag = "".join(self.output_buffer)
            self.output_buffer = None
        elif tagname == "head":
            self.head_tag = "".join(self.output_buffer)
            self.output_buffer = None
        elif tagname == "body":
            self.body_tag = "".join(self.output_buffer)
            self.output_buffer = None
            if self.body_content is None:
                self.body_content = []

    def handle_endtag(self, tagname):
        # Lowercase the tag name
        tagname = tagname.lower()

        # Don't close HTML, HEAD, or BODY tags here, but close everything else.
        if tagname in ("html", "head", "body"):
            while self.tagstack:
                tn = self.tagstack.pop()
                self.add_output("</%s>" % (tn,))
            return

        # If the tag wasn't opened, don't close it.
        if tagname not in self.tagstack:
            return;

        # Force proper nesting of tags
        while self.tagstack[-1] != tagname:
            tn = self.tagstack.pop()
            self.add_output("</%s>" % (tn,))
        assert self.tagstack

        # Close the tag
        tn = self.tagstack.pop()
        assert tn == tagname
        self.add_output("</%s>" % (tn,))

    def handle_comment(self, data):
        if self.omit_comments:
            return

        # According to XML 1.0 section 2.5 ("Comments"):
        #  "For compatibility, the string "--" (double-hyphen) MUST NOT occur
        #  within comments."
        data = re.compile(r'-(?=-)', re.S).sub('- ', data)

        # Also, XML comments can't end in '-'
        if data.endswith("-"):
            data += " "

        self.add_output("<!--%s-->" % (data,));

    def handle_decl(self, decl):
        return;     # Omit SGML declarations

    def handle_finish(self):
        # Close all open tags
        while self.tagstack:
            tn = self.tagstack.pop()
            self.add_output("</%s>" % (tn,))

        if self.html_tag is None:
            self.html_tag = "<html>"
        if self.head_tag is None:
            self.head_tag = "<head>"
        if self.body_tag is None:
            self.body_tag = "<body>"
            self.body_content = self.head_content
            self.head_content = []

    def toxml(self):
        self.close()
        return "".join(
            [self.prologue, self.html_tag, self.head_tag] +
            self.head_content +
            ["</head>", self.body_tag] +
            self.body_content +
            ["</body></html>"])

    def todocument(self):
        return minidom.parseString('<?xml version="1.0" encoding="UTF-8"?>' + self.toxml())

if __name__ == '__main__':
    p = TagSoupToXml()
    p.feed(open("pages/index.html", "rb").read())
    print(p.toxml())

# vim:set ts=4 sw=4 sts=4 expandtab:
