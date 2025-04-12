# -*- coding: utf-8 -*-
# Placeholders.py - Placeholder-plugin support
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

from xml.dom import minidom, EMPTY_NAMESPACE, XHTML_NAMESPACE

from StillWeb.TagSoupToXml import TagSoupToXml
from StillWeb.NamespaceNormalization import substitute_namespaces, normalize_namespaces

# NOTE: Only plugins that are part of StillWeb itself should use this
# namespace. Other plugins (or plugin authors) should define their own
# namespaces.
# NOTE ALSO: "tag:" URIs have well-defined syntax and semantics.  See RFC 4151
# or http://www.taguri.org/ for information about generating them.
PLACEHOLDERS_NAMESPACE = "tag:dlitz.net,2008:StillWeb.Placeholders"

# The following elements are defined under the PLACEHOLDERS_NAMESPACE:
#   <p:math>    LaTeX math expression (see StillWeb.TeXPlugin)
#   <p:m>       Synonym for <p:math>  (see StillWeb.TeXPlugin)
#   <p:maxima>  GNU Maxima expression (see StillWeb.MaximaPlugin)

class BaseReplaceException(Exception):
    pass

class ReplaceWithNothing(BaseReplaceException):
    """raise ReplaceWithNothing() from inside a placeholder
    callback to cause the placeholder element to be removed from the page.
    """

class ReplaceWithText(BaseReplaceException):
    """raise ReplaceWithText(text) from inside a placeholder callback to
    replace the placeholder element with the specified text."""
    def __init__(self, text):
        super().__init__(text)
        if not isinstance(text, str):
            raise TypeError("text must be a string, not %r" % (type(text),))
        self.text = text

class ReplaceWithNode(BaseReplaceException):
    """raise ReplaceWithNode(xml_dom_node) from inside a placeholder callback to
    replace the placeholder element with the specified DOM node.  If the node
    is not owned by the current document, it will be imported using importNode.

    XHTML_NAMESPACE and EMPTY_NAMESPACE will be fixed unless fix_namespaces is false.
    """
    def __init__(self, node, fix_namespaces=True):
        super().__init__(node)
        if not hasattr(node, 'nodeType'):
            raise TypeError("node must be a XML DOM node, not %r" % (type(node),))
        self.node = node
        self.fix_namespaces = fix_namespaces

class ReplaceWithHTML(BaseReplaceException):
    """raise ReplaceWithHTML(html) from inside a placeholder callback to
    replace the placeholder element with the specified html code.

    The Placeholders plugin will run the HTML through TagSoupToXml first.
    """
    def __init__(self, html, omit_comments=True):
        if not isinstance(html, str):
            raise TypeError("html must be a string, not %r" % (type(text),))
        super().__init__()
        self.html = html
        self.omit_comments = omit_comments

class PlaceholdersPlugin:
    def __init__(self, framework):
        self._framework = framework
        self._namespace_callbacks = {}
        self._element_callbacks = {}

        # Register the placeholder namespace
        pg_plugin = self._framework.plugins['StillWeb.PageGenerator']
        pg_plugin.register_filter('load_content:after', self._process_placeholders)

    def cleanup(self):
        if self._framework is not None:
            self._framework = None
            self._namespace_callbacks = None
            self._element_callbacks = None

    #
    # Exported API
    #
    def register_callback(self, callback, element_namespaceURI, element_localName=None):
        """Register a callback function associated with the specified element.

        If element_localName is unspecified, then this callback function is
        associated with _any_ element with the specified namespaceURI.

        When a callback function is invoked, it is passed the current
        PageGenerator instance and the matching DOM Element node.
        """
        if element_localName is not None:
            k = (element_namespaceURI, element_localName)
            if k in self._element_callbacks:
                raise ValueError("callback already assigned for element %r" % (k,))
            self._element_callbacks[k] = callback
        else:
            if element_namespaceURI in self._namespace_callbacks:
                raise ValueError("callback already assigned for namespace %r" % (element_namespaceURI,))
            self._namespace_callbacks[namespaceURI] = namespaceURI

    #
    # Filter callback(s)
    #
    def _process_placeholders(self, page_generator):
        self.__recurse_placeholders(page_generator, page_generator.content.documentElement)

    def __recurse_placeholders(self, page_generator, element):
        # Try element-specific callback
        callback = self._element_callbacks.get((element.namespaceURI, element.localName))
        if callback is not None:
            return self.__invoke_callback(page_generator, element, callback)

        # Try (wildcard) namespace callback
        callback = self._namespace_callbacks.get(element.namespaceURI)
        if callback is not None:
            return self.__invoke_callback(page_generator, element, callback)

        # Fall back: Recurse into child nodes
        for node in element.childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                self.__recurse_placeholders(page_generator, node)

    def __invoke_callback(self, page_generator, element, callback):
        try:
            callback(page_generator, element)
        except ReplaceWithNothing as exc:
            # Remove the element
            element.parentNode.removeChild(element)
        except ReplaceWithText as exc:
            # Replace the element with the given text
            text_node = element.ownerDocument.createTextNode(exc.text)
            element.parentNode.replaceChild(text_node, element)
        except ReplaceWithNode as exc:
            # Replace the element with the given node
            new_node = exc.node
            if new_node.ownerDocument is not element.ownerDocument:
                new_node = element.ownerDocument.importNode(new_node, True)
            element.parentNode.replaceChild(new_node, element)
            if exc.fix_namespaces:
                # page_generator.content uses HTML without specifying a namespace
                substitute_namespaces(new_node, {XHTML_NAMESPACE: EMPTY_NAMESPACE})
                normalize_namespaces(new_node, strip_dups=True)
        except ReplaceWithHTML as exc:
            #
            # Replace the element with the given HTML code
            #

            # Parse with TagSoupToXml
            p = TagSoupToXml(omit_comments=exc.omit_comments)
            p.feed(exc.html)
            p.close()

            # Get a DOM document
            doc = p.todocument()

            # Find the <body> element
            for node in doc.documentElement.childNodes:
                if node.nodeType != node.ELEMENT_NODE:
                    continue
                if node.localName == 'body':
                    bodyElement = node
                    break
            else:
                raise AssertionError("<body> element not found")

            # At this stage, HTML code doesn't have a namespace assigned yet.
            assert bodyElement.namespaceURI == EMPTY_NAMESPACE

            # Replace the placeholder element with the children of the <body> node.
            for node in bodyElement.childNodes:
                new_node = element.ownerDocument.importNode(node, True)
                element.parentNode.insertBefore(new_node, element)
            element.parentNode.removeChild(element)


def create_plugin(framework):
    return PlaceholdersPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
