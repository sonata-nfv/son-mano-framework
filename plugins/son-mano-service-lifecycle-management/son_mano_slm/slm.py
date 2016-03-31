"""
This is SONATA's service lifecycle management plugin
"""


import logging
import yaml
import time
import requests
import uuid
import json

from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:slm")
LOG.setLevel(logging.DEBUG)

#
# Configurations
#
# The topic to which service instantiation requests of the GK are published
GK_INSTANCE_CREATE_TOPIC = "service.instances.create"

# The topic to which service instance deploy replies of the Infrastructure Adaptor are published
INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC = "infrastructure.service.deploy"

# The NSR Repository can be accessed through a RESTful API
NSR_REPOSITORY_URL = "http://api.int.sonata-nfv.eu:4002/records/nsr/"


class ServiceLifecycleManager(ManoBasePlugin):
    """
    This class implements the service lifecycle manager.

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
        # call super class (will automatically connect to broker and register the SLM to the plugin manger)
        super(self.__class__, self).__init__(version="0.1-dev",description="This is the SLM plugin")

    def __del__(self):
        """
        Destroy SLM instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to subscribe to.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()
        #
        # GK <-> SLM interface
        #
        # We want to subscribe to GK_INSTANCE_CREATE_TOPIC to react on GK messages
        self.manoconn.register_async_endpoint(
            self.on_gk_service_instance_create,  # function called when message received
            GK_INSTANCE_CREATE_TOPIC)  # topic to listen to
        #
        # SLM <-> infra. adaptor interface
        #
        self.manoconn.register_async_endpoint(self.on_infra_adaptor_service_deploy_reply, INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC)

    def on_lifecycle_start(self, ch, method, properties, message):
        """
        This event is called after the plugin has successfully registered itself
        to the plugin manager and received its lifecycle.start event from the
        plugin manager. The plugin is expected to do its work after this event.

        This is a default method each plugin should implement.

        :param ch: RabbitMQ channel
        :param method: RabbitMQ method
        :param properties: RabbitMQ properties
        :param message: RabbitMQ message content
        :return:
        """
        super(self.__class__, self).on_lifecycle_start(ch, method, properties, message)
        LOG.info("Lifecycle start event")
        # TODO does the SLM need to perform any actions after it has been started?

    def on_gk_service_instance_create(self, ch, method, properties, message):
        """
        This is our first SLM specific event method. It is called when the SLM
        receives a message from the GK published to GK_INSTANCE_CREATE_TOPIC.

        Here we should react and trigger the service instantiation.

        :param ch: RabbitMQ channel
        :param method: RabbitMQ method
        :param properties: RabbitMQ properties
        :param message: RabbitMQ message content
        :return:
        """

        LOG.info("GK service.instance.start event")

        #TODO: We need to check whether the received message is formatted as expected.
        #TODO: We need to define what can go wrong during this method to report back to the gk 
 
        status = 'INSTANTIATING'
        error = None

        #The request data is in the message as a yaml file, constructed like:
        #---
        #NSD:
        #        descriptor_version:
        #        ...
        #VNFD1:
        #        descriptor_version:
        #        ...
        #VNFD2:
        #        descriptor_version:
        #        ...
        #...

        service_request_from_gk = yaml.load(message)

        #The slm reacts to this service_intance_create message with a call_async() to infrastructure.service.deploy
        #The response message is a yaml file, constructed like:
        #---
        #forwarding_graph:
        #        ...
        #vnf_images:
        #        - vnf_id:
        #          url:
        #        - vnf_id:
        #          url
        #        - ...

        #The message for the infrastructure adaptor is a yaml file, built from a dictionary
        service_request_for_infra_adaptor = {}


        #Adding the forwarding graph to the dictionary
        service_request_for_infra_adaptor['forwarding_graph'] = service_request_from_gk['NSD']['forwarding_graphs']


        #vnf_images contains a list of dictionaries
        service_request_for_infra_adaptor['vnf_images'] = []

        
        #constructing the dictionary for each VNF
        for key in service_request_from_gk.keys():
            if (key[:4] == 'VNFD'):
                #Determine which vnf_id is mapped to vnf_name, vnf_version, vnf_group.
                vnf_descriptor = service_request_from_gk[key]
                for network_function in service_request_from_gk['NSD']['network_functions']:
                    if (network_function['vnf_name'] == vnf_descriptor['vnf_name']) and (network_function['vnf_group'] == vnf_descriptor['vnf_group']) and (network_function['vnf_version'] == vnf_descriptor['vnf_version']):
                        vnf_dict = {'vnf_id': network_function['vnf_id'],'url' : vnf_descriptor['virtual_deployment_units'][0]['vm_image']}
                        service_request_for_infra_adaptor['vnf_images'].append(vnf_dict)


        #Sending the message towards the infrastructure adaptor, with callback pointer
        self.manoconn.call_async(self.on_infra_adaptor_service_deploy_reply, INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC, yaml.dump(service_request_for_infra_adaptor))                

        
        #Reply for the GK
        return yaml.dump({'status'    : status,        #INSTANTIATING or ERROR
                          'error'     : error,         #NULL or a string describing the ERROR
                          'timestamp' : time.time()})  #time() returns the number of seconds since the epoch in UTC as a float      

    def on_infra_adaptor_service_deploy_reply(self, ch, method, properties, message):
        """
        This method is called when the Infrastructure Adaptor replies to a service deploy request from the SLM.
        Based on the content of the reply message, the NSR has to be contacted.
        The GK should be notified of the result of the service request.
        """
        msg = yaml.load(message)
        # filter result of service request out of the message
        request_status = msg["request_status"]
        if request_status == 'RUNNING':
            #Add NSR and VNFRs to Repositories
            nsr_request = msg["nsr"];
            if ("id" not in nsr_request):
                nsr_request["id"] = uuid.uuid4().hex
            nsr_request["vnfr"] = msg["vnfr"]

            nsr_response = self.postNsrToRepository(json.dumps(nsr_request), {'Content-Type':'application/json'})
            # TODO: handle response from repository
            #Inform the GK
            #TODO: add correlation_id, build message for GK, add info on NSR, VNFRs
            self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump({'request_status':request_status}))
        else:
            #Inform the GK
            #TODO: add correlation_id, build message for GK
            self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump({'request_status':request_status}))

    def postNsrToRepository(self, nsr, headers):
        return requests.post(NSR_REPOSITORY_URL + 'ns-instances', data=nsr, headers=headers)

        

def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
    # create our service lifecycle manager
    ServiceLifecycleManager()

if __name__ == '__main__':
    main()
