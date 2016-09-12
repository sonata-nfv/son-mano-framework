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
This is SONATA's service lifecycle management plugin
"""

import logging
import yaml
import time
import requests
import uuid
import threading
import json
import os

from sonmanobase.plugin import ManoBasePlugin
try:
    from son_mano_slm import slm_helpers as tools
except:
    import slm_helpers as tools

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:slm")
LOG.setLevel(logging.DEBUG)

#
# Configurations
#
# The topic to which service instantiation requests
# of the GK are published
GK_INSTANCE_CREATE_TOPIC = "service.instances.create"

GK_INSTANCE_UPDATE = 'service.instances.update'

# The topic to which service instance deploy replies
# of the Infrastructure Adaptor are published
INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC = "infrastructure.service.deploy"

# The topic to which available vims are published
INFRA_ADAPTOR_AVAILABLE_VIMS = 'infrastructure.management.compute.list'

# Topics for interaction with the specific manager registry 
SRM_ONBOARD = 'specific.manager.registry.ssm.on-board'
SRM_START = 'specific.manager.registry.ssm.instantiate'
SRM_UPDATE = 'specific.manager.registry.ssm.update'

# The NSR Repository can be accessed through a RESTful
# API. Links are red from ENV variables.
NSR_REPOSITORY_URL = os.environ.get("url_nsr_repository")
VNFR_REPOSITORY_URL = os.environ.get("url_vnfr_repository")

# Monitoring repository, can be accessed throught a RESTful
# API. Link is red from ENV variable.
MONITORING_REPOSITORY_URL = os.environ.get("url_monitoring_server")


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
        self.service_requests_being_handled = {}
        self.service_updates_being_handled = {}

        # call super class (will automatically connect to
        # broker and register the SLM to the plugin manger)
        super(self.__class__, self).__init__(version="0.1-dev", description="This is the SLM plugin")

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
        # We want to subscribe SERVICE.INSTANCE.CREATE to react on GK messages
        self.manoconn.register_async_endpoint(
            self.on_gk_service_instance_create, # function called when message received
            GK_INSTANCE_CREATE_TOPIC)           # topic to listen to

        self.manoconn.register_async_endpoint(
            self.on_gk_service_update,
            GK_INSTANCE_UPDATE)

    def on_lifecycle_start(self, ch, method, properties, message):
        """
        This event is called when the plugin has successfully registered itself
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

        LOG.info("Message received on service.instances.create corr_id: " + str(properties.correlation_id))

        #The request data is in the message as a yaml file,
        #and should be constructed like:
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

        LOG.info("Checking whether request payload is formatted correctly.")
        # The request should not have a correlation_id that is already being
        # used by a different request path/track
        for prop_id in self.service_requests_being_handled.keys():
            if properties.correlation_id in self.service_requests_being_handled[prop_id]['original_corr_id']:
                LOG.info("Request has correlation_id that is already in use.")
                return yaml.dump({'status'   : 'ERROR',
                                  'error'    : 'Correlation_id is already in use, please make sure to generate a new one.',
                                  'timestamp': time.time()})

        # The service request in the yaml file should be a dictionary
        if not isinstance(service_request_from_gk, dict):
            LOG.info("service request with corr_id " + properties.correlation_id + "rejected: Message is not a dictionary.")
            return yaml.dump({'status'   : 'ERROR',
                              'error'    : 'Message is not a dictionary',
                              'timestamp': time.time()})

        # The dictionary should contain a 'NSD' key
        if 'NSD' not in service_request_from_gk.keys():
            LOG.info("service request with corr_id " + properties.correlation_id + "rejected: NSD is not a dictionary.")
            return yaml.dump({'status'   : 'ERROR',
                              'error'    : 'No NSD field in dictionary',
                              'timestamp': time.time()})

        # Their should be as many VNFDx keys in the dictionary as their
        # are network functions according to the NSD.
        number_of_vnfds = 0
        for key in service_request_from_gk.keys():
            if key[:4] == 'VNFD':
                number_of_vnfds = number_of_vnfds + 1

        if len(service_request_from_gk['NSD']['network_functions']) != number_of_vnfds:
            LOG.info("service request with corr_id " + properties.correlation_id + "rejected: number of vnfds does not match nsd.")

            return yaml.dump({'status'   : 'ERROR',
                              'error'    : 'Number of VNFDs doesn\'t match number of vnfs',
                              'timestamp': time.time()})

        #Check whether a vnfd is none.
        for key in service_request_from_gk.keys():
            if key[:4] == 'VNFD':
                if service_request_from_gk[key] is None:
                    return yaml.dump({'status'   : 'ERROR',
                                      'error'    : 'VNFDs are not allowed to be empty',
                                      'timestamp': time.time()})

        LOG.info("Request payload is formatted correctly, proceeding...")

        #If all checks on the received message pass, an uuid is created for
        #the service, and we add it to the dict of services being deployed.
        #Each VNF also gets an uuid. This is added to the VNFD dictionary.
        #The correlation_id is used as key for this dict, since it should
        #be available in all the callback functions.
        self.service_requests_being_handled[properties.correlation_id] = service_request_from_gk

        #Since the key will change when new async calls are being made
        #(each new call needs a unique corr_id), we need to keep track
        #of the original one to reply to the GK at a later stage.
        self.service_requests_being_handled[properties.correlation_id]['original_corr_id'] = properties.correlation_id

        self.service_requests_being_handled[properties.correlation_id]['NSD']['instance_uuid'] = str(uuid.uuid4())
        LOG.info("instance uuid for service generated: " + self.service_requests_being_handled[properties.correlation_id]['NSD']['instance_uuid'])

        for key in service_request_from_gk.keys():
            if key[:4] == 'VNFD':
                self.service_requests_being_handled[properties.correlation_id][key]['instance_uuid'] = str(uuid.uuid4())
                LOG.info("instance uuid for vnf <" + key + "> generated: " + self.service_requests_being_handled[properties.correlation_id][key]['instance_uuid'])

	    #SSM handling: if NSD has service_specific_managers field,
	    #then SLM contacts the SMR with this NSD.
        #'ssms_ready_to_start' is set to false. This flag is used
        #To make sure that both the ssm onboarding is finished and
        #the service deployed before the ssm start trigger is made.
        if 'service_specific_managers' in service_request_from_gk['NSD'].keys():
            if len(service_request_from_gk['NSD']['service_specific_managers']) > 0:
                LOG.info('SSMs needed for this service, trigger on-boarding process in SMR.')
                corr_id_for_onboarding = str(uuid.uuid4())
                self.service_requests_being_handled[properties.correlation_id]['corr_id_for_onboarding'] = corr_id_for_onboarding
                self.manoconn.call_async(self.on_ssm_onboarding_return, SRM_ONBOARD, yaml.dump(service_request_from_gk['NSD']), correlation_id=corr_id_for_onboarding)
                self.service_requests_being_handled[properties.correlation_id]['ssms_ready_to_start'] = False

        #After the received request has been processed, we can start
        #handling it in a different thread.
        LOG.info('Starting deployment of new service.')
        t = threading.Thread(target=self.start_new_service_deployment, args=(ch, method, properties, message))
        t.daemon = True
        t.start()

        response_for_gk = {'status'  : 'INSTANTIATING', # INSTANTIATING or ERROR
                          'error'    : None,            # NULL or a string describing the ERROR
                          'timestamp': time.time()}     # time() returns the number of seconds since the epoch in UTC as a float      

        LOG.info('Response from SLM to GK on request: ' + str(response_for_gk))
        return yaml.dump(response_for_gk)

    def on_gk_service_update(self, ch, method, properties, message):
        """
        This method handles a service update request
        """

        request = yaml.load(message)
        LOG.info('Update request received for instance ' + request['Instance_id'])

        #get nsr from repository
        appendix_nsr_link = 'ns-instances/' + request['Instance_id']
        nsr_response = requests.get(NSR_REPOSITORY_URL + appendix_nsr_link, timeout=10.0)

        if (nsr_response.status_code == 200):
            LOG.info("NSR retrieved successfully")
            nsr = nsr_response.json()

            #get the vnfrs from repository
            vnfrs = [] 
            vnfr_dict = {}           
            for vnfr_obj in nsr['network_functions']:
                vnfr_id = vnfr_obj['vnfr_id']
                vnfr_response = requests.get(VNFR_REPOSITORY_URL + 'vnf-instances/' + vnfr_id, timeout=10.0)
                
                if (vnfr_response.status_code == 200):
                    vnfr = vnfr_response.json()
                    vnfrs.append(vnfr)
                    vnfr_dict[vnfr_id] = vnfr

                else:
                    LOG.info('retrieving vnfr failed, aborting...')
                    error_message = {'status':'ERROR', 'error':'Updating failed, could not retrieve vnfr.'}
                    return yaml.dump(error_message)
        else:
            LOG.info('retrieving nsr failed, aborting...')
            error_message = {'status':'ERROR', 'error':'Updating failed, could not retrieve nsr.'}
            return yaml.dump(error_message)
        
        #create corr_id for interation with SMR to use as reference one response is received.
        corr_id = str(uuid.uuid4())
        #keep track of running updates, so we can update the records after the response is received.
        self.service_updates_being_handled[corr_id] = {'nsd':request['NSD'], 'nsr':nsr, 'instance_id':request['Instance_id'], 'orig_corr_id':properties.correlation_id, 'vnfrs':vnfr_dict}

        #Build request for SMR
        LOG.info('retrieving nsr and vnfrs succeeded, building message for SMR...')
        request_for_smr = {'NSD':request['NSD'], 'NSR':nsr, 'VNFR':vnfrs}
        self.manoconn.call_async(self.on_update_request_reply, SRM_UPDATE, yaml.dump(request_for_smr), correlation_id=corr_id)
        LOG.info('SMR contacted, awaiting response...')

        response_for_gk = {'status':'UPDATING', 'error':None}
        LOG.info('Inform GK that update process is started.')        
        return yaml.dump(response_for_gk)

    def on_update_request_reply(self, ch, method, properties, message):
        """
        This method handles a response of the SMR on an update request
        """

        LOG.info('Update report received from SMR, updating the records...')
        LOG.info('Response from SMR: ' + yaml.dump(message, indent=4))
        #updating the records. As only the nsr changes in the demo, we only update the nsr for now.
        nsr = self.service_updates_being_handled[properties.correlation_id]['nsr']
        instance_id = self.service_updates_being_handled[properties.correlation_id]['instance_id']
        nsd = self.service_updates_being_handled[properties.correlation_id]['nsd']

        nsr['version'] = str(int(nsr['version']) + 1)
        nsr['descriptor_reference'] = nsd['uuid']

        nsr_response = requests.put(NSR_REPOSITORY_URL + 'ns-instances/' + instance_id, data=json.dumps(nsr), headers={'Content-Type':'application/json'}, timeout=10.0)
        
        if nsr_response.status_code is not 200:
            message = {'status':'ERROR', 'error':'could not update records.'}
            self.manoconn.notify(GK_INSTANCE_UPDATE, message, correlation_id=self.service_updates_being_handled[instance_id]['orig_corr_id']) 
            return       

        LOG.info('Records updated, informing the gatekeeper of result.')
        message_for_gk = {'status':'UPDATE_COMPLETED', 'error':None, 'nsr':nsr}
        #The SLM just takes the message from the SMR and forwards it towards the GK
        self.manoconn.notify(GK_INSTANCE_UPDATE, yaml.dump(message_for_gk), correlation_id=self.service_updates_being_handled[instance_id]['orig_corr_id'])        

    def on_ssm_onboarding_return(self, ch, method, properties, message):
        """
        This method catches a reply on the ssm onboarding topic
        """

        LOG.info("Response from SRM regarding on-boarding received.")

        for service_request in self.service_requests_being_handled:
            service_request = self.service_requests_being_handled[service_request]
            #Check which service the response relates to.
            if 'corr_id_for_onboarding' in service_request.keys():
                if service_request['corr_id_for_onboarding'] == properties.correlation_id:
                    #If service deployment is finished, the ssm start can be triggered.
                    if service_request['ssms_ready_to_start'] == True:
                        LOG.info("Request to start SSMs sent.")
                        self.manoconn.call_async(self.on_ssm_start_return, SRM_START, yaml.dump(service_request['message_for_srm']))
                        self.service.requests_being_handled.pop(service_request)
                        break
                    #If service deployment is not finished, this sets a flag to state
                    #that onboarding is finished.
                    else:
                        LOG.info("Request to start SSMs is pending, waiting for service deployement to finish.")
                        service_request['ssms_ready_to_start'] = True
                        break
                        

    def start_new_service_deployment(self, ch, method, properties, message):
        """
        This method initiates the deployment of a new service
        """

        LOG.info("VIM list requested from IA, to facilitate service with uuid " + self.service_requests_being_handled[properties.correlation_id]['NSD']['instance_uuid'])
        #First, we need to request a list of the available vims, in order
        #to choose one to place the service on. This is done by sending
        #a message with an empty body on the infrastructure.management.
        #resource.list topic.
        new_corr_id, self.service_requests_being_handled = tools.replace_old_corr_id_by_new(self.service_requests_being_handled, properties.correlation_id)
        self.manoconn.call_async(self.start_vim_selection, INFRA_ADAPTOR_AVAILABLE_VIMS, None, correlation_id=new_corr_id)

    def start_vim_selection(self, ch, method, properties, message):
        """
        This method manages the decision of which vim the service is going to be placed on.
        """
        #For now, we will go through the vims in the list and check if they have enough resources for the service. Once we find such a vim, we stick with this one.
        #TODO: Outsource this process to an SSM if there is one available.

        vimList = yaml.load(message)
        LOG.info("VIM list received: " + yaml.dump(vimList, indent=4))

        if not isinstance(vimList, list):
            self.inform_gk_with_error(properties.correlation_id, error_msg='No VIM.')
            return
        if len(vimList) == 0:
            self.inform_gk_with_error(properties.correlation_id, error_msg='No VIM.')
            return

        #TODO: If an SSM needs to select the vim, this is where to trigger it. Currently, an internal method is handling the decision.
        #For now, we take the first one in the list, and just store the vim_uuid
        self.service_requests_being_handled[properties.correlation_id]['vim'] = vimList[0]['vim_uuid']
        LOG.info("VIM selected: " + yaml.dump(self.service_requests_being_handled[properties.correlation_id]['vim'], indent=4))

        self.request_deployment_from_IA(properties.correlation_id)

    def inform_gk_with_error(self, correlation_id, error_msg=None):
        """
        This method informs the gk that no vim has the resources neede to deploy this service.
        """

        LOG.info("Inform GK of Error for service with instance uuid " + self.service_requests_being_handled[correlation_id]['NSD']['instance_uuid'])
        response_message = {'status':'ERROR', 'error': error_msg, 'timestamp': time.time()}
        self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump(response_message), correlation_id=self.service_requests_being_handled[correlation_id]['original_corr_id'])


    def request_deployment_from_IA(self, correlation_id):
        """
        This method is triggered once a vim is selected to place the service on.
        """

        request = tools.build_message_for_IA(self.service_requests_being_handled[correlation_id])
        LOG.info('Request message for IA built: ' + yaml.dump(request, indent=4))
        #In the service_requests_being_handled dictionary, we replace the old corr_id with the new one, to be able to keep track of the request
        new_corr_id, self.service_requests_being_handled = tools.replace_old_corr_id_by_new(self.service_requests_being_handled, correlation_id)
        LOG.info('Contacting the IA on infrastructure.service.deploy.')
        self.manoconn.call_async(self.on_infra_adaptor_service_deploy_reply,
                                 INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC,
                                 yaml.dump(request),
                                 correlation_id=new_corr_id)

    def on_infra_adaptor_service_deploy_reply(self, ch, method, properties, message):
        """
        This method is called when the Infrastructure Adaptor replies to a service deploy request from the SLM.
        Based on the content of the reply message, the NSR has to be contacted.
        The GK should be notified of the result of the service request.
        """

        LOG.info("Deployment reply received from IA for instance uuid " + self.service_requests_being_handled[properties.correlation_id]['NSD']['instance_uuid'])

        msg = yaml.load(message)

        LOG.info("Response from IA: " + yaml.dump(msg, indent=4))
        #The message that will be returned to the gk
        message_for_gk = {}
        message_for_gk['status'] = 'ERROR'
        message_for_gk['error'] = {}
        message_for_gk['vnfrs'] = []

        message_for_gk['timestamp'] = time.time()

        if msg['request_status'][:8] == 'DEPLOYED':
            nsr = tools.build_nsr(self.service_requests_being_handled[properties.correlation_id], msg)
            LOG.info('nsr built: ' + yaml.dump(nsr, indent=4))
            #Retrieve VNFRs from message and translate
            vnfrs = tools.build_vnfrs(self.service_requests_being_handled[properties.correlation_id], msg['vnfrs'])
            LOG.info('vnfrs built: ' + yaml.dump(vnfrs, indent=4))
            ## Store vnfrs in the repository and add vnfr ids to nsr if it is not already present
            for vnfr in vnfrs:
                #Store the message, catch exception when time-out occurs
                try:
                    vnfr_response = requests.post(VNFR_REPOSITORY_URL + 'vnf-instances', data=yaml.dump(vnfr), headers={'Content-Type':'application/x-yaml'}, timeout=10.0)
                    #If storage succeeds, add vnfr to reply to gk
                    if (vnfr_response.status_code == 200):
                        message_for_gk['vnfrs'].append(vnfr)
                    #If storage fails, add error code and message to rply to gk
                        LOG.info('repo response for vnfr: ' + str(vnfr_response))
                    else:
                        message_for_gk['error']['vnfr'] = {'http_code': vnfr_response.status_code, 'message': vnfr_response.json()}
                        LOG.info('vnfr to repo failed: ' + str(message_for_gk['error']['vnfr']))
                        break
                except:
                    message_for_gk['error']['vnfr'] = {'http_code': '0', 'message': 'Timeout when contacting server'}
                    LOG.info('time-out on vnfr to repo')

                    break

            #Store nsr in the repository, catch exception when time-out occurs
            try:
                nsr_response = requests.post(NSR_REPOSITORY_URL + 'ns-instances', data=json.dumps(nsr), headers={'Content-Type':'application/json'}, timeout=10.0)
                if (nsr_response.status_code == 200):
                    LOG.info('repo response for nsr: ' + str(nsr_response))
                    message_for_gk['nsr'] = nsr

                else:
                    message_for_gk['error']['nsr'] = {'http_code': nsr_response.status_code, 'message': nsr_response.json()}
                    LOG.info('nsr to repo failed: ' + str(message_for_gk['error']['nsr']))
            except:
                message_for_gk['error']['nsr'] = {'http_code': '0', 'message': 'Timeout when contacting server'}

            #TODO: put this in an if clause, so it is only done when nsr and
            #vnfrs are accepted by repository.
            LOG.info('nsr and vnfrs stored in Repositories, starting montitoring process.')
            monitoring_message = tools.build_monitoring_message(self.service_requests_being_handled[properties.correlation_id], msg, nsr, vnfrs)
            LOG.info('Monitoring message built: ' + json.dumps(monitoring_message, indent=4))

            try:
                monitoring_response = requests.post(MONITORING_REPOSITORY_URL + 'service/new', data=json.dumps(monitoring_message), headers={'Content-Type':'application/json'}, timeout=10.0)

                if (monitoring_response.status_code == 200):
                    LOG.info('Monitoring response: ' + str(monitoring_response))
                    monitoring_json = monitoring_response.json()
                    LOG.info('Monitoring json: ' + str(monitoring_json))
        
                    if ('status' not in monitoring_json.keys()) or (monitoring_json['status'] != 'success'):
                        message_for_gk['error']['monitoring'] = monitoring_json

                else:
                    message_for_gk['error']['monitoring'] = {'http_code': monitoring_response.status_code, 'message': monitoring_response.json()}

            except:
                message_for_gk['error']['monitoring'] = {'http_code': '0', 'message': 'Timeout when contacting server'}
                LOG.info('time-out on monitoring manager.')


            #If no errors occured, return message fields are set accordingly 
            #And SRM is informed to start ssms if needed.
            self.service_requests_being_handled[properties.correlation_id]['completed'] = True
            if message_for_gk['error'] == {}:
                message_for_gk['status'] = 'READY'
                message_for_gk['error'] = None

                #Check if SSMs must be started with this service
                if 'service_specific_managers' in self.service_requests_being_handled[properties.correlation_id]['NSD'].keys():
                    if len(self.service_requests_being_handled[properties.correlation_id]['NSD']['service_specific_managers']) > 0:
                        dict_for_srm = {'NSD':self.service_requests_being_handled[properties.correlation_id]['NSD'], 'NSR':nsr}
                        #If onboarding is finished, the ssm start trigger can be sent.
                        if self.service_requests_being_handled[properties.correlation_id]['ssms_ready_to_start'] == True:   
                            LOG.info("Informing SRM that SSMs can be started.")                                             
                            self.manoconn.call_async(self.on_ssm_start_return, SRM_START, yaml.dump(dict_for_srm))
                        #If onboarding is not finished, this sets a flag so that when onboarding is finished, they can trigger ssm start.
                        else:
                            LOG.info("service deployement completed. Waiting for SSM onboarding to finish so SSMs can be started.")
                            self.service_requests_being_handled[properties.correlation_id]['ssms_ready_to_start'] = True
                            self.service_requests_being_handled[properties.correlation_id]['completed'] = False
                            self.service_requests_being_handled[properties.correlation_id]['message_for_srm'] = dict_for_srm

        else:
            LOG.info("inform gk of result of deployment for service with uuid " + self.service_requests_being_handled[properties.correlation_id]['NSD']['instance_uuid'])
            LOG.info("Message for gk: " + yaml.dump(message_for_gk, indent=4))
            message_for_gk['error'] = 'Deployment result: ' + msg['request_status']
            self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump(message_for_gk), correlation_id=self.service_requests_being_handled[properties.correlation_id]['original_corr_id'])
            return

        #Inform the gk of the result.
        LOG.info("inform gk of result of deployment for service with uuid " + self.service_requests_being_handled[properties.correlation_id]['NSD']['instance_uuid'])
        LOG.info("Message for gk: " + yaml.dump(message_for_gk, indent=4))
        self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, yaml.dump(message_for_gk), correlation_id=self.service_requests_being_handled[properties.correlation_id]['original_corr_id'])
        #Delete service request from handling dictionary, as handling is completed.
        if self.service_requests_being_handled[properties.correlation_id]['completed']:
            self.service_requests_being_handled.pop(properties.correlation_id, None)

    def on_ssm_start_return(self, ch, method, properties, message):
        """
        This method handles responses from the srm.management.start topic
        """        

        pass

def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
#    logging.getLogger("amqp-storm").setLevel(logging.DEBUG)
    # create our service lifecycle manager
    ServiceLifecycleManager()

if __name__ == '__main__':
    main()
