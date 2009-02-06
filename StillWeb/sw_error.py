# -*- coding: utf-8 -*-
# sw_error.py - StillWeb exceptions
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

class ScriptError(Exception):
    pass

class UnknownCommandError(ScriptError):
    pass

