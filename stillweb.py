# -*- coding: utf-8 -*-
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

import sys

from StillWeb.Framework import Framework

initial_plugin_list = [
    ('StillWeb.ScriptProcessor',),
    ('vars', 'StillWeb.VarsPlugin'),
    ('StillWeb.BasicCommands',),
    ('StillWeb.PageGenerator',),
    ('StillWeb.Placeholders',),
    ('StillWeb.MyFilters',),
    ('StillWeb.HtAccess',),
    ('StillWeb.FeedGenerator',),
    ('StillWeb.TeXPlugin',),
    ('StillWeb.NewsPlugin',),
    ('StillWeb.MaximaPlugin',),
]

if __name__ == '__main__':
    master_script_filename = sys.argv[1]

    framework = Framework()
    try:
        for args in initial_plugin_list:
            framework.load_plugin(*args)
        framework.plugins['StillWeb.ScriptProcessor'].process_script(master_script_filename)
    finally:
        framework.cleanup()

# vim:set ts=4 sw=4 sts=4 expandtab:
