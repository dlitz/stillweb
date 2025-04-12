# -*- coding: utf-8 -*-
# Framework.py - Basic StillWeb framework
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

class Framework(object):
    def __init__(self):
        # The "plugins" dictionary is available to plugins for accessing other
        # plugins' APIs, but plugins must not modify it.
        self.plugins = {}

        self.__plugin_cleanup_order = []

    def cleanup(self):
        if self.plugins is not None:
            for plugin_name in self.__plugin_cleanup_order:
                plugin = self.plugins[plugin_name]

                # Call the plugin's cleanup routine
                plugin.cleanup()

                # Remove the plugin from the plugins dictionary
                del self.plugins[plugin_name]

            # Clean up references
            self.plugins = None
            self.__plugin_cleanup_order = None

    def load_plugin(self, plugin_name, module=None):
        """Load a plugin

        SECURITY WARNING: This command allows the execution of arbitrary code.
        """

        if plugin_name in self.plugins:
            raise ValueError("Plugin %r already loaded" % (plugin_name,))

        if module is None:
            module = plugin_name

        if isinstance(module, str):
            module_name = module
            module = None

            # HACK - import the module
            c = {}
            exec("import %s as MODULE" % (module_name,), c)
            module = c['MODULE']

        # Initialize the plugin module
        self.plugins[plugin_name] = module.create_plugin(self)

        # Plugins are cleaned up in reverse order
        self.__plugin_cleanup_order.insert(0, plugin_name)

# vim:set ts=4 sw=4 sts=4 expandtab:
