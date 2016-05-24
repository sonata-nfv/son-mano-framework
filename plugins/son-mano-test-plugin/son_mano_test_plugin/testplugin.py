"""
 Copyright 2015-2017 Paderborn University

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""
"""
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
