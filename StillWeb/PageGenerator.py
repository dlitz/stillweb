# -*- coding: utf-8 -*-
# PageGenerator.py - HTML page generator
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

import os
import errno
from xml.dom import minidom, XHTML_NAMESPACE, EMPTY_NAMESPACE

from StillWeb.TagSoupToXml import TagSoupToXml
from StillWeb.sw_util import TypicalPaths
from StillWeb.NamespaceNormalization import substitute_namespaces, normalize_namespaces

class NeedsUpdate(Exception):
    """Raised by a 'check_freshness' filter when a page needs to be re-generated."""

class PageGenerator:
    # NB: This is not the PageGeneratorPlugin.  A new PageGenerator is
    # instantiated every time the script command 'make' is invoked.

    def __init__(self, path_info, template_filename):
        self.path_info = path_info
        self.template_filename = template_filename
        self._filters = {
            'check_freshness': [],
            'init_page:before': [],
            'init_page:after': [],
            'load_content:before': [],
            'load_content:after': [],
            'generate_page:before': [],
            'generate_page': [],
            'generate_page:filter_head': [],
            'generate_page:after': [],
            'generate_output:before': [],
            'generate_output:after': [],
            'write_output:before': [],
            'write_output:after': [],
        }
        self.output = None

    def cleanup(self):
        self.path_info = None
        self.page = None
        self.content = None
        self._filters = None
        self.output = None

    #
    # Exported API
    #

    def register_filter(self, stage, callback):
        self._filters[stage].append(callback)

    def invoke_filters(self, stage, *args, **kwargs):
        for callback in self._filters[stage]:
            callback(self, *args, **kwargs)

    def check_freshness(self):
        template_mtime = os.stat(self.template_filename).st_mtime
        source_mtime = os.stat(self.path_info.source_filename).st_mtime
        try:
            output_mtime = os.lstat(self.path_info.output_filename).st_mtime
        except EnvironmentError as exc:
            if exc.errno == errno.ENOENT:
                raise NeedsUpdate
            else:
                raise
        if max([template_mtime, source_mtime, output_mtime]) != output_mtime:
            raise NeedsUpdate

        self.invoke_filters('check_freshness')

    def init_page(self):
        self.invoke_filters('init_page:before')

        # The page starts as a template, which we modify until it's suitable for output.
        self.page = minidom.parse(self.template_filename)

        self.invoke_filters('init_page:after')

    def load_content(self):
        self.invoke_filters('load_content:before')

        # Convert HTML tag soup to XML
        p = TagSoupToXml(omit_comments=True)  # Omit commented-out parts in the final output
        p.feed(open(self.path_info.source_filename, "rt", encoding="UTF-8").read())   # TODO: support other encodings? (is that safe?)
        p.close()

        # Return a DOM URL
        self.content = p.todocument()

        # Drop any "http://www.w3.org/1999/xhtml" namespace declarations
        substitute_namespaces(self.content.documentElement, {XHTML_NAMESPACE: EMPTY_NAMESPACE})
        normalize_namespaces(self.content.documentElement, strip_dups=True)

        self.invoke_filters('load_content:after')

    def generate_page(self):
        self.invoke_filters('generate_page:before')
        self.invoke_filters('generate_page')
        self.invoke_filters('generate_page:after')

    def generate_output(self):
        self.invoke_filters('generate_output:before')

        self.output = self.page.doctype.toxml('UTF-8') + self.page.documentElement.toxml('UTF-8')

        self.invoke_filters('generate_output:after')

    def write_output(self):
        self.invoke_filters('write_output:before')

        if os.path.exists(self.path_info.output_filename):
            os.unlink(self.path_info.output_filename)
        f = open(self.path_info.output_filename, "wb")
        f.write(self.output)
        f.close()

        self.invoke_filters('write_output:after')


class PageGeneratorPlugin:

    def __init__(self, framework):
        self._framework = framework
        self._framework.plugins['StillWeb.ScriptProcessor'].register_command('make', self.handle_make)
        self._filters = []

    def cleanup(self):
        self._framework = None
        self._filters = None

    #
    # Exported API
    #
    def register_filter(self, stage, callback):
        self._filters.append((stage, callback))

    #
    # Commands
    #

    def handle_make(self, target_url):
        tp = TypicalPaths(self._framework, target_url)
        template_filename = self._framework.plugins['vars'].vars['template']

        # Create the PageGenerator instance for this page
        pg = PageGenerator(tp, template_filename)

        try:
            # Register filters
            for (stage, callback) in self._filters:
                pg.register_filter(stage, callback)

            # Check if the page needs to be built
            try:
                pg.check_freshness()
            except NeedsUpdate:
                pass
            else:
                print("skipping %s" % (tp.output_filename,))
                return

            # Make sure the directory exists
            self._framework.plugins['StillWeb.BasicCommands'].ensure_path(tp.output_dir, tp.pathtuple[:-1])

            print("making %s (using %s)" % (tp.output_filename, tp.source_filename))

            # Load the template and content
            pg.init_page()
            pg.load_content()

            # Generate the page
            pg.generate_page()

            # Generate the output
            pg.generate_output()

            # Write the output file
            pg.write_output()

        finally:
            pg.cleanup()


def create_plugin(framework):
    return PageGeneratorPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
