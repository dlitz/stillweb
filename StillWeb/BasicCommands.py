# -*- coding: utf-8 -*-
# BasicCommands.py - Basic script commands for StillWeb
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

import os

from StillWeb.sw_util import TypicalPaths

class BasicCommandsPlugin:

    def __init__(self, framework):
        self._framework = framework
        self._framework.plugins['StillWeb.ScriptProcessor'].register_command('mkdir', self.handle_mkdir)
        self._framework.plugins['StillWeb.ScriptProcessor'].register_command('symlink', self.handle_symlink)

    def cleanup(self):
        self._framework = None

    def ensure_path(self, root_dir, pathtuple):
        """Make sure root_dir and the specified subdirectory exists (but don't create root_dir's parents)"""
        assert isinstance(root_dir, str)
        assert isinstance(pathtuple, tuple)
        for i in range(len(pathtuple)+1):
            p = os.path.join(root_dir, *pathtuple[:i])
            if not os.path.exists(p):
                print("Creating directory %s" % (p,))
                os.mkdir(p)

    def handle_mkdir(self, target_url):
        """Make a directory if it does not already exist.

        Usage: mkdir TARGET_RELATIVE_URL
        """
        tp = TypicalPaths(self._framework, target_url)

        self.ensure_path(tp.output_dir, tp.pathtuple)

    def handle_symlink(self, target_url):
        """Make a symlink from a file/directory in the source directory to the corresponding location in the destination directory.

        Usage: symlink TARGET_RELATIVE_URL
        """
        if not target_url.startswith("/"):
            raise NotImplementedError("target_url must start with /")

        tp = TypicalPaths(self._framework, target_url)

        # Make sure the parent directory exists
        self.ensure_path(tp.output_dir, tp.pathtuple[:-1])

        print("symlinking %s (to %s)" % (tp.output_filename, tp.source_filename))
        if os.path.islink(tp.output_filename):
            os.unlink(tp.output_filename)
        os.symlink(os.path.realpath(tp.source_filename), tp.output_filename)


def create_plugin(framework):
    return BasicCommandsPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
