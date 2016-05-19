"""
Created by Manuel Peuster <manuel@peuster.de>

This is a stupid MANO plugin used for some integration tests.

ATTENTION: Please do not change this plugin and DO NOT use it for any code experiments.
(we have the example-plugin for this)
"""

import logging
import sys


sys.path.append("../../../son-mano-base")
from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.DEBUG)
LOG = logging.getLogger("plugin:test-plugin")
LOG.setLevel(logging.DEBUG)


class TestPlugin(ManoBasePlugin):
    """
    This is the most simple plugin. It does nothing (except of registration etc.).
    """
    def __init__(self):
        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__(version="1.0-dev")


def main():
    TestPlugin()

if __name__ == '__main__':
    main()
