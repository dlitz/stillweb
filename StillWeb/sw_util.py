# -*- coding: utf-8 -*-
# sw_util.py - StillWeb utility functions
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

import urllib.parse
import os
import re
import random
import errno

from StillWeb.sw_urllib import rebase_url, rfc3986_urljoin, relative_url

def pathtuple_from_target_url(target_url):
    """Return the corresponding pathtuple for a (relative) target URL

    Leading, trailing, and doubled slashes are ignored.
    """
    return tuple(urllib.parse.unquote(p) for p in target_url.lstrip("/").split("/") if p)

def getChildText(node):
    retval = []
    for n in node.childNodes:
        if n.nodeType in (node.TEXT_NODE, node.CDATA_SECTION_NODE):
            retval.append(n.nodeValue)
    return "".join(retval)

def replaceChildText(node, text):
    retval = []
    for n in tuple(node.childNodes):
        if n.nodeType in (node.TEXT_NODE, node.CDATA_SECTION_NODE):
            node.removeChild(n)
    node.appendChild(node.ownerDocument.createTextNode(text))

def createCDATASectionOrText(document, text):
    if "]]>" in text:
        return document.createTextNode(text)
    else:
        return document.createCDATASection(text)

def getChildElementsNS(node, nsURI, elementName):
    for n in node.childNodes:
        if n.nodeType == n.ELEMENT_NODE and n.namespaceURI == nsURI and n.localName == elementName:
            yield n

def getAttributeNodes(element):
    assert element.nodeType == element.ELEMENT_NODE
    for i in range(element.attributes.length):
        yield element.attributes.item(i)

def generate_fake_url():
    # SECURITY: You might need a stronger source of random numbers if you
    # intend to hide this generated URL.  We don't do that anywhere in
    # StillWeb, currently.
    random_label = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for i in range(28))
    return "http://%s.example.com/" % (random_label,)

def strip_index_from_url(url):
    """Remove the 'index.*' trailer from an URL"""
    (scheme, netloc, path, params, query, fragment) = urllib.parse.urlparse(url)
    path_parts = path.split("/")
    if path_parts and path_parts[-1].startswith("index."):
        path_parts[-1] = ""
        path = "/".join(path_parts)
    return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))

def ensure_path(path):
    """Like os.makedirs, but doesn't complain if a directory already exists."""
    try:
        os.makedirs(path)
    except EnvironmentError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            # Path created successfully.  Be quiet now.
            return
        raise   # Something went wrong, raise the error.

class TypicalPaths:
    """Return an object containing commonly-used paths based on the given framework and target URL

    Currently, this object has the following attributes (some may be missing if they are not available):

    orig_target_url
        The original target URL (passed as input)

    target_url
        The normalized target URL (with "index.*" removed)

    base_url
        The base_url variable.

    current_url
        The target_url joined to the base_url.

    pathtuple
        A tuple representing the parts of the target URL.

        For example, given the relative URL "/foo/bar.html", pathtuple will be ('foo', 'bar.html').

    output_dir
        The output_dir variable.

    output_filename
        The corresponding path in the output directory.  Equivalent to::
            os.path.join(x.output_dir, *x.pathtuple)

    source_dir
        The output_dir variable.  Use the following construct to get the output filename::

    source_filename
        The corresponding path in the source directory.  Equivalent to::
            os.path.join(x.source_dir, *x.pathtuple)

    """
    def __init__(self, framework, orig_target_url):
        if not orig_target_url.startswith("/"):
            raise AssertionError("orig_target_url must start with /")

        self.orig_target_url = orig_target_url
        self.target_url = strip_index_from_url(orig_target_url)
        self.pathtuple = pathtuple_from_target_url(orig_target_url)
        if "output_dir" in framework.plugins['vars'].vars:
            self.output_dir = framework.plugins['vars'].vars['output_dir']
            self.output_filename = os.path.join(self.output_dir, *self.pathtuple)
        if "source_dir" in framework.plugins['vars'].vars:
            self.source_dir = framework.plugins['vars'].vars['source_dir']
            self.source_filename = os.path.join(self.source_dir, *self.pathtuple)

        if "base_url" in framework.plugins['vars'].vars:
            self.base_url = framework.plugins['vars'].vars['base_url']
            self.current_url = rebase_url(self.target_url, generate_fake_url(), self.base_url)


# vim:set ts=4 sw=4 sts=4 expandtab:
