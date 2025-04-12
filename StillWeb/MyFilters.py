# -*- coding: utf-8 -*-
# MyFilters.py - My PageGenerator filters
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

from xml.dom import EMPTY_NAMESPACE

from StillWeb.sw_util import getChildText, getChildElementsNS
from StillWeb.LinkRewriter import HTML_CRITERIA, rewrite_links

#
# Plugin interface
#
class MyFiltersPlugin:
    def __init__(self, framework):
        self._framework = framework

        pg_plugin = self._framework.plugins['StillWeb.PageGenerator']
        pg_plugin.register_filter('generate_page', _filter_set_title)
        pg_plugin.register_filter('generate_page', _filter_copy_head)
        pg_plugin.register_filter('generate_page', _filter_copy_body)
        pg_plugin.register_filter('generate_page', _filter_copy_onload)
        pg_plugin.register_filter('generate_page', _filter_rewrite_links)

    def cleanup(self):
        self._framework = None

def create_plugin(framework):
    return MyFiltersPlugin(framework)

#
# Filter to copy page title from pg.content -> pg.page
#
def _filter_set_title(pg):
    # Extract title text from pg.content
    (head_element,) = getChildElementsNS(pg.content.documentElement, EMPTY_NAMESPACE, 'head')
    (title_element,) = getChildElementsNS(head_element, EMPTY_NAMESPACE, 'title')
    title_text = getChildText(title_element)

    # Replace children of <title> element in pg.title
    (title_element,) = pg.page.getElementsByTagName('title')
    for n in title_element.childNodes:
        title_element.removeChild(n)
    title_element.appendChild(pg.page.createTextNode(title_text))

#
# Populate <head> element
#
def _filter_copy_head(pg):
    # Find <head> elements of both pages
    (srcHeadElement,) = pg.content.getElementsByTagName('head')
    (destHeadElement,) = pg.page.getElementsByTagName('head')

    # Import <head> element from pg.content into pg.page's DOM (but don't add
    # it to the document tree just yet).
    tmpHeadElement = pg.page.importNode(srcHeadElement, True)

    # Remove <title>, since it's handled elsewhere.
    (n,) = getChildElementsNS(tmpHeadElement, EMPTY_NAMESPACE, 'title')
    if n:
        n.parentNode.removeChild(n)

    # Remove other items from <head>
    pg.invoke_filters('generate_page:filter_head', tmpHeadElement)

    # Copy the remaining nodes
    for n in tmpHeadElement.childNodes:
        destHeadElement.appendChild(n)

#
# Populate <div id="PageContent"> element
#
def _filter_copy_body(pg):
    (srcBodyElement,) = pg.content.getElementsByTagName('body')
    (destBodyElement,) = pg.page.getElementsByTagName('body')

    for destDivElement in destBodyElement.getElementsByTagName("div"):
        if destDivElement.getAttribute('id') != "PageContent":
            continue

        # Clear out the existing <div id="PageContent"> element
        for n in destDivElement.childNodes:
            destDivElement.removeChild(n)

        # Populate the <div id="PageContent"> element
        for n in srcBodyElement.childNodes:
            destDivElement.appendChild(pg.page.importNode(n, True))

        # There is only one <div id="PageContent"> element
        break
    else:
        raise ValueError('<div id="PageContent"> not found')

#
# Populate onload="" for JavaScript
#
def _filter_copy_onload(pg):
    (srcBodyElement,) = pg.content.getElementsByTagName('body')
    (destBodyElement,) = pg.page.getElementsByTagName('body')

    # HACK - just copy the onload attribute from pg.content -> pg.page
    onload = srcBodyElement.getAttribute('onload')
    if onload:
        destBodyElement.setAttribute('onload', onload)

#
# Do link rewriting
#
def _filter_rewrite_links(pg):
    rewrite_links(pg.page, HTML_CRITERIA,
        target_url=pg.path_info.target_url,
        base_url=pg.path_info.base_url)

# vim:set ts=4 sw=4 sts=4 expandtab:
