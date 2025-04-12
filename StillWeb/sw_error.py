# -*- coding: utf-8 -*-
# sw_error.py - StillWeb exceptions
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

class ScriptError(Exception):
    pass

class UnknownCommandError(ScriptError):
    pass

