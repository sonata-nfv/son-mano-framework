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

# The topic to which resource availabiltiy replies of the Infrastructure Adaptor are published
INFRA_ADAPTOR_RESOURCE_AVAILABILITY_REPLY_TOPIC = "infrastructure.management.compute.resources";

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

        # TODO build request to IA: format is still to be defined
        resource_request = {};

        #If all the above checks succeed, we send the message as received from the GK to the IA, and return a message to the GK indicating that the process is initiated.
        self.manoconn.call_async(self.callback_factory(service_request_from_gk),
                                 INFRA_ADAPTOR_RESOURCE_AVAILABILITY_REPLY_TOPIC,
                                 yaml.dump(resource_request),
                                 correlation_id=properties.correlation_id)


        return yaml.dump({'status'    : 'INSTANTIATING',        #INSTANTIATING or ERROR
                          'error'     : 'None',         #NULL or a string describing the ERROR
                          'timestamp' : time.time()})  #time() returns the number of seconds since the epoch in UTC as a float      

    def callback_factory(self, nsd_request):
        request = nsd_request

        def on_infra_adaptor_resource_availability_reply(self, ch, method, properties, message):
            # TODO handle IA response: format is still to be defined
            self.manoconn.call_async(self.on_infra_adaptor_service_deploy_reply,
                                 INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC,
                                 yaml.dump(request),
                                 correlation_id=properties.correlation_id)


        return on_infra_adaptor_resource_availability_reply

    def on_infra_adaptor_service_deploy_reply(self, ch, method, properties, message):
        """
        This method is called when the Infrastructure Adaptor replies to a service deploy request from the SLM.
        Based on the content of the reply message, the NSR has to be contacted.
        The GK should be notified of the result of the service request.
        """
        msg = yaml.load(message)
        #The message that will be returned to the gk
        message_for_gk = {}
        message_for_gk['error'] = {}
        # filter result of service request out of the message and add it to the reply
        request_status = msg['request_status']
        message_for_gk['request_status'] = request_status

        if request_status == 'RUNNING':
            #Retrieve NSR from message
            nsr = msg['nsr'];
            if ('id' not in nsr):
                nsr['id'] = uuid.uuid4().hex

            #Retrieve VNFRs from message
            vnfrs = msg["vnfr"]
            ## Store vnfrs in the repository and add vnfr ids to nsr if it is not already present
            if ('vnfr' not in nsr):
                nsr['vnfr'] = []
            for vnfr in vnfrs:
                if ('vnfr' not in nsr):
                    nsr['vnfr'].append(vnfr['id'])
                #Store the message, catch exception when time-out occurs
                try:
                    vnfr_response = self.postVnfrToRepository(yaml.dump(vnfr), {'Content-Type':'application/x-yaml'}, timeout=20.0)
                    #If storage succeeds, add uuids to reply to gk
                    if (vnfr_response.status_code == 200):
                        if 'vnfr' in message_for_gk.keys():
                            #The reply should contain an uuid, but just in case
                            if 'vnfr_uuid' in vnfr_response.json().keys():
                                message_for_gk['vnfr'].append(vnfr_response.json()['vnfr_uuid'])
                            else:
                                message_for_gk['vnfr'].append(vnfr_response.json())
                        else:
                            message_for_gk['vnfr'] = []
                            #The reply should contain an uuid, but just in case
                            if 'vnfr_uuid' in vnfr_response.json().keys():
                                message_for_gk['vnfr'].append(vnfr_response.json()['vnfr_uuid'])
                            else:
                                message_for_gk['vnfr'].append(vnfr_response.json())
                    #If storage fails, add error code and message to reply to gk
                    else:
                        message_for_gk['vnfr'] = []
                        message_for_gk['error']['vnfr'] = {'http_code':vnfr_response.status_code, 'message':vnfr_response.json()}
                        break
                except:
                    message_for_gk['vnfr'] = []
                    message_for_gk['error']['vnfr'] = {'http_code':'0', 'message':'Timeout when contacting server'}
                    break
                    
            #Store nsr in the repository, catch exception when time-out occurs
            try:
                nsr_response = self.postNsrToRepository(json.dumps(nsr), {'Content-Type':'application/json'}, timeout=20.0)
                if (nsr_response.status_code == 200):
                    #The reply should contain an uuid, but just in case
                    if 'nsr_uuid' in nsr_response.json().keys():
                        message_for_gk['nsr'] = nsr_response.json()['nsr_uuid']
                    else:
                        message_for_gk['nsr'] = nsr_response.json()
                else:
                    message_for_gk['error']['nsr'] = {'http_code':nsr_response.status_code, 'message':nsr_response.json()}
            except:
                message_for_gk['error']['nsr'] = {'http_code':'0', 'message':'Timeout when contacting server'}
                
        print(message_for_gk)
        self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump(message_for_gk))


    def postNsrToRepository(self, nsr, headers, timeout=None):
        return requests.post(NSR_REPOSITORY_URL + 'ns-instances', data=nsr, headers=headers, timeout=timeout)

    def postVnfrToRepository(self, vnfr, headers, timeout=None):
        return requests.post(VNFR_REPOSITORY_URL + 'vnf-instances', data=vnfr, headers=headers, timeout=timeout)
        

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
