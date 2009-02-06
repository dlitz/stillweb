# -*- coding: utf-8 -*-
# MaximaPlugin.py - GNU maxima plugin for StillWeb
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

import subprocess
import tempfile

from StillWeb.Placeholders import ReplaceWithHTML, ReplaceWithNode, ReplaceWithNothing, PLACEHOLDERS_NAMESPACE
from StillWeb.sw_util import getChildText, TypicalPaths, ensure_path

class MaximaPlugin:
    def __init__(self, framework):
        self._framework = framework

        # Register the placeholder namespace
        ph_plugin = self._framework.plugins['StillWeb.Placeholders']
        ph_plugin.register_callback(self._handle_maxima_element, PLACEHOLDERS_NAMESPACE, 'maxima')

    def cleanup(self):
        if self._framework is not None:
            self._framework = None

    #
    # Namespace callback(s)
    #
    def _handle_maxima_element(self, page_generator, element):
        return self.maxima_expression_placeholder(getChildText(element), force_img=(element.getAttribute('force') == 'img'))

    #
    # Exported API
    #
    def maxima_expression_placeholder(self, maxima_expression):
        # SECURITY WARNING: This allows execution of arbitrary Maxima code
        command_file = tempfile.NamedTemporaryFile('w+t', encoding="ascii")
        output_file = tempfile.NamedTemporaryFile('w+t', encoding="ascii")
        maxima_command = """tex(%s, "%s");""" % (maxima_expression, output_file.name)
        command_file.write(maxima_command)
        command_file.flush()

        # Feed the expression to GNU maxima
        args = ['maxima', b'--very-quiet', b'--batch=' + command_file.name.encode('ascii')]
        subprocess.check_call(args)

        tex_code = output_file.read().strip().strip("$")    # Strip leading and trailing whitespace and dollar-signs

        output_file.close()
        command_file.close()

        # Use TeXPlugin to complete the placeholder
        return self._framework.plugins['StillWeb.TeXPlugin'].math_placeholder(tex_code)

def create_plugin(framework):
    return MaximaPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
