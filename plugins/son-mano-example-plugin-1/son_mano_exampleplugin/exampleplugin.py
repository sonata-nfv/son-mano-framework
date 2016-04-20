"""
Created by Manuel Peuster <manuel@peuster.de>

This is a stupid MANO plugin used for testing.
"""

import logging
import json
import time
import sys
import os
import yaml

sys.path.append("../../../son-mano-base")
from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:example-plugin-1")
LOG.setLevel(logging.DEBUG)


class DemoPlugin1(ManoBasePlugin):
    """
    This is a very simple example plugin to demonstrate
    some APIs.

    It does the following:
    1. registers itself to the plugin manager
    2. waits some seconds
    3. requests a list of active plugins from the plugin manager and prints it
    4. de-registers itself
    """

    def __init__(self):
        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__(version="0.1-dev")

    def __del__(self):
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to listen.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()
        # Examples to demonstrate how a plugin can listen to certain events:
        self.manoconn.register_async_endpoint(
            self._on_example_request,  # call back method (expected to return a response message)
            "example.plugin.*.request")
        self.manoconn.register_notification_endpoint(
            self._on_example_notification,  # call back method
            "example.plugin.*.notification")

        #Faking the IA, currently disabled.
        #self.manoconn.register_notification_endpoint(
        #    self.on_service_deploy_request,
        #    "infrastructure.service.deploy")

        # Activate this to sniff and print all messages on the broker
        #self.manoconn.subscribe(self.manoconn.callback_print, "#")

    def run(self):
        """
        Plugin logic. Does nothing in our example.
        """
        # go into infinity loop (we could do anything here)
        while True:
            time.sleep(1)

    def on_registration_ok(self):
        """
        Event that is triggered after a successful registration process.
        """
        LOG.info("Registration OK.")

    def on_lifecycle_start(self, ch, method, properties, message):
        super(self.__class__, self).on_lifecycle_start(ch, method, properties, message)

#        # Example that shows how to send a request/response message
#        time.sleep(1)
#        self.manoconn.call_async(
#                        self._on_example_request_response,
#                        "example.plugin.%s.request" % str(self.uuid),
#                        json.dumps({"content": "my request"}))
#        time.sleep(1)
#        # Example that shows how to send a notification message
#        self.manoconn.notify(
#                        "example.plugin.%s.notification" % str(self.uuid),
#                        json.dumps({"content": "my notification"}))

#        time.sleep(5)
#        os._exit(0)

        #At deployment, this plugin generates a service request, identical to how the GK will do it in the future.
        message = self.createGkNewServiceRequestMessage()

        self.manoconn.call_async(
                        self.on_service_request_from_gk,
                        "service.instances.create",
                        message,
                        content_type="application/yaml")

    def on_service_request_from_gk(self, ch, method, properties, message):
        """
        Printing response from the SLM to the GK on deployment message.
        """
        print("RESPONSE FROM GK START")
        print(yaml.load(message))
        print("RESPONSE FROM GK END")


    def on_service_deploy_request(self, ch, method, properties, message):
        """
        IA faking
        """
       
        LOG.debug("request from SLM for IA: %r" % str(yaml.load(message)))
        if properties.app_id != 'son-plugin.DemoPlugin1':
            self.manoconn.notify("infrastructure.service.deploy", self.createInfrastructureAdapterResponseMessage(), content_type='application/yaml', correlation_id=properties.correlation_id)

    def _on_example_request(self, ch, method, properties, message):
        """
        Only used for the examples.
        """
        print("Example message: %r " % message)
        return json.dumps({"content" : "my response"})

    def _on_example_request_response(self, ch, method, properties, message):
        """
        Only used for the examples.
        """
        print("Example message: %r " % message)

    def _on_example_notification(self, ch, method, properties, message):
        """
        Only used for the examples.
        """
        print("Example message: %r " % message)

    def createGkNewServiceRequestMessage(self):
        """
        This method helps creating messages for the service request packets.
        """
        
        path_descriptors = '/test_descriptors/'
    	#import the nsd and vnfds that form the service	
        nsd_descriptor   = open(path_descriptors + 'sonata-demo.yml','r')
        vnfd1_descriptor = open(path_descriptors + 'firewall-vnfd.yml','r')
        vnfd2_descriptor = open(path_descriptors + 'iperf-vnfd.yml','r')
        vnfd3_descriptor = open(path_descriptors + 'tcpdump-vnfd.yml','r')

        service_request = {'NSD': yaml.load(nsd_descriptor), 'VNFD1': yaml.load(vnfd1_descriptor), 'VNFD2': yaml.load(vnfd2_descriptor), 'VNFD3': yaml.load(vnfd3_descriptor)}

        return yaml.dump(service_request)

    def createInfrastructureAdapterResponseMessage(self):
        path_descriptors = 'test_descriptors/'

        ia_nsr = yaml.load(open(path_descriptors + 'infrastructure-adapter-nsr.yml','r'))

        return str(ia_nsr)



def main():
    # reduce log level to have a nice output for demonstration
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.DEBUG)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.DEBUG)
    DemoPlugin1()

if __name__ == '__main__':
    main()
