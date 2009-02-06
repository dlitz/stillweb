# -*- coding: utf-8 -*-
# NewsPlugin.py - Generate list of articles from an Atom feed
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

import os
import errno
from xml.dom import minidom

from StillWeb.sw_util import TypicalPaths, getChildElementsNS, getChildText
from StillWeb.NamespaceNormalization import normalize_namespaces
from StillWeb.PageGenerator import NeedsUpdate
from StillWeb.FeedGenerator import ATOM_NAMESPACE, atom_datetime_to_utc
from StillWeb.Placeholders import ReplaceWithNode

# XML Namespace for news
NEWS_NAMESPACE = "tag:dlitz.net,2008:StillWeb.NewsPlugin"

class NewsPlugin:
    def __init__(self, framework):
        self._framework = framework
        self._feed_url = None
        self._feed_path_info = None

        pg_plugin = self._framework.plugins['StillWeb.PageGenerator']
        pg_plugin.register_filter('check_freshness', self._check_freshness)

        # Register the placeholder namespace
        ph_plugin = self._framework.plugins['StillWeb.Placeholders']
        ph_plugin.register_callback(self._handle_news_element, NEWS_NAMESPACE, 'news')

        framework.plugins['StillWeb.ScriptProcessor'].register_command('set_news_feed', self.handle_set_news_feed)

    def cleanup(self):
        if self._framework is not None:
            self._framework = None
            self._feed_url = None
            self._feed_path_info = None

    #
    # Commands
    #
    def handle_set_news_feed(self, target_url):
        self._feed_url = target_url
        self._feed_path_info = TypicalPaths(self._framework, target_url)
        print("news feed URL set to %s" % (self._feed_url,))

    #
    # Placeholder callback(s)
    #
    def _handle_news_element(self, page_generator, c_newsElement):
        if self._feed_url is None:
            raise ValueError("news-here element found before set_news_feed called")

        # Find the template element
        (c_templateElement,) = getChildElementsNS(c_newsElement, NEWS_NAMESPACE, 'template')

        # Create the result document
        result_doc = minidom.parseString("<div/>")

        # Load the Atom feed
        feed = minidom.parseString(open(self._feed_path_info.output_filename, "rb").read())

        # Get the content-type of page links
        page_content_type = self._framework.plugins['vars'].vars['page_content_type']

        # Get the maximum number of entries (if any)
        limit = c_newsElement.getAttribute('limit')
        if not limit:
            limit = None
        else:
            limit = int(limit)

        for i, f_entryElement in enumerate(getChildElementsNS(feed.documentElement, ATOM_NAMESPACE, 'entry')):
            # Don't output more than the specified number of articles
            if limit is not None and i >= limit:
                break

            params = {}

            # Get entry title
            (f_titleElement,) = getChildElementsNS(f_entryElement, ATOM_NAMESPACE, 'title')
            assert f_titleElement.getAttribute('type') == 'text'
            params['title'] = getChildText(f_titleElement)

            # Get entry publication/update dates
            params['published'] = getChildText(tuple(getChildElementsNS(f_entryElement, ATOM_NAMESPACE, 'published'))[0])
            params['updated'] = getChildText(tuple(getChildElementsNS(f_entryElement, ATOM_NAMESPACE, 'updated'))[0])

            # Get entry <link rel="alternate" type="text/html">
            ee = getChildElementsNS(f_entryElement, ATOM_NAMESPACE, 'link')
            for e in ee:
                rel = e.getAttribute('rel')
                type = e.getAttribute('type')
                hreflang = e.getAttribute('hreflang')
                if rel == "alternate" and type == page_content_type and not hreflang:
                    params['href'] = e.getAttribute('href')
                    break
            else:
                raise RuntimeError("link not found")

            # Get entry summary
            (f_summaryElement,) = getChildElementsNS(f_entryElement, ATOM_NAMESPACE, 'summary')
            assert f_summaryElement.getAttribute('type') == 'xhtml'
            (f_summaryDiv,) = (n for n in f_summaryElement.childNodes if n.nodeType == n.ELEMENT_NODE)
            params['summaryDiv'] = f_summaryDiv

            # Create per-entry <div> element
            r_divElement = result_doc.createElement('div')
            result_doc.documentElement.appendChild(r_divElement)

            # Copy the template to the result
            self.__copy_template_to_result(c_templateElement, r_divElement, params)

        # Namespace normalization
        normalize_namespaces(result_doc.documentElement)

        # Replace the placeholder
        raise ReplaceWithNode(result_doc.documentElement)

    def __copy_template_to_result(self, src, dest, params):
        for node in src.childNodes:
            if node.nodeType == node.ELEMENT_NODE and node.namespaceURI == NEWS_NAMESPACE:
                if node.localName == 'title-here':
                    new_node = dest.ownerDocument.createTextNode(params['title'])
                elif node.localName == 'summary-here':
                    new_node = dest.ownerDocument.importNode(params['summaryDiv'], deep=True)
                elif node.localName == 'published-here':
                    new_node = dest.ownerDocument.createTextNode(atom_datetime_to_utc(params['published']).replace("T", " ").replace("Z", " UTC")) # HACK FIXME - pretty-print
                elif node.localName == 'updated-here':
                    new_node = dest.ownerDocument.createTextNode(atom_datetime_to_utc(params['updated']).replace("T", " ").replace("Z", " UTC")) # HACK FIXME - pretty-print
                elif node.localName == 'a':
                    new_node = dest.ownerDocument.createElement('a')

                    # Import attributes (SECURITY: This is perhaps too liberal)
                    for i in range(node.attributes.length):
                        attrNode = node.attributes.item(i)
                        new_node.setAttributeNode(dest.ownerDocument.importNode(attrNode, deep=True))

                    new_node.setAttribute('href', params['href'])
                else:
                    raise ValueError("Illegal element name: %r" % (node.tagName,))
            else:
                new_node = dest.ownerDocument.importNode(node, deep=False)
            dest.appendChild(new_node)

            # Recurse
            if node.nodeType == node.ELEMENT_NODE:
                self.__copy_template_to_result(node, new_node, params)

    #
    # Filter callbacks
    #
    def _check_freshness(self, page_generator):
        if self._feed_url is None:
            return

        try:
            feed_mtime = os.lstat(self._feed_path_info.output_filename).st_mtime
            output_mtime = os.lstat(page_generator.path_info.output_filename).st_mtime
        except EnvironmentError as exc:
            if exc.errno != errno.ENOENT:
                raise
            # If one of the files we're looking for doesn't exist, then they need to be updated.
            raise NeedsUpdate

        if feed_mtime > output_mtime:
            raise NeedsUpdate


def create_plugin(framework):
    return NewsPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
