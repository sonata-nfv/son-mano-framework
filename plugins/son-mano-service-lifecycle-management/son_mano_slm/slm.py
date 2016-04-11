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
VNFR_REPOSITORY_URL = "http://api.int.sonata-nfv.eu:4002/records/vnfr/";


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

        #The request data is in the message as a yaml file, and should be constructed like:
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
        LOG.debug("request from GK: %r" % str(service_request_from_gk))

        #The service request in the yaml file should be a dictionary
        if not isinstance(service_request_from_gk, dict):
            return yaml.dump({'status'    : 'REJECTED',        
                              'error'     : 'Message is not a dictionary',
                              'timestamp' : time.time()})

        #The dictionary should contain a 'NSD' key
        if 'NSD' not in service_request_from_gk.keys():
            return yaml.dump({'status'    : 'REJECTED',        
                              'error'     : 'No NSD field in dictionary',
                              'timestamp' : time.time()})

        #Their should be as many VNFDx keys in the dictionary as their are network functions according to the NSD.
        number_of_vnfds = 0
        for key in service_request_from_gk.keys():
            if key[:4] == 'VNFD':
                number_of_vnfds = number_of_vnfds + 1

        if len(service_request_from_gk['NSD']['network_functions']) != number_of_vnfds:
            return yaml.dump({'status'    : 'REJECTED',        
                              'error'     : 'Number of VNFDs doesn\'t match number of vnfs',
                              'timestamp' : time.time()})

        #If all the above checks succeed, we send the message as received from the GK to the IA, and return a message to the GK indicating that the process is initiated.
        
        self.manoconn.call_async(self.on_infra_adaptor_service_deploy_reply, 
                                 INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC, 
                                 yaml.dump(service_request_from_gk), 
                                 correlation_id=properties.correlation_id)                

        return yaml.dump({'status'    : 'INSTANTIATING',        #INSTANTIATING or ERROR
                          'error'     : 'None',         #NULL or a string describing the ERROR
                          'timestamp' : time.time()})  #time() returns the number of seconds since the epoch in UTC as a float      

    def on_infra_adaptor_service_deploy_reply(self, ch, method, properties, message):
        """
        This method is called when the Infrastructure Adaptor replies to a service deploy request from the SLM.
        Based on the content of the reply message, the NSR has to be contacted.
        The GK should be notified of the result of the service request.
        """
        msg = yaml.load(message)
        LOG.debug("IA request from SLM: %r" % str(msg))        
        # filter result of service request out of the message
        request_status = msg['request_status']
        if request_status == 'RUNNING':
            #Add NSR and VNFRs to Repositories
            nsr_request = msg['nsr'];
            if ('id' not in nsr_request):
                nsr_request['id'] = uuid.uuid4().hex

            vnfrs = {}
            vnfrs["vnfr"] = msg["vnfr"]
            ## add vnfr ids to nsr
            if ('vnfr' not in nsr_request):
                nsr_request['vnfr'] = []
                for vnfr in vnfrs['vnfr']:
                    vnfr_request = {}
                    vnfr_request['vnfr'] = vnfr;
                    vnfr_response = self.postVnfrToRepository(yaml.dump(vnfr_request), {'Content-Type':'application/x-yaml'})
                    nsr_request['vnfr'].append(vnfr['id'])

            nsr_response = self.postNsrToRepository(json.dumps(nsr_request), {'Content-Type':'application/json'})

            # TODO: handle responses from repositories
            #Inform the GK
            #TODO: add correlation_id, build message for GK, add info on NSR, VNFRs
            self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump({'request_status':request_status}))
        else:
            #Inform the GK
            #TODO: add correlation_id, build message for GK
            self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump({'request_status':request_status}))

    def postNsrToRepository(self, nsr, headers):
        return requests.post(NSR_REPOSITORY_URL + 'ns-instances', data=nsr, headers=headers)

    def postVnfrToRepository(self, vnfr, headers):
        return requests.post(VNFR_REPOSITORY_URL + 'vnf-instances', data=vnfr, headers=headers)
        

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
