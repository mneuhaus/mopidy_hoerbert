from __future__ import unicode_literals

import logging
import os

from mopidy import config, ext


__version__ = '0.1.1'

# TODO: If you need to log, use loggers named after the current Python module
logger = logging.getLogger(__name__)


class Extension(ext.Extension):

    dist_name = 'Mopidy-Hoerbert'
    ext_name = 'hoerbert'
    version = __version__

    def get_default_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), 'ext.conf')
        return config.read(conf_file)

    def get_config_schema(self):
        schema = super(Extension, self).get_config_schema()
        schema['pin_button_play'] = config.Integer()
        schema['pin_button_sleep'] = config.Integer()
        schema['sleep_time'] = config.Integer()
        schema['pin_button_volume_up'] = config.Integer()
        schema['pin_button_volume_down'] = config.Integer()
        schema['volume_steps'] = config.Integer()
        for i in range(1, 10):
            schema['pin_button_playlist_' + str(i)] = config.Integer()
            schema['playlist_' + str(i)] = config.String()
        return schema

    def setup(self, registry):
        # You will typically only implement one of the following things
        # in a single extension.

        # TODO: Edit or remove entirely
        from .frontend import GpioFrontend
        registry.add('frontend', GpioFrontend)

        # # TODO: Edit or remove entirely
        # from .backend import FoobarBackend
        # registry.add('backend', FoobarBackend)

        # # TODO: Edit or remove entirely
        # registry.add('http:static', {
        #     'name': self.ext_name,
        #     'path': os.path.join(os.path.dirname(__file__), 'static'),
        # })
