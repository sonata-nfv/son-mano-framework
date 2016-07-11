"""
Copyright (c) 2015 SONATA-NFV
ALL RIGHTS RESERVED.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.
This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).
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
