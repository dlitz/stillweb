# -*- coding: utf-8 -*-
# ScriptProcessor.py - StillWeb script processor
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

import sys
import shlex

class ScriptError(Exception):
    pass

class UnknownCommandError(ScriptError):
    pass


class ScriptProcessor:

    def __init__(self, framework):
        self._framework = framework

        self._commands = {}

        # Add built-in commands
        self.register_command('.load_plugin', self.handle_load_plugin)
        self.register_command('execute', self.handle_execute)

    def cleanup(self):
        if self._framework is not None:
            self._commands = None
            self._framework = None

    #
    # Exported API
    #
    def process_script(self, filename, file=None):
        if file is None:
            file = open(filename, "rt", encoding="UTF-8")
        try:
            lineno = 0
            while True:
                line = file.readline()
                lineno += 1
                if not line:
                    break
                try:
                    rawargs = shlex.split(line, comments=True)
                    if not rawargs:
                        continue
                    self.exec_command(*rawargs)
                except Exception as exc:
                    print("Error in %s, line %d:" % (filename, lineno), file=sys.stderr)
                    raise
        finally:
            file.close()

    def exec_command(self, *rawargs):
        cmd = rawargs[0]
        args = rawargs[1:]
        try:
            handler = self._commands[cmd]
        except KeyError:
            raise UnknownCommandError("Unknown command: %r" % (cmd,))
        handler(*args)

    def register_command(self, command_name, handler):
        if command_name in self._commands:
            raise ValueError("command %r already added" % (command_name,))
        self._commands[command_name] = handler

    #
    # Built-in commands
    #
    def handle_load_plugin(self, plugin_name, module_name=None):
        """Command to load a plugin

        Usage: .load_plugin PYTHON-MODULE [NAME]

        SECURITY WARNING: This command allows the execution of arbitrary code.
        """

        self._framework.load_plugin(plugin_name, module_name)

    def handle_execute(self, filename):
        """Run another script

        Usage: execute FILE
        """
        self.process_script(filename)


def create_plugin(framework):
    return ScriptProcessor(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
