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
import uuid

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
        self.correlation_id = uuid.uuid4().hex

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
#        self.manoconn.register_notification_endpoint(
#            self.on_service_deploy_request,
#            "infrastructure.service.deploy")
#        
        # Activate this to sniff and print all messages on the broker
#        self.manoconn.subscribe(self.callback_print, "infrastructure.service.deploy")

        #We need to receive all messages from the slm intended for the gk
        self.manoconn.subscribe(self.on_slm_messages, "service.instances.create")

        self.manoconn.subscribe(self.on_topology, "infrastructure.management.topology")

#        self.manoconn.subscribe(self.on_onboard, "specific.manager.registry.ssm.on-board")

    def run(self):
        """
        Plugin logic. Does nothing in our example.
        """
        # lets run for 30 seconds and stop
        time.sleep(180)
        print('Timeout')
        os._exit(1)

    def on_registration_ok(self):
        """
        Event that is triggered after a successful registration process.
        """
        LOG.info("Registration OK.")

    def on_lifecycle_start(self, ch, method, properties, message):
        super(self.__class__, self).on_lifecycle_start(ch, method, properties, message)

        #Add new VIM to IA
#        vim_message = json.dumps({'tenant':'iMinds', 'wr_type' : 'compute', 'vim_type': 'Mock', 'vim_address' : 'http://localhost:9999', 'username' : 'Eve', 'pass':'Operator'})

#        self.manoconn.call_async(self.on_infrastructure_adaptor_reply, 
#                                'infrastructure.management.compute.add',
#                                vim_message)

#        time.sleep(3)

        #At deployment, this plugin generates a service request, identical to how the GK will do it in the future.
        message = self.createGkNewServiceRequestMessage()
        uuid_str = '4cd63b8b-b32f-4c6c-82e4-02fb89b53411'


#        for x in range(1,50):
#            final_part = uuid_str[-8:]
#            final_part_int = int(final_part, 16)
#            final_part_int = final_part_int + 2
#            uuid_str = uuid_str[:-8] + hex(final_part_int)[2:]

        self.manoconn.call_async(
                        self.on_slm_messages,
                        "service.instances.create",
                        message,
                        content_type="application/yaml",
                        correlation_id=uuid_str)


    def on_infrastructure_adaptor_reply(self, ch, method, properties, message):
        
        print('infra response: ' + str(json.loads(str(message, "utf-8"))))

    def on_slm_messages(self, ch, method, properties, message):
        """
        Printing response from the SLM to the GK on all messages.
        """
        msg = yaml.load(message)

        print(properties.app_id)

        print("RESPONSE FROM GK START")
        print("RESPONSE FROM GK END")
        if 'error' in msg.keys() and (properties.correlation_id == self.correlation_id): 		
            if msg['error'] != None:	
                print(msg['error'])
                os._exit(1)
        if 'status' in msg.keys() and (properties.correlation_id == self.correlation_id):
            if msg['status'] == 'Deployment completed':
                os._exit(0)
        

    def callback_print(self, ch, method, properties, message):

        print('correlation_id: ' + str(properties.correlation_id))  
        print('message: ' + str(message))      

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

    def on_onboard(self, ch, method, properties, payload):

        if properties.app_id != 'son-plugin.DemoPlugin1':
            message = yaml.load(payload)
            ssms = message['service_specific_managers']

            ssm_uuid = str(uuid.uuid4())
            topic1 = 'ssm.management.' + str(ssm_uuid) + '.task'
            topic2 = 'ssm.management.' + str(ssm_uuid) + '.place'

            self.manoconn.subscribe(self.on_task, topic1)
            self.manoconn.subscribe(self.on_place, topic2)

            ssm_list = [ssm_uuid]
            message = {'SSMs':ssm_list}
            payload = yaml.dump(message)

            self.manoconn.notify(str(properties.reply_to), payload, correlation_id=properties.correlation_id)

    def on_task(self, ch, method, properties, payload):

        if properties.app_id != 'son-plugin.DemoPlugin1':
            message = yaml.load(payload)
            message['schedule'][0] = 'req_placement_from_ssm'

            payload = yaml.dump(message)

            self.manoconn.notify(str(properties.reply_to), payload, correlation_id=properties.correlation_id)

    def on_place(self, ch, method, properties, payload):

        if properties.app_id != 'son-plugin.DemoPlugin1':
            message = {'placement': ['from_ssm']}
            payload = yaml.dump(message)

            self.manoconn.notify(str(properties.reply_to), payload, correlation_id=properties.correlation_id)

    def createGkNewServiceRequestMessage(self):
        """
        This method helps creating messages for the service request packets.
        """
        
        path_descriptors = 'test_descriptors/'
    	#import the nsd and vnfds that form the service	
        nsd_descriptor   = open(path_descriptors + 'sonata-demo.yml','r')
        vnfd1_descriptor = open(path_descriptors + 'firewall-vnfd.yml','r')
        vnfd2_descriptor = open(path_descriptors + 'iperf-vnfd.yml','r')
        vnfd3_descriptor = open(path_descriptors + 'tcpdump-vnfd.yml','r')

        service_request = {'NSD': yaml.load(nsd_descriptor), 'VNFD1': yaml.load(vnfd1_descriptor), 'VNFD2': yaml.load(vnfd2_descriptor), 'VNFD3': yaml.load(vnfd3_descriptor)}

        return yaml.dump(service_request)

    def createInfrastructureAdapterResponseMessage(self):
        path_descriptors = 'test_records/'

        ia_nsr = yaml.load(open(path_descriptors + 'ia-nsr.yml','r'))

        return str(ia_nsr)

    def on_topology(self, ch, method, properties, message):

        # message should be a dictionary with the key 'topology'. The value of 
        # this key can be anything for now, SLM does not screen it, it sends
        # this value as is to the SSM.

        message = {'topology': ['something']}
        payload = yaml.dump(message)

        self.manoconn.notify(str(properties.reply_to), payload, correlation_id=properties.correlation_id)


def main():
    # reduce log level to have a nice output for demonstration
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
    DemoPlugin1()

if __name__ == '__main__':
    main()
