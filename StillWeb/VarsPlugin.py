# -*- coding: utf-8 -*-
# VarsPlugin.py - StillWeb 'vars' plugin
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

class VarsPlugin:

    def __init__(self, framework):
        self.__framework = framework

        self.vars = {}  # Part of the exported API

        framework.plugins['StillWeb.ScriptProcessor'].register_command('set', self.handle_set_command)

    def cleanup(self):
        self.vars = None
        self.__framework = None

    def handle_set_command(self, name, value):
        """Set variable

        Usage: set NAME VALUE
        """
        self.vars[name] = value

def create_plugin(framework):
    return VarsPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:

