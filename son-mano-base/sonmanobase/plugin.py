# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, 5GTANGO
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).
#
# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).

import logging
import json
import time
import os
import threading

from sonmanobase import messaging
from sonmanobase.logger import TangoLogger

LOG = TangoLogger.getLogger("son-mano-base:plugin", log_level=logging.DEBUG, log_json=True)

class ManoBasePlugin(object):
    """
    Abstract class that should be inherited by other MANO plugins.
    This class provides basic mechanisms to
    - connect to the broker
    - send/receive async/sync request/response calls
    - send/receive notifications
    """

    def __init__(self,
                 name="son-plugin",
                 version=None,
                 description=None,
                 start_running=True):
        """
        Performs plugin initialization steps, e.g., connection setup
        :param name: Plugin name prefix
        :param version: Plugin version
        :param description: A description string
        :return:
        """
        self.name = "%s.%s" % (name, self.__class__.__name__)
        self.version = version
        self.description = description
        self.uuid = None  # uuid given by plugin manager on registration
        self.state = None  # the state of this plugin READY/RUNNING/PAUSED/FAILED

        LOG.info(
            "Starting MANO Plugin: %r ..." % self.name)
        # create and initialize broker connection
        while True:
            try:
                self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)
                break
            except:
                time.sleep(1)

        LOG.info("Plugin connected to broker.")

        self.declare_subscriptions()

        self.on_lifecycle_start()

        # jump to run
        if start_running:
            LOG.info("Plugin running...")
            self.run()

    def __del__(self):
        """
        Actions done when plugin is destroyed.
        :return:
        """
        self.manoconn.stop_connection()
        self.manoconn.stop_threads()
        del self.manoconn

    def declare_subscriptions(self):
        """
        Can be overwritten by subclass.
        But: The this superclass method should be called in any case.
        """
        # plugin status update subscription

        LOG.info("declaring subscriptions")

    def run(self):
        """
        To be overwritten by subclass
        """
        # go into infinity loop (we could do anything here)
        while True:
            time.sleep(1)

    def on_lifecycle_start(self):
        """
        To be overwritten by subclass
        """
        LOG.debug("Received lifecycle.start event.")
        self.state = "RUNNING"
