# -*- coding: utf-8 -*-
# FeedGenerator.py - StillWeb Atom feed generator
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

import os
import fnmatch
import errno
import re
import datetime
import shutil
import base64
import urllib.parse
import pickle

from xml.dom import minidom, XMLNS_NAMESPACE, XHTML_NAMESPACE, EMPTY_NAMESPACE

from StillWeb.sw_util import getChildText, replaceChildText, TypicalPaths, createCDATASectionOrText, getChildElementsNS, ensure_path
from StillWeb.LinkRewriter import rewrite_links, HTML_CRITERIA
from StillWeb.PageGenerator import NeedsUpdate
from StillWeb.NamespaceNormalization import normalize_namespaces, substitute_namespaces

# XML namespace and content type for Atom 1.0 (RFC 4287) documents
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
ATOM_CONTENT_TYPE = "application/atom+xml"

# rewrite_links criteria for Atom 1.0 documents
ATOM_CRITERIA = [
    ((ATOM_NAMESPACE, "category"),     (None, "scheme")),
    ((ATOM_NAMESPACE, "content"),      (None, "src")),
    ((ATOM_NAMESPACE, "generator"),    (None, "uri")),
    ((ATOM_NAMESPACE, "icon"),         None),
    ((ATOM_NAMESPACE, "link"),         (None, "href")),
    ((ATOM_NAMESPACE, "logo"),         None),
    ((ATOM_NAMESPACE, "uri"),          None),
]


class FeedGeneratorError(Exception):
    pass

class FGValueError(ValueError, FeedGeneratorError):
    pass

_atom_datetime_regex = re.compile(r"^(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.\d+)?(Z|[+-]\d\d:\d\d)$")
def atom_datetime_to_utc(s):
    """Perform syntax checking on an Atom 1.0 datetime and return a datetime that can be used in a string sort."""
    m = _atom_datetime_regex.search(s)
    if not m:
        raise ValueError("Invalid RFC 4287 (Atom) datetime")
    (year, month, day, hour, minute, second) = (int(x) for x in m.groups()[:6])
    (fraction, zone) = m.groups()[6:]
    if fraction:
        microsecond = int(round(1e6*float(fraction)))
    else:
        microsecond = 0
    if zone == "Z":
        return s

    # Convert to UTC
    local_time = datetime.datetime(year, month, day, hour, minute, second, microsecond)
    (offset_h, offset_m) = zone[1:].split(":")
    if zone.startswith("-"):
        offset_h = -int(offset_h)
        offset_m = int(offset_m)
    else:
        offset_h = int(offset_h)
        offset_m = int(offset_m)
    offset = datetime.timedelta(hours=offset_h, minutes=offset_m)
    ut = local_time - offset

    retval = ut.isoformat() + "Z"
    assert _atom_datetime_regex.search(retval)
    return retval

def atom_datetime_to_sort_key(s):
    """Given an Atom date-time string, return a key suitable for sorting on."""
    # Return ("date", "time", fractional)
    dt = atom_datetime_to_utc(s)
    assert dt.endswith("Z")
    dt = dt[:-1]
    (date, extra) = dt.split("T", 1)
    tt = extra.split(".", 1)
    if len(tt) == 1:
        (time,) = tt
        microsecond = 0
    else:
        (time, fractional) = tt
        microsecond = int(round(1e6 * float("." + fractional)))
    return (date, time, microsecond)

def find_elements_with_class(node, className, remove=False):
    """Return an iterator that generates a list of elements with the given class.

    If `remove` is set, the class will be removed when found.
    """

    # If we are passed a DOMDocument, use the top-level element instead.
    if node.nodeType == node.DOCUMENT_NODE:
        node = node.documentElement

    assert node.nodeType == node.ELEMENT_NODE
    class_attr = node.getAttributeNode('class')
    if class_attr:
        c = class_attr.nodeValue.split(" ")
        if className in c:
            if remove:
                # Remove class="feed-summary"
                c.remove(className)
                if c:
                    class_attr.nodeValue = " ".join(c)
                else:
                    node.removeAttributeNode(class_attr)
            yield node

    # Recurse
    for n in node.childNodes:
        if n.nodeType == n.ELEMENT_NODE:
            for result in find_elements_with_class(n, className, remove):
                yield result


