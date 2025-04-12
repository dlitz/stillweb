# -*- coding: utf-8 -*-
# LinkRewriter.py - Link (URL) rewriting
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

from StillWeb.sw_urllib import rebase_url, rfc3986_urljoin, relative_url
from StillWeb.sw_util import generate_fake_url, getChildText, replaceChildText

HTML_CRITERIA = [
    (None,                  (None, "href")),
    (None,                  (None, "src")),
    (None,                  (None,"usemap")),
    ((None, "form"),        (None, "action")),
    ((None, "img"),         (None, "longdesc")),
    ((None, "q"),           (None, "cite")),
    ((None, "blockquote"),  (None, "cite")),
]

class LinkRewriter:

    MATCHED_ELEMENT = 1
    MATCHED_ATTRIBUTE = 2

    def __init__(self, match_criteria):
        """

        match_criteria
            Sequence of (element, attribute) 2-tuples:

            element
                (namespaceURI, localName) or None.
                If element is None, then this matches any element.
                If namespaceURI is None, then the namespace is ignored.

            attribute
                (namespaceURI, localName) or None.
                If attribute is None, then this matches the *contents* of the
                element.  Otherwise, the attribute value is matched.
                If namespaceURI is None, then the namespace is ignored.
        """
        self._criteria = list(match_criteria)

    def match_element(self, node):
        assert node.nodeType == node.ELEMENT_NODE
        for criterion in self._criteria:
            (c_elem, c_attr) = criterion
            if c_elem is not None:
                (namespaceURI, localName) = c_elem
                if namespaceURI is not None and node.namespaceURI != namespaceURI:
                    continue
                if node.localName != localName:
                    continue
            if c_attr is None:
                yield (self.MATCHED_ELEMENT, node, criterion)
            else:
                (namespaceURI, localName) = c_attr
                for i in range(node.attributes.length):
                    a = node.attributes.item(i)
                    if namespaceURI is not None and a.namespaceURI != namespaceURI:
                        continue
                    if a.localName != localName:
                        continue
                    yield (self.MATCHED_ATTRIBUTE, (a.namespaceURI, a.localName), criterion)

    def rewrite_links(self, node, callback_func):
        """Rewrite links inside a document.

        For each link found, call `callback_func`, passing it the URL amd the
        matched criterion.

        The callback function should return the replacement URL.
        """
        assert node.nodeType in (node.DOCUMENT_NODE, node.ELEMENT_NODE)
        if node.nodeType == node.DOCUMENT_NODE:
            return self.rewrite_links(node.documentElement, callback_func)

        # Find any matching elements or attributes, and rewrite their URLs.
        for (m_type, m_match, m_criterion) in self.match_element(node):
            if m_type == self.MATCHED_ELEMENT:
                url = getChildText(node).strip()
                url = callback_func(url, m_criterion)
                replaceChildText(node, url)
            elif m_type == self.MATCHED_ATTRIBUTE:
                (namespaceURI, localName) = m_match
                url = node.getAttributeNS(namespaceURI, localName)
                url = callback_func(url, m_criterion)
                node.setAttributeNS(namespaceURI, localName, url)
            else:
                raise AssertionError("Unrecognized m_type")

        # Walk through the child nodes.
        for n in node.childNodes:
            if n.nodeType == node.ELEMENT_NODE:
               self.rewrite_links(n, callback_func)

def rewrite_links(node, match_criteria, target_url, base_url, always_absolute=False):
    # We generate a fake URL so links like <a href="/">...</a> will resolve
    # to the top-level URL of the *site* rather than of the *server*.
    fake_base_url = generate_fake_url()
    fake_current_url = rfc3986_urljoin(fake_base_url, target_url)
    real_base_url = base_url
    real_current_url = rebase_url(fake_current_url, fake_base_url, real_base_url)

    def cb(url, criterion):
        # Resolve the link URL with respect to the current (fake) URL
        link_url = rfc3986_urljoin(fake_current_url, url)

        # Convert the fake URL into an absolute real URL
        link_url = rebase_url(link_url, fake_base_url, real_base_url)

        if not always_absolute:
            # Convert the absolute URL into a relative URL
            link_url = relative_url(link_url, real_current_url)

        return link_url

    LinkRewriter(match_criteria).rewrite_links(node, cb)

# vim:set ts=4 sw=4 sts=4 expandtab:
