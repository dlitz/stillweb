# -*- coding: utf-8 -*-
# HtAccess.py - StillWeb .htaccess file generator
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

import os
import shutil
import urllib.parse

from StillWeb.sw_util import TypicalPaths

class HtAccessPlugin:
    def __init__(self, framework):
        self._framework = framework
        self._framework.plugins['StillWeb.ScriptProcessor'].register_command('make_htaccess', self.handle_make_htaccess)

    def cleanup(self):
        self._framework = None

    def handle_make_htaccess(self, target_url):
        """Make a .htaccess file, adding a proper RewriteBase to the file

        Usage: make_htaccess TARGET_RELATIVE_URL
        """

        tp = TypicalPaths(self._framework, target_url)

        print("generating htaccess %s (using %s)" % (tp.output_filename, tp.source_filename))

        source_file = open(tp.source_filename, "rt", encoding='UTF-8')

        if os.path.exists(tp.output_filename):
            os.unlink(tp.output_filename)
        output_file = open(tp.output_filename, "wt", encoding='UTF-8')

        shutil.copyfileobj(source_file, output_file)

        # Add RewriteBase line to .htaccess
        output_file.write("\n# Begin automatically-generated section\n")

        # SECURITY FIXME - base_url must not have special characters that will be interpreted weirdly by Apache
        output_file.write("RewriteBase %s\n" % (urllib.parse.urlparse(tp.base_url).path,))

        # Close files
        source_file.close()
        output_file.close()

def create_plugin(framework):
    return HtAccessPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