class FeedGeneratorPlugin:

    def __init__(self, framework):
        self._framework = framework

        pg_plugin = self._framework.plugins['StillWeb.PageGenerator']
        pg_plugin.register_filter('check_freshness', self._check_freshness)
        pg_plugin.register_filter('load_content:after', self._load_content)
        pg_plugin.register_filter('generate_page:filter_head', self._filter_head)
        pg_plugin.register_filter('write_output:after', self._write_output)

        framework.plugins['StillWeb.ScriptProcessor'].register_command('make_atom_feed', self.handle_make_atom_feed)

    def cleanup(self):
        if self._framework is not None:
            self._framework = None

    #
    # Command
    #
    def handle_make_atom_feed(self, target_url):
        """Write the data we've collected so far as an Atom feed

        Usage: make-atom-feed TARGET_RELATIVE_URL
        """

        tp = TypicalPaths(self._framework, target_url)
        data_dir = self._get_feed_data_dir()

        def is_update_needed():
            # Check if the feed needs to be updated
            try:
                output_mtime = os.lstat(tp.output_filename).st_mtime
            except EnvironmentError as exc:
                if exc.errno != errno.ENOENT:
                    raise
                # The output file doesn't exist, so an update is needed
                return True

            # Output file exists.  Check timestamps.
            source_mtime = os.lstat(tp.source_filename).st_mtime
            if output_mtime < source_mtime:
                # The source file was modified, so an update is needed.
                return True

            for basename in fnmatch.filter(os.listdir(data_dir), "entry-*-stamp"):
                entry_mtime = os.lstat(os.path.join(data_dir, basename)).st_mtime
                if output_mtime < entry_mtime:
                    # one of the entries is newer than the output file, so an update is needed
                    return True

            return False

        if not is_update_needed():
            # No update needed
            print("skipping %s" % (tp.output_filename,))
            return

        # Make sure the output directory exists
        self._framework.plugins['StillWeb.BasicCommands'].ensure_path(tp.output_dir, tp.pathtuple[:-1])

        print("making %s (using %s)" % (tp.output_filename, tp.source_filename))

        # Load the entries
        entries = []
        regex = re.compile(r"^entry-([^-.]*)-stamp$")
        for basename in os.listdir(data_dir):
            m = regex.search(basename)
            if not m:
                continue
            rootword = m.group(1)
            filename = os.path.join(data_dir, "entry-%s-data" % (rootword,))
            try:
                f = open(filename, "rb")
                entry = pickle.load(f)
                f.close()
            except EnvironmentError as exc:
                if exc.errno == errno.ENOENT:
                    continue
                else:
                    raise
            entries.append(entry)

        # Check for duplicate ids
        ids = {}
        for entry in entries:
            if entry['id'] in ids:
                raise FGValueError("Duplicate id %r in %s (already defined in %s)" % (entry['id'], entry['path_info'].source_filename, ids[entry['id']]))
            ids[entry['id']] = entry['path_info'].source_filename

        # Skip entries whose publication dates are in the future
        unpublished_entries = []
        now = atom_datetime_to_utc(datetime.datetime.utcnow().isoformat() + "Z")
        for i, entry in enumerate(entries):
            if entry['published'] > now:
                unpublished_entries.append(i)
        for i in reversed(unpublished_entries):
            print("%s: skipping %s ('published' in the future)" % (tp.output_filename, entry['path_info'].output_filename,))
            del entries[i]

        # Sort the entries by their publication date, newest first.
        entries.sort(key=lambda entry: atom_datetime_to_sort_key(entry['published']), reverse=True)

        # Find the most recent update
        if not entries:
            raise FGValueError("Refusing to make empty feed")
        most_recent_update = entries[0]['updated']

        # Load and parse the template file
        feedDocument = minidom.parseString(open(tp.source_filename, "rb").read())
        feedElement = feedDocument.documentElement
        assert (feedElement.namespaceURI, feedElement.localName) == (ATOM_NAMESPACE, "feed")

        # Set <updated> to the newest entry's <updated> (or <published>) field
        if tuple(getChildElementsNS(feedDocument, ATOM_NAMESPACE, "updated")):
            raise FGValueError("Template contains auto-generated <updated> field")
        updatedElement = feedDocument.createElementNS(ATOM_NAMESPACE, 'updated')
        feedElement.appendChild(updatedElement)
        replaceChildText(updatedElement, most_recent_update)

        # Create a <link rel="self"> element if one does not already exist.
        for linkElement in getChildElementsNS(feedElement, ATOM_NAMESPACE, "link"):
            if linkElement.getAttribute('rel') == 'self':
                break
        else:
            linkElement = feedDocument.createElementNS(ATOM_NAMESPACE, 'link')
            linkElement.setAttribute('rel', 'self')
            linkElement.setAttribute('type', ATOM_CONTENT_TYPE)
            linkElement.setAttribute('href', tp.target_url)
            feedElement.appendChild(linkElement)

        # Do URL path substitution
        rewrite_links(feedElement, ATOM_CRITERIA, tp.target_url, tp.base_url, always_absolute=True)

        # Add the entries
        for entry in entries:
            # Create an <entry> element
            entryElement = feedDocument.importNode(minidom.parseString(entry['atom:entry']).documentElement, True)
            assert (entryElement.namespaceURI, entryElement.localName) == (ATOM_NAMESPACE, 'entry')
            feedElement.appendChild(entryElement)


        # Write the feed to the output file
        if os.path.exists(tp.output_filename):
            os.unlink(tp.output_filename)
        output_file = open(tp.output_filename, "wb")
        try:
            output_file.write(feedDocument.toxml("UTF-8"))
        except:
            os.unlink(tp.output_filename)
            raise
        finally:
            output_file.close()

    #
    # Filter callbacks
    #

    def _check_freshness(self, page_generator):
        stamp_mtime = self._get_entry_timestamp(page_generator)
        try:
            html_output_mtime = os.lstat(page_generator.path_info.output_filename).st_mtime
        except EnvironmentError as exc:
            if exc.errno != errno.ENOENT:
                raise
            # If one of the files we're looking for doesn't exist, then they need to be updated.
            raise NeedsUpdate

        # Check if the entry's timestamp file is up-to-date.  If it's missing
        # or older than the HTML output, then it needs to be updated.
        if stamp_mtime is None or html_output_mtime > stamp_mtime:
            raise NeedsUpdate

    def _load_content(self, page_generator):
        content = page_generator.content

        # Initialize the current entry
        current_entry = {}

        # Find the <head> and <body> elements.
        (headElement,) = page_generator.content.getElementsByTagName('head')
        (bodyElement,) = page_generator.content.getElementsByTagName('body')

        # Find the <atom:entry> element inside the <head> element.
        entries = headElement.getElementsByTagNameNS(ATOM_NAMESPACE, 'entry')
        if not entries:
            # No Atom feed entry.  Do nothing.
            self._clear_entry_data(page_generator)
            return
        elif len(entries) > 1:
            # There should only be one atom:entry
            raise FGValueError("Too many Atom entries in %s" % (page_generator.path_info.source_filename,))
        (entryElement,) = entries

        # Store the <atom:entry> element (with all namespace information included)
        dummyDocument = minidom.parseString('<dummy/>')
        new_entryElement = dummyDocument.importNode(entryElement, True)
        dummyDocument.documentElement.appendChild(new_entryElement)
        normalize_namespaces(new_entryElement)
        current_entry['atom:entry'] = new_entryElement.toxml()

        # Find and store the page summary (if any) in the <body> element, and un-set class="feed-summary".
        summaryElements = list(find_elements_with_class(content, "feed-summary", remove=True))
        if len(summaryElements) > 1:
            # There should only be one element with class="feed-summary"
            raise FGValueError('Too many elements have class="feed-summary" in %s' % (page_generator.path_info.source_filename,))
        elif summaryElements:
            # Save the summary
            current_entry['summary'] = summaryElements[0].toxml()
        else:
            # Save an empty summary
            current_entry['summary'] = None

        # Save the page body
        current_entry['body'] = bodyElement.toxml()

        # Save the page title
        (titleElement,) = getChildElementsNS(headElement, EMPTY_NAMESPACE, 'title')
        current_entry['title'] = getChildText(titleElement)

        # Save the path_info
        current_entry['path_info'] = page_generator.path_info

        # Perform some early processing
        self._early_process_entry(page_generator, current_entry)

        # Write the entry to disk
        self._write_entry_data(page_generator, current_entry)

    def _filter_head(self, page_generator, headElement):
        # Remove the <atom:entry> element from the <head> element
        for entryElement in headElement.getElementsByTagNameNS(ATOM_NAMESPACE, 'entry'):
            entryElement.parentNode.removeChild(entryElement)

    def _write_output(self, page_generator):
        self._update_entry_timestamp(page_generator)

    #
    # Internal functions
    #
    def _get_feed_data_dir(self):
        d = os.path.join(self._framework.plugins['vars'].vars['intermediate_data_dir'], "StillWeb.FeedGenerator")

        # Quietly make sure the directory exists
        ensure_path(d)

        return d

    def _get_entry_rootword(self, page_generator):
        """Return the 'root word' of the current entry in the feed_data_dir"""
        return urllib.parse.quote(page_generator.path_info.orig_target_url, safe='').replace(".", "%2E").replace("-", "%2D")

    def _get_entry_timestamp(self, page_generator):
        stamp_filename = os.path.join(self._get_feed_data_dir(), "entry-%s-stamp" % (self._get_entry_rootword(page_generator),))
        try:
            return os.lstat(stamp_filename).st_mtime
        except EnvironmentError as exc:
            if exc.errno != errno.ENOENT:
                raise
            return None

    def _update_entry_timestamp(self, page_generator):
        # Make sure the data directory exists
        feed_data_dir = self._get_feed_data_dir()

        # Touch the timestamp file
        stamp_filename = os.path.join(feed_data_dir, "entry-%s-stamp" % (self._get_entry_rootword(page_generator),))
        open(stamp_filename, "ab").close()
        os.utime(stamp_filename, None)

    def _clear_entry_data(self, page_generator):
        # Remove any existing entry data (needed if we remove an atom:entry element from a document)
        feed_data_dir = self._get_feed_data_dir()
        prefix = "entry-%s-" % (self._get_entry_rootword(page_generator),)
        try:
            listing = os.listdir(feed_data_dir)
        except EnvironmentError as exc:
            if exc.errno == errno.ENOENT:
                pass
            else:
                raise
        else:
            for basename in listing:
                if basename.startswith(prefix):
                    os.unlink(os.path.join(feed_data_dir, basename))

    def _write_entry_data(self, page_generator, data):
        feed_data_dir = self._get_feed_data_dir()
        filename = os.path.join(feed_data_dir, "entry-%s-data" % (self._get_entry_rootword(page_generator),))
        f = open(filename, "wb")
        pickle.dump(data, f)
        f.close()

    def _early_process_entry(self, page_generator, entry):
        """Perform early in-place processing of an entry."""

        entryDocument = minidom.parseString(entry['atom:entry'])
        entryElement = entryDocument.documentElement
        page_content_type = self._framework.plugins['vars'].vars['page_content_type']

        # Extract the 'id' of the entry
        (idElement,) = getChildElementsNS(entryElement, ATOM_NAMESPACE, 'id')
        entry['id'] = getChildText(idElement).strip()

        # Extract and normalize the 'published' date of the entry
        (publishedElement,) = getChildElementsNS(entryElement, ATOM_NAMESPACE, 'published')
        entry['published'] = atom_datetime_to_utc(getChildText(publishedElement).strip())

        # Extract and normalize the 'updated' date of the entry; Create it if it doesn't exist.
        ee = tuple(getChildElementsNS(entryElement, ATOM_NAMESPACE, 'updated'))
        if ee:
            (updatedElement,) = ee  # there should be only one
        else:
            # Create an <updated> element using the 'published' date
            updatedElement = entryDocument.createElementNS(ATOM_NAMESPACE, 'updated')
            replaceChildText(updatedElement, entry['published'])
            entryElement.appendChild(updatedElement)
        entry['updated'] = atom_datetime_to_utc(getChildText(updatedElement).strip())

        # Create a <title> element if one does not already exist.
        ee = tuple(getChildElementsNS(entryElement, ATOM_NAMESPACE, 'title'))
        if not ee:
            titleElement = entryDocument.createElementNS(ATOM_NAMESPACE, 'title')
            titleElement.setAttribute('type', 'text')
            titleElement.appendChild(entryDocument.createTextNode(entry['title']))
            entryElement.appendChild(titleElement)

        # Create a <link rel="alternate"> element if one does not already exist.
        ee = getChildElementsNS(entryElement, ATOM_NAMESPACE, 'link')
        linkElement = None
        for e in ee:
            rel = e.getAttribute('rel')
            type = e.getAttribute('type')
            hreflang = e.getAttribute('hreflang')
            if rel == "alternate" and type == page_content_type and not hreflang:
                if linkElement is not None:
                    raise FGValueError('Conflicting <link rel="alternate" type=%r hreflang=%r> entries in %s' % (
                        page_content_type, hreflang, page_generator.path_info.source_filename,))
                linkElement = e
        if not linkElement:
            linkElement = entryDocument.createElementNS(ATOM_NAMESPACE, 'link')
            linkElement.setAttribute('rel', 'alternate')
            linkElement.setAttribute('href', page_generator.path_info.target_url)
            linkElement.setAttribute('type', page_content_type)
            entryElement.appendChild(linkElement)

        # Rewrite URLs in the atom:entry element
        rewrite_links(entryElement, ATOM_CRITERIA, page_generator.path_info.target_url, page_generator.path_info.base_url, always_absolute=True)

        # Add a <summary> element, if applicable
        if entry['summary']:
            summaryDocument = minidom.parseString(entry['summary'])

            # Rewrite URLs in the summary
            rewrite_links(summaryDocument.documentElement, HTML_CRITERIA,
                entry['path_info'].target_url, entry['path_info'].base_url, always_absolute=True)

            # Create Atom <summary> element
            summaryElement = entryElement.ownerDocument.createElementNS(ATOM_NAMESPACE, 'summary')
            summaryElement.setAttribute('type', 'xhtml')
            entryElement.appendChild(summaryElement)

            # Create XHTML <div> element
            divElement = entryElement.ownerDocument.createElementNS(XHTML_NAMESPACE, 'div')
            divElement.setAttributeNS(XMLNS_NAMESPACE, 'xmlns', XHTML_NAMESPACE)
            summaryElement.appendChild(divElement)

            # Add data
            for n in summaryDocument.documentElement.childNodes:
                divElement.appendChild(divElement.ownerDocument.importNode(n, True))

            # Elements with no namespace become XHTML elements
            substitute_namespaces(divElement, {EMPTY_NAMESPACE: XHTML_NAMESPACE})

            # Clean up
            data = None
            summaryDocument.unlink()
            summaryDocument = None
            del entry['summary']

        # Add a <content> element
        if True:
            bodyDocument = minidom.parseString(entry['body'])

            # Rewrite URLs in the body
            rewrite_links(bodyDocument.documentElement, HTML_CRITERIA,
                entry['path_info'].target_url, entry['path_info'].base_url, always_absolute=True)

            # Create Atom <content> element
            contentElement = entryElement.ownerDocument.createElementNS(ATOM_NAMESPACE, 'content')
            contentElement.setAttribute('type', 'xhtml')
            entryElement.appendChild(contentElement)

            # Create XHTML <div> element
            divElement = entryElement.ownerDocument.createElementNS(XHTML_NAMESPACE, 'div')
            divElement.setAttributeNS(XMLNS_NAMESPACE, 'xmlns', XHTML_NAMESPACE)
            contentElement.appendChild(divElement)

            # Add data
            for n in bodyDocument.documentElement.childNodes:
                divElement.appendChild(divElement.ownerDocument.importNode(n, True))

            # Elements with no namespace become XHTML elements
            substitute_namespaces(divElement, {EMPTY_NAMESPACE: XHTML_NAMESPACE})

            # Clean up
            data = None
            bodyDocument.unlink()
            bodyDocument = None
            del entry['body']

        # Perform xmlns normalization
        normalize_namespaces(entryDocument.documentElement, strip_dups=True)

        # Update the new atom:entry document
        entry['atom:entry'] = entryDocument.toxml()

def create_plugin(framework):
    return FeedGeneratorPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
