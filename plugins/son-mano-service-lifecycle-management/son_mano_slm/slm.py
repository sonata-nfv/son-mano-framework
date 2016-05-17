"""
This is SONATA's service lifecycle management plugin
"""

import logging
import yaml
import time
import requests
import uuid
import threading
import json
try:
    import slm_helpers as tools
except ImportError:
    pass

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
INFRA_ADAPTOR_RESOURCE_AVAILABILITY_REPLY_TOPIC = "infrastructure.management.compute.resourceAvailability";

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
        self.deployed_ssms = {}
        self.service_requests_being_handled = {}

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

        # When a new SSM registered, we want to add it to the deployed SSMs list.
        self.manoconn.register_notification_endpoint(
            self.on_ssm_registration,
            'ssm.management.register')

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

        #If all checks on the received message pass, an uuid is created for the service, and we add it to the dict of services that are being deployed. 
        #Each VNF also gets an uuid. This is added to the VNFD dictionary.
        #The correlation_id is used as key for this dict, since it should be available in all the callback functions.
        self.service_requests_being_handled[properties.correlation_id] = service_request_from_gk

        #Since the key will change when new async calls are being made (each new call needs a unique corr_id), we need to keep track of the original one to reply to the GK at a later stage.
        self.service_requests_being_handled[properties.correlation_id]['original_corr_id'] = properties.correlation_id 

        self.service_requests_being_handled[properties.correlation_id]['instance_uuid'] = uuid.uuid4().hex
        for key in service_request_from_gk.keys():
            if key[:4] == 'VNFD':
                self.service_requests_being_handled[properties.correlation_id][key]['instance_uuid'] = uuid.uuid4().hex

        #We make sure that all required SSMs are deployed.
        #The order of the required ssms is the order in which they are to be called. To garantuee that we call
        #all of them, we add them to the service_requests_being_handled dictionary.
        #Each SSM should be able to handle the same input format, and return the same output format. 
        self.service_requests_being_handled[properties.correlation_id]['ssms_to_handle'] = []
        if 'SSMs' in service_request_from_gk['NSD'].keys():
            #Check whether each SSM is already deployed by previous service requests. If not, deploy them.
            for ssm in service_request_from_gk['NSD']['SSMs']:
                if ssm['name'] not in self.deployed_ssms.keys():
                    #TODO: deploy the SSM
                    pass
            self.serice_requests_being_handled[properties.correlation_id]['ssms_to_handle'] = service_request_from_gk['NSD']['SSMs']
    

        #After the received request has been processed, we can start handling it in a different thread.
        t = threading.Thread(target=self.start_new_service_deployment, args=(ch, method, properties, message))
        t.daemon = True
        t.start()

        return yaml.dump({'status'    : 'INSTANTIATING',        #INSTANTIATING or ERROR
                          'error'     : None,         #NULL or a string describing the ERROR
                          'timestamp' : time.time()})  #time() returns the number of seconds since the epoch in UTC as a float      

    def start_new_service_deployment(self, ch, method, properties, message):
        """
        This method initiates the deployment of a new service
        """
        #TODO: if this method is reached as callback on a ssm reply, handle the response of the ssm --> add the data to the dict

        #Contact the SSMs if needed
        if self.service_requests_being_handled[properties.correlation_id]['ssms_to_handle'] != []:
            LOG.info("Deploying new SSM")

            ssm_to_interact_with = self.service_requests_being_handled[properties.correlation_id]['ssms_to_handle'].pop(0)
            #TODO: build message for ssm if needed (I propose to keep it generalised, for example the entire data field in the service_requests_being_handled)
            message_for_ssm = {'dummy':'dummy'}
            #Contacting the SSM. In the service_requests_being_handled dictionary, we replace the old corr_id with the new one, to be able to keep track of the request
            new_corr_id, self.service_requests_being_handled = tools.replace_old_corr_id_by_new(self.service_requests_being_handled, properties.correlation_id)
            self.manoconn.call_async(self.start_new_service_deployment, 'ssm.scaling.' + str(ssm_to_interact_with['ssm_name']['uuid']) + '.compute', yaml.dump(message_for_ssm), correlation_id=new_corr_id)

        #If the list of SSMs to handle is empty, it means we can continu with the deployment phase, by requesting the IA if it has enough available resources.
        else:               
            LOG.info("Requesting resources")
            # TODO build request to IA: format is still to be defined. Use properties.correlation_id to extract request info from service_requests_being_handeld.
            resource_request = tools.build_resource_request(self.service_requests_being_handled[properties.correlation_id])

            #Before we request the IA to deploy the service, we check if it has the resources to do so. In the service_requests_being_handled dictionary, we replace the old corr_id with the new one, to be able to keep track of the request
            new_corr_id, self.service_requests_being_handled = tools.replace_old_corr_id_by_new(self.service_requests_being_handled, properties.correlation_id)      
            self.manoconn.call_async(self.on_infra_adaptor_resource_availability_reply,
                                 INFRA_ADAPTOR_RESOURCE_AVAILABILITY_REPLY_TOPIC,
                                 yaml.dump(resource_request),
                                 content_type="tex/x-yaml", 
                                 correlation_id=new_corr_id)

    def on_infra_adaptor_resource_availability_reply(self, ch, method, properties, message):
        """
        This method handles the IA replying if it has enough resources to deploy the service.
        """
        msg = yaml.load(message)

        def contacting_infa_adaptor_for_service_deploy(cbf, topic, message, correlation_id):
            """
            Dummy call_async intermediate, to explicitely run it in different thread
            """            
            self.manoconn.call_async(cbf, topic, message, correlation_id=correlation_id)

        #If the resources are available, we make a request to the IA to deploy the service.
        if msg['status'] == 'OK':
            LOG.info("Deploying service")
            request = tools.build_message_for_IA(self.service_requests_being_handled[properties.correlation_id])
            #In the service_requests_being_handled dictionary, we replace the old corr_id with the new one, to be able to keep track of the request
            new_corr_id, self.service_requests_being_handled = tools.replace_old_corr_id_by_new(self.service_requests_being_handled, properties.correlation_id)

            t = threading.Thread(target=contacting_infa_adaptor_for_service_deploy, args=(self.on_infra_adaptor_service_deploy_reply,
                                                                                               INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC,
                                                                                               yaml.dump(request),
                                                                                               new_corr_id))
            t.daemon = True
            t.start()

        #If the resources are not available, the deployment is aborted and the gatekeeper informed.
        else:
            LOG.info("Error with resource availability")
            LOG.info(msg)
            response_message = {'error': msg}
            self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump(response_message), correlation_id = self.service_requests_being_handled[properties.correlation_id]['original_corr_id'])

    def on_infra_adaptor_service_deploy_reply(self, ch, method, properties, message):
        """
        This method is called when the Infrastructure Adaptor replies to a service deploy request from the SLM.
        Based on the content of the reply message, the NSR has to be contacted.
        The GK should be notified of the result of the service request.
        """

        LOG.info("Handling deployment info")

        msg = yaml.load(message)
        #The message that will be returned to the gk
        message_for_gk = {}
        message_for_gk['error'] = {}
        # filter result of service request out of the message and add it to the reply
        request_status = msg['request_status']
        message_for_gk['request_status'] = request_status

        if request_status[:6] == 'normal':
            nsr = msg['nsr'];
            if ('id' not in nsr):
                nsr['id'] = uuid.uuid4().hex

            #Retrieve VNFRs from message
            vnfrs = msg["vnfrList"]
            ## Store vnfrs in the repository and add vnfr ids to nsr if it is not already present
            if ('vnfr' not in nsr):
                nsr['vnfr'] = []
            for vnfr in vnfrs:
                if ('vnfr' not in nsr):
                    nsr['vnfr'].append(vnfr['id'])
                #Store the message, catch exception when time-out occurs
                try:
                    vnfr_response = requests.post(VNFR_REPOSITORY_URL + 'vnf-instances', data=yaml.dump(vnfr), headers={'Content-Type':'application/x-yaml'}, timeout=10.0)
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
                nsr_response = requests.post(NSR_REPOSITORY_URL + 'ns-instances', data=json.dumps(nsr), headers={'Content-Type':'application/json'}, timeout=10.0)
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
            
            if message_for_gk['error'] == {}:
                message_for_gk['error'] = None
                message_for_gk['status'] = 'Deployment completed'
                
        else:
            message_for_gk['error'] = {'request_status_from_IA' : request_status}

        #Inform the gk of the result.
        self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump(message_for_gk), correlation_id=self.service_requests_being_handled[properties.correlation_id]['original_corr_id'])
        #Delete service request from handling dictionary, as handling is completed.
        self.service_requests_being_handled.pop(properties.correlation_id, None)


    def on_ssm_registration(self, ch, method, properties, message):
        """
        This method registers a newly deployed SSM in the SLM.
        """        
        #A deployed ssm is registered in the list as a dictionary,  with the name as key (comparable with requested ssms) and the uuid (which is a platform variable) of the ssm as value.
        msg = yaml.load(message)
        if 'ssm_name' in msg.keys() and 'ssm_uuid' in msg.keys():
            self.deployed_ssms[msg['ssm_name']] = {'uuid':msg['ssm_uuid']}

        #The SLM needs to register on the topic on which the SSM will broadcast service graph updates. This can not be done with an async_call, since other plugins (monitoring) can trigger the SSM to do this.
        self.manoconn.register_notification_endpoint(self.on_new_service_graph_received,'ssm.scaling.' + msg['ssm_uuid'] + '.done')

def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
#    logging.getLogger("pika").setLevel(logging.DEBUG)
    # create our service lifecycle manager
    ServiceLifecycleManager()

if __name__ == '__main__':
    main()
