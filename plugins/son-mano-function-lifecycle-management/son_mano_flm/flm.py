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
partner consortium (www.sonata-nfv.eu).a
"""
"""
This is SONATA's function lifecycle management plugin
"""

import logging
import yaml
import time
import requests
import uuid
import json
import sys
import concurrent.futures as pool
import flm_topics as t

from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:flm")
LOG.setLevel(logging.DEBUG)


class FunctionLifecycleManager(ManoBasePlugin):
    """
    This class implements the function lifecycle manager.

    see: https://github.com/sonata-nfv/son-mano-framework/issues/23
    """

    def __init__(self):
        """
        Initialize class and son-mano-base.plugin.BasePlugin class.
        This will automatically connect to the broker, contact the
        plugin manager, and self-register this plugin to the plugin
        manager.

        After the connection and registration procedures are done, the
        'on_lifecycle_start' method is called.
        :return:
        """
        # call super class (will automatically connect to
        # broker and register the FLM to the plugin manger)
        ver = "0.1-dev"
        des = "This is the FLM plugin"
        super(self.__class__, self).__init__(version=ver, description=des)

    def __del__(self):
        """
        Destroy FLM instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to subscribe to.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()

        # The FLM should instantiate the VNFs upon request from the SLM

        self.manoconn.subscribe(self.function_instance_create,
                                t.FUNCTION_CREATE)

    def on_lifecycle_start(self, ch, mthd, prop, msg):
        """
        This event is called when the plugin has successfully registered itself
        to the plugin manager and received its lifecycle.start event from the
        plugin manager. The plugin is expected to do its work after this event.

        :param ch: RabbitMQ channel
        :param method: RabbitMQ method
        :param properties: RabbitMQ properties
        :param message: RabbitMQ message content
        :return:
        """
        super(self.__class__, self).on_lifecycle_start(ch, mthd, prop, msg)
        LOG.info("Lifecycle start event")

    def function_instance_create(self, ch, method, prop, payload):
        """
        This method handles the request to deploy a vnf.
        """

        if prop.app_id != 'son-plugin.FunctionLifecycleManager':

            message = yaml.load(payload)
            vnfd = message['vnfd']
            mapping = message['mapping']

            # TODO: contact IA to deploy this vnf with the mapping
            # TODO: hardcoded response to SLM
            response = {'vnf_name': vnfd['name'], 'status':'DEPLOYED'}
            payload = yaml.dump(response)

            self.manoconn.notify(t.FUNCTION_CREATE, payload, correlation_id=prop.correlation_id)


def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
#    logging.getLogger("amqp-storm").setLevel(logging.DEBUG)
    # create our function lifecycle manager
    FunctionLifecycleManager()

if __name__ == '__main__':
    main()
