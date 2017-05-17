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
import os
import requests
import copy
import uuid
import json
import threading
import sys
import concurrent.futures as pool
#import psutil

from sonmanobase.plugin import ManoBasePlugin
try:
    from son_mano_slm import slm_helpers as tools
except:
    import slm_helpers as tools

try:
    from son_mano_slm import slm_helpers_old as oldtools
except:
    import slm_helpers_old as oldtools

try:
    from son_mano_slm import slm_topics as t
except:
    import slm_topics as t

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:slm")
LOG.setLevel(logging.INFO)

# Declaration of topics, to be removed after transition
# To new SLM is completed

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
#NSR_REPOSITORY_URL = os.environ.get("url_nsr_repository")
#VNFR_REPOSITORY_URL = os.environ.get("url_vnfr_repository")

# Monitoring repository, can be accessed throught a RESTful
# API. Link is red from ENV variable.


class ServiceLifecycleManager(ManoBasePlugin):
    """
    This class implements the service lifecycle manager.
    """

    def __init__(self,
                 auto_register=True,
                 wait_for_registration=True,
                 start_running=True):
        """
        Initialize class and son-mano-base.plugin.BasePlugin class.
        This will automatically connect to the broker, contact the
        plugin manager, and self-register this plugin to the plugin
        manager.

        After the connection and registration procedures are done, the
        'on_lifecycle_start' method is called.
        :return:
        """

        # Create the ledger that saves state
        self.services = {}

        #The frequency of state sharing events
        self.state_share_frequency = 1

        # Create a configuration dict that contains config info of SLM
        # Setting the number of SLMs and the rank of this SLM
        self.slm_config = {}
        self.slm_config['slm_rank'] = 0
        self.slm_config['slm_total'] = 1
        self.slm_config['old_slm_rank'] = 0
        self.slm_config['old_slm_total'] = 1
        self.slm_config['tasks_other_slm'] = {}

        # Create the list of known other SLMs
        self.known_slms = []

        self.thrd_pool = pool.ThreadPoolExecutor(max_workers=10)

        # Create some flags that will be used for SLM management
        self.bufferAllRequests = False
        self.bufferOldRequests = False
        self.deltaTnew = 1
        self.deltaTold = 1

        self.old_reqs = {}
        self.new_reqs = {}

        self.flm_ledger = {}

        # The following can be removed once transition is done
        self.service_requests_being_handled = {}
        self.service_updates_being_handled = {}

        # call super class (will automatically connect to
        # broker and register the SLM to the plugin manger)
        ver = "0.1-dev"
        des = "This is the SLM plugin"

        super(self.__class__, self).__init__(version=ver, 
                                             description=des,                  
                                             auto_register=auto_register,
                                             wait_for_registration=wait_for_registration,
                                             start_running=start_running)

    def __del__(self):
        """
        Destroy SLM instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics that SLM subscribes on.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()

        # The topic on which deploy requests are posted.
        self.manoconn.subscribe(self.service_instance_create, t.GK_CREATE)

        # The topic on which pause requests are posted.
        self.manoconn.subscribe(self.service_instance_pause, t.GK_PAUSE)

        # The topic on which resume requests are posted.
        self.manoconn.subscribe(self.service_instance_resume, t.GK_RESUME)

        # The topic on which termination requests are posted.
        self.manoconn.subscribe(self.service_instance_kill, t.GK_KILL)

        # The topic on which SLMs share state with eachother
        self.manoconn.subscribe(self.inter_slm, t.MANO_STATE)

        # The topic on which update requests are posted.
        self.manoconn.subscribe(self.service_update, t.GK_UPDATE)

        # The topic on which plugin status info is shared
        self.manoconn.subscribe(self.plugin_status, t.PL_STATUS)

        # The topic on which the FLM receives deploy request from SLM
        self.manoconn.subscribe(self.flm_deploy, t.MANO_DEPLOY)

        # The topic on which monitoring information is received
        self.manoconn.subscribe(self.monitoring_feedback, t.MON_RECEIVE)

        # To be removed when transition to new SLM is completed
        self.manoconn.register_async_endpoint(
            self.on_gk_service_update,
            GK_INSTANCE_UPDATE)

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
        LOG.info("SLM started and operational")

    def deregister(self):
        """
        Send a deregister request to the plugin manager.
        """
        LOG.info('Deregistering SLM with uuid ' + str(self.uuid))
        message = {"uuid": self.uuid}
        self.manoconn.notify("platform.management.plugin.deregister",
                            json.dumps(message))
        os._exit(0)

    def on_registration_ok(self):
        """
        This method is called when the SLM is registered to the plugin mananger
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")

        # This SLM is currently the only known SLM
        self.known_slms.append(str(self.uuid))


##########################
# SLM Threading management
##########################


    def get_ledger(self, serv_id):

        return self.services[serv_id] 

    def get_services(self):

        return self.services

    def set_services(self, service_dict):

        self.services = service_dict

        return

    def error_handling(self, serv_id, topic, message):

        self.services[serv_id]['kill_chain'] = True

        message = {'error': message,
                   'timestamp': time.time(),
                   'status': 'ERROR'}

        corr_id = self.services[serv_id]['original_corr_id']
        self.manoconn.notify(topic, 
                             yaml.dump(message), 
                             correlation_id=corr_id)

        return

    def start_next_task(self, serv_id):
        """
        This method makes sure that the next task in the schedule is started
        when a task is finished, or when the first task should begin.

        :param serv_id: the instance uuid of the service that is being handled.
        :param first: indicates whether this is the first task in a chain.
        """

        # If the kill field is active, the chain is killed
        if self.services[serv_id]['kill_chain']:
            LOG.info("Killing workflow with id: " + serv_id)
            #TODO: delete SSMs, already deployed fucntions, records, stop monitoring
            #TODO: Or, jump into the kill workflow.
            del self.services[serv_id]
            return

        # Select the next task, only if task list is not empty
        if len(self.services[serv_id]['schedule']) > 0:

            #share state with other SLMs
            next_task = getattr(self, self.services[serv_id]['schedule'].pop(0))

            # Push the next task to the threadingpool
            task = self.thrd_pool.submit(next_task, serv_id)

            # Log the result of the task, for future reference
#            new_log = [next_task, task.result()]
#            self.services[serv_id]['task_log'].append(new_log)

            # Log if a task fails
            if task.exception() is not None:
                print(task.result())

#            if tasknumber % (1 / self.state_share_frequency) == 0:
#                self.slm_share('IN PROGRESS', self.services[serv_id])

            # When the task is done, the next task should be started if no flag
            # is set to pause the chain.
            if self.services[serv_id]['pause_chain']:
                self.services[serv_id]['pause_chain'] = False
            else:
                self.start_next_task(serv_id)


        else:
            #share state with other SLMs
            self.slm_share('DONE', self.services[serv_id])

            del self.services[serv_id]

####################
# SLM input - output
####################

    def plugin_status(self, ch, method, properties, payload):
        """
        This method is called when the plugin manager broadcasts new
        information on the plugins.
        """
        #TODO: needs unit testing

        message = yaml.load(payload)

        # If the plugin configuration has changed, it needs to be checked
        # whether the number of SLMs has changed.
        self.update_slm_configuration(message['plugin_dict'])

    def slm_down(self):
        """
        This method is called when this SLM notices that another SLM
        has gone missing. This SLM needs to determine whether it should
        take over unfinished tasks from this SLM.
        """
        #TODO: needs unit testing

        for serv_id in self.slm_config['tasks_other_slm'].keys():

            # TODO: only take over when ID's match
            LOG.info('SLM down, taking over requests')
            self.services[serv_id] = self.slm_config['tasks_other_slm'][serv_id]

            if 'schedule' not in self.services[serv_id].keys():
                del self.services[serv_id]
                ch = self.slm_config['tasks_other_slm'][serv_id]['ch']
                method = self.slm_config['tasks_other_slm'][serv_id]['method']
                properties = self.slm_config['tasks_other_slm'][serv_id]['properties']
                payload = self.slm_config['tasks_other_slm'][serv_id]['payload']

                self.service_instance_create(ch, method, properties, payload)

            else:
                self.start_next_task(serv_id)

        self.slm_config['tasks_other_slm'] = {}

    def inter_slm(self, ch, method, properties, payload):
        """
        This method handles messages that are shared between different SLMs.
        """
        #TODO: needs unit testing

        msg = yaml.load(payload)

        if msg['slm_id'] != str(self.uuid):

            if msg['status'] == 'DONE':
                if (str(msg['corr_id'])) in self.slm_config['tasks_other_slm'].keys():
                    del self.slm_config['tasks_other_slm'][str(msg['corr_id'])]

            if msg['status'] == 'IN PROGRESS':
                self.slm_config['tasks_other_slm'][str(msg['corr_id'])] = msg['state']


    def service_instance_create(self, ch, method, properties, payload):
        """
        This function handles a received message on the *.instance.create
        topic.
        """

        # Check if the messages comes from the GK or is forward by another SLM
        message_from_gk = True
        if properties.app_id == self.name:
            message_from_gk = False     
            if properties.reply_to is None:
                return
        
        # Bypass for backwards compatibility, to be removed after transition 
        # to new version of SLM is completed
        message = yaml.load(payload)
        # if 'NSD' in message.keys():
        #     if message['NSD']['descriptor_version'] == '1.0':
        #         response = self.on_gk_service_instance_create(ch, method, properties, payload)
        #         self.manoconn.notify(GK_INSTANCE_CREATE_TOPIC, response, correlation_id=properties.correlation_id)

        # Extract the correlation id and generate a reduced id
        corr_id = properties.correlation_id
        reduced_id = tools.convert_corr_id(corr_id) 

        # If the message comes from another SLM, check if the request has made
        # a round trip
        if not message_from_gk:
            roundtrip = (reduced_id % self.slm_config['slm_total'] == self.slm_config['slm_rank'])

            if roundtrip:
                # If the message made a round trip, a new SLM should be started
                # as this implies that the resources are exhausted 
                deploy_new_slm()

            else:
                # TODO: check if this SLM has the resources for this request
                has_enough_resources = True
                if has_enough_resources:
                    pass
                else:
                    # TODO: forward to next SLM
                    return

        # Start handling the request
        message = yaml.load(payload)

        # Add the service to the ledger
        serv_id = self.add_service_to_ledger(message, corr_id)

        # Schedule the tasks that the SLM should do for this request.
        add_schedule = []
        
        add_schedule.append('validate_deploy_request')
        add_schedule.append('contact_gk')

        #Onboard and instantiate the SSMs, if required.
        if self.services[serv_id]['service']['ssm'] != None:
           add_schedule.append('onboard_ssms')
           add_schedule.append('instant_ssms')

        if self.services[serv_id]['service']['ssm'] != None:
            if 'task' in self.services[serv_id]['service']['ssm'].keys():
                add_schedule.append('trigger_task_ssm')

        add_schedule.append('request_topology')

        #Perform the placement
        if self.services[serv_id]['service']['ssm'] is None:
            add_schedule.append('SLM_mapping')
        else:
            if 'placement' in self.services[serv_id]['service']['ssm'].keys():
                add_schedule.append('req_placement_from_ssm')
            else:
                add_schedule.append('SLM_mapping')

        add_schedule.append('ia_prepare')
        add_schedule.append('vnf_deploy')
        add_schedule.append('vnf_chain')
        add_schedule.append('store_nsr')
        add_schedule.append('wan_configure')
        add_schedule.append('start_monitoring')
        add_schedule.append('inform_gk')


        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info("New instantiation request received. Instantiation started.")
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def service_instance_pause(self, ch, method, prop, payload):

        pass

    def service_instance_resume(self, ch, method, prop, payload):

        pass

    def service_instance_kill(self, ch, method, prop, payload):
        """
        This function handles a received message on the *.instance.kill
        topic.
        """

        # Check if the messages comes from the GK or is forward by another SLM
        message_from_gk = True
        if prop.app_id == self.name:
            message_from_gk = False     
            if properties.reply_to is None:
                return

        content = yaml.load(payload)
        serv_id = content['instance_id']
        LOG.info("Termination request received for service " + str(serv_id))

        # Check if the ledger has an entry for this instance, as this method can
        # be called from multiple paths
        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Recreating ledger.")
            self.recreate_ledger(prop.correlation_id, serv_id)

        # Schedule the tasks that the SLM should do for this request.
        add_schedule = []

        add_schedule.append("stop_monitoring")
        add_schedule.append("wan_deconfigure")
        add_schedule.append("vnf_unchain")
        add_schedule.append("terminate_service")
        add_schedule.append("terminate_ssms")
        add_schedule.append("terminate_fsms")
        add_schedule.append("update_records")
        add_schedule.append("inform_gk")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info("Termination workflow started for service " + str(serv_id))
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def service_update(self, ch, method, prop, payload):

        pass

    def monitoring_feedback(self, ch, method, prop, payload):

        LOG.info("Monitoring message received")
        LOG.info(payload)

    def resp_topo(self, ch, method, prop, payload):
        """
        This function handles responses to topology requests made to the
        infrastructure adaptor.
        """
        message = yaml.load(payload)

        LOG.info("Topology received from IA.")
        LOG.debug("Requested info on topology: " + str(message))

        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        # Add topology to ledger
        self.services[serv_id]['infrastructure']['topology'] = message

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)


    def resp_onboard(self, ch, method, prop, payload): 
        """
        This function handles responses to a request to onboard the ssms
        of a new service.
        """
        LOG.info("Onboarding response received from SMR.")
        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        message = yaml.load(payload)

        if message['error'] is None:
            LOG.info("SSMs onboarded succesfully")
        else:
            LOG.info("SSM onboarding failed: " + response['error'])
            self.error_handling(serv_id, t.GK_CREATE, message['error'])

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_instant(self, ch, method, prop, payload):
        """
        This function handles responses to a request to onboard the ssms
        of a new service.
        """
        LOG.info("Instantiating response received from SMR.")

        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        message = yaml.load(payload)
        for ssm_type in self.services[serv_id]['service']['ssm'].keys():
            ssm = self.services[serv_id]['service']['ssm'][ssm_type]
            response = message[ssm['id']]
            ssm['instantiated'] = False
            if response['error'] is None:
                LOG.info("SSM instantiated correctly.")
                ssm['instantiated'] = True
            else:
                LOG.info("SSM instantiation failed: " + response['error'])
                self.error_handling(serv_id, t.GK_CREATE, response['error'])

            ssm['uuid'] = response['uuid']

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_task(self, ch, method, prop, payload):
        """
        This method handles updates of the task schedule by the an SSM.
        """
        #TODO: Test this method

        LOG.info("Response from task ssm: " + payload)

        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        message = yaml.load(payload)
        self.services[serv_id]['schedule'] = message['schedule']

        LOG.info("New taskschedule: " + str(self.services[serv_id]['schedule']))

        # # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_place(self, ch, method, prop, payload):
        """
        This method handles a placement performed by an SSM.
        """
        #TODO: Test this method

        LOG.info(payload)
        message = yaml.load(payload)

        is_dict = isinstance(message, dict)
        LOG.info("Type Dict: " + str(is_dict))

        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        mapping = message['mapping']
        error = message['error']

        if error != None:
            self.error_handling(serv_id, t.GK_CREATE, error)
            
        else:
            # Add mapping to ledger
            LOG.info("Calculated SSM mapping: " + str(mapping))
            self.services[serv_id]['service']['mapping'] = mapping
            for function in self.services[serv_id]['function']:
                vnf_id = function['id']
                function['vim_uuid'] = mapping[vnf_id]['vim']

        self.start_next_task(serv_id)

    def resp_ssm_configure(self, ch, method, prop, payload):
        """
        This method handles an ssm configuration response
        """
        #TODO: Test this method

        LOG.info(payload)
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)
        self.start_next_task(serv_id)

    def resp_vnf_depl(self, ch, method, prop, payload):
        """
        This method handles a response from the FLM to a vnf deploy request.
        """
        LOG.info('Message received from FLM on VNF deploy call.')
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        #Inform GK if VNF deployment failed
        if message['error'] != None:

            LOG.info("Deployment of VNF failed")
            LOG.debug("Message: " + str(message))
            self.error_handling(serv_id, t.GK_CREATE, message['error'])

        else:
            LOG.info("VNF correctly Deployed.")
            for function in self.services[serv_id]['function']:
                if function['id'] == message['vnfr']['id']:
                    function['vnfr'] = message['vnfr']
                    LOG.info("Added vnfr for instance: " + message['vnfr']['id'])
                
        vnfs_to_depl = self.services[serv_id]['vnfs_to_deploy'] - 1 
        self.services[serv_id]['vnfs_to_deploy'] = vnfs_to_depl

        # Only continue if all vnfs are deployed
        if vnfs_to_depl == 0:
            self.services[serv_id]['act_corr_id'] = None
            self.start_next_task(serv_id)

    def resp_prepare(self, ch, method, prop, payload):
        """
        This method handles a response to a prepare request.
        """
        # Retrieve the service uuid
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        response = yaml.load(payload)
        LOG.debug("Response from IA on .prepare call: " + str(response))

        if response['request_status'] == "COMPLETED":
            LOG.info("Message from IA: Infrastructure prepared")
        else:
            LOG.info("Error occured while preparing vims, aborting workflow")
            self.error_handling(serv_id, t.GK_CREATE, response['message'])

        self.start_next_task(serv_id)


    def contact_gk(self, serv_id):
        """
        This method handles communication towards the gatekeeper.`

        :param serv_id: the instance uuid of the service
        """

        # Get the correlation_id for the message
        corr_id = self.services[serv_id]['original_corr_id']

        #Build the message for the GK
        message = {}
        message['status'] = self.services[serv_id]['status']
        message['error'] = self.services[serv_id]['error']
        message['timestamp'] = time.time()

        if 'add_content' in self.services[serv_id].keys():
            message.update(self.services[serv_id]['add_content'])

        payload = yaml.dump(message)
        self.manoconn.notify(t.GK_CREATE, payload, correlation_id=corr_id)

    def request_topology(self, serv_id):
        """
        This method is used to request the topology of the available
        infrastructure from the Infrastructure Adaptor.

        :param serv_id: The instance uuid of the service
        """

        # Generate correlation_id for the call, for future reference
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        self.manoconn.call_async(self.resp_topo,
                                 t.IA_TOPO,
                                 None,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

        LOG.info("Topology requested from IA.")

    def ia_prepare(self, serv_id):
        """
        This method informs the IA which PoPs will be used and which
        type the image will be (by linking the image)

        :param serv_id: The instance uuid of the service
        """

        LOG.info("Requesting IA to prepare the infrastructure.")
        # Build mapping message for IA
        IA_mapping = {}

        # Add the service instance uuid
        IA_mapping['instance_id'] = serv_id

        # Create the VIM list
        IA_mapping['vim_list'] = []

        # Add the vnfs
        for function in self.services[serv_id]['function']:
            vim_uuid = function['vim_uuid']

            #Add VIM uuid if new
            new_vim = True
            for vim in IA_mapping['vim_list']:
                if vim['uuid'] == vim_uuid:
                    new_vim = False
                    index = IA_mapping['vim_list'].index(vim)

            if new_vim:
                IA_mapping['vim_list'].append({'uuid': vim_uuid, 'vm_images': []})
                index = len(IA_mapping['vim_list']) - 1

            for vdu in function['vnfd']['virtual_deployment_units']:
                url = vdu['vm_image']
                vm_uuid = tools.generate_image_uuid(vdu, function['vnfd'])

                IA_mapping['vim_list'][index]['vm_images'].append({'image_uuid': vm_uuid,'image_url': url})


        # Add correlation id to the ledger for future reference
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        # Send this mapping to the IA
        self.manoconn.call_async(self.resp_prepare,
                                 t.IA_PREPARE,
                                 yaml.dump(IA_mapping),
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def vnf_deploy(self, serv_id):
        """
        This method triggeres the deployment of all the vnfs.
        """

        functions = self.services[serv_id]['function']
        self.services[serv_id]['vnfs_to_deploy'] = len(functions)

        self.services[serv_id]['act_corr_id'] = []

        for function in functions:

            corr_id = str(uuid.uuid4())
            self.services[serv_id]['act_corr_id'].append(corr_id)

            message = function
            message['service_id'] = serv_id

            LOG.info("Requesting the deployment of vnf " + function['id'])
            LOG.debug("Payload of request: " + str(message))
            self.manoconn.call_async(self.resp_vnf_depl,
                                     t.MANO_DEPLOY, 
                                     yaml.dump(message), 
                                     correlation_id=corr_id)

        self.services[serv_id]['pause_chain'] = True


    def onboard_ssms(self, serv_id):
        """
        This method instructs the ssm registry manager to onboard the
        required SSMs.

        :param serv_id: The instance uuid of the service
        """

        corr_id = str(uuid.uuid4())
        # Sending the NSD to the SRM triggers it to onboard the ssms
        msg = {}
        msg['NSD'] = self.services[serv_id]['service']['nsd']
        msg['VNFD'] = []
        for function in self.services[serv_id]['function']:
            msg['VNFD'].append(function['vnfd'])

        pyld = yaml.dump(msg)
        self.manoconn.call_async(self.resp_onboard,
                                 t.SRM_ONBOARD,
                                 pyld,
                                 correlation_id=corr_id)

        # Add correlation id to the ledger for future reference
        self.services[serv_id]['act_corr_id'] = corr_id

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

        LOG.info("SSM on-boarding trigger sent to SMR.")

    def instant_ssms(self, serv_id):
        """
        This method instructs the ssm registry manager to instantiate the
        required SSMs.

        :param serv_id: The instance uuid of the service
        :param ssm_id: which ssm you want to deploy
        """

        corr_id = str(uuid.uuid4())        
        # Sending the NSD to the SRM triggers it to instantiate the ssms

        msg = {}
        msg['NSD'] = self.services[serv_id]['service']['nsd']
        msg['UUID'] = serv_id
        
        LOG.info("Keys in message for SSM instantiation: " + str(msg.keys()))
        pyld = yaml.dump(msg)

        self.manoconn.call_async(self.resp_instant,
                                 t.SRM_INSTANT,
                                 pyld,
                                 correlation_id=corr_id)

        # Add correlation id to the ledger for future reference
        self.services[serv_id]['act_corr_id'] = corr_id

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

        LOG.info("SSM instantiation trigger sent to SMR")

    def trigger_task_ssm(self, serv_id):
        """
        This method contacts the master SSM and allows it to update
        the task schedule.

        :param serv_id: the instance uuid of the service
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        # Select the master SSM and create topic to reach it on
        ssm_id = self.services[serv_id]['service']['ssm']['task']['uuid']
        topic = "task.ssm." + str(serv_id)

        # Adding the schedule to the message
        message = {'schedule': self.services[serv_id]['schedule']}

        # Contact SSM
        payload = yaml.dump(message)
        self.manoconn.call_async(self.resp_task,
                                 topic,
                                 payload,
                                 correlation_id=corr_id)

        LOG.info("task registered on " + str(topic))

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def req_placement_from_ssm(self, serv_id):
        """
        This method requests the placement by an ssm.

        :param serv_id: The instance uuid of the service.
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        #Check if placement SSM is available
        ssm_place = self.services[serv_id]['service']['ssm']['placement']
        #If not available, fall back on SLM placement
        if ssm_place['instantiated'] == False:
            return self.SLM_mapping(serv_id)         
        # build message for placement SSM
        nsd = self.services[serv_id]['service']['nsd']
        top = self.services[serv_id]['infrastructure']['topology']

        vnfds = []
        for function in self.services[serv_id]['function']:
            vnfd_to_add = function['vnfd']
            vnfd_to_add['instance_uuid'] = function['id']
            vnfds.append(function['vnfd'])

        message = {'nsd': nsd, 'topology': top, 'uuid': serv_id, 'vnfds': vnfds}

        # Contact SSM
        payload = yaml.dump(message)

        LOG.info("Placement requested from SSM: " + str(message.keys()))

        self.manoconn.call_async(self.resp_place,
                                 t.EXEC_PLACE,
                                 payload,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def configure_ssm(self, serv_id):
        """
        This method contacts a configuration ssm with the descriptors
        and the records if they are available.

        :param serv_id: The instance uuid of the service.
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        if self.services[serv_id]['service']['ssm']['configure'] is None:
            LOG.info("Configuration SSM requested but not available")
            return

        if not self.services[serv_id]['service']['ssm']['configure']['instantiated']:
            LOG.info("Configuration SSM not instantiated")
            return

        # Building the content message for the configuration ssm
        content = {'service': self.services[serv_id]['service'],
                   'functions': self.services[serv_id]['function']}

        payload = yaml.dump(content)
        ssm_id = self.services[serv_id]['service']['ssm']['configure']['uuid']
        topic = "configure.ssm." + str(serv_id)
        self.manoconn.call_async(self.resp_ssm_configure,
                                 topic,
                                 payload,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True


    def slm_share(self, status, content):

        message = {'status':status, 'state':content, 'corr_id': content['original_corr_id'], 'slm_id': self.uuid}
        payload = yaml.dump(message)
        self.manoconn.notify('mano.inter.slm', payload)

    def flm_deploy(self, ch, method, prop, payload):
        """
        This methods fakes the FLM by handling requests from the SLM to dpeloy
        a specific function
        """

        message = yaml.load(payload)

        if 'vnfd' in message.keys():

            outg_message = {}
            outg_message['vnfd'] = message['vnfd']
            outg_message['vnfd']['instance_uuid'] = message['id']
            outg_message['vim_uuid'] = message['vim_uuid']
            outg_message['service_instance_id'] = message['service_id']

            payload = yaml.dump(outg_message)

            corr_id = str(uuid.uuid4())
            #adding the vnfd to the flm ledger
            self.flm_ledger[corr_id] = {}
            self.flm_ledger[corr_id]['vnfd'] = message['vnfd']
            self.flm_ledger[corr_id]['orig_corr_id'] = prop.correlation_id

            LOG.info("VNF deployment request from fake FLM to IA.")
            LOG.debug("Payload of request: " + payload)
            # Contact the IA
            self.manoconn.call_async(self.IA_deploy_response,
                                     t.IA_DEPLOY,
                                     payload,
                                     correlation_id=corr_id)

    def IA_deploy_response(self, ch, method, prop, payload):
        """
        This method fakes the FLMs reaction to a IA response.
        """

        # When the IA responses, the FLM builds the record and then 
        # forwards this to the SLM.
        LOG.info("IA reply to fake FLM on VNF deploy call")
        LOG.debug("Payload of request: " + str(payload))

        inc_message = yaml.load(payload)

        # Build the message for the SLM
        outg_message = {}
        outg_message['status'] = inc_message['request_status']

        # Getting vnfd from the FLM ledger
        vnfd = self.flm_ledger[prop.correlation_id]['vnfd']

        error = None
        if inc_message['message'] != '':
            error = inc_message['message']

        if inc_message['request_status'] == "COMPLETED":

            # Build the record
            vnfr = tools.build_vnfr(inc_message['vnfr'], vnfd)
            outg_message['vnfr'] = vnfr      

            # Store the record
#            try:
            vnfr_response = requests.post(t.VNFR_REPOSITORY_URL + 'vnf-instances', data=yaml.dump(vnfr), headers={'Content-Type':'application/x-yaml'}, timeout=1.0)
            LOG.info("Storing VNFR on " + str(t.VNFR_REPOSITORY_URL + 'vnf-instances'))
            LOG.debug("VNFR: " + str(vnfr))

            if (vnfr_response.status_code == 200):
                LOG.info("VNFR storage accepted.")
                outg_message['vnfr'] = vnfr
            #If storage fails, add error code and message to rply to gk
            else:
                error = {'http_code': vnfr_response.status_code, 'message': vnfr_response.json()}
                LOG.info('vnfr to repo failed: ' + str(error))
            # except:
            #     error = {'http_code': '0', 'message': 'Timeout when contacting VNFR server'}
            #     LOG.info('time-out on vnfr to repo')

        outg_message['error'] = error
        outg_message['inst_id'] = vnfd['instance_uuid']

        self.manoconn.notify(t.MANO_DEPLOY,
                             yaml.dump(outg_message),
                             correlation_id=self.flm_ledger[prop.correlation_id]['orig_corr_id'])    

    def store_nsr(self, serv_id):

        #TODO: get request_status from response from IA on chain
        request_status = 'normal operation'

        nsd = self.services[serv_id]['service']['nsd']

        vnfr_ids = []
        for function in self.services[serv_id]['function']:
            vnfr_ids.append(function['id'])

        nsr = tools.build_nsr(request_status, nsd, vnfr_ids, serv_id)
        LOG.debug("NSR to be stored: " + yaml.dump(nsr))

        error = None

        try:
            header = {'Content-Type':'application/json'}
            nsr_resp = requests.post(t.NSR_REPOSITORY_URL + 'ns-instances',
                                     data=json.dumps(nsr), 
                                     headers=header,
                                     timeout=1.0)
            nsr_resp_json = nsr_resp.json()
            if (nsr_resp.status_code == 200):
                LOG.info("NSR accepted and stored for instance " + serv_id)
            else:
                LOG.info('NSR not accepted: ' + str(nsr_resp_json))
                error = {'http_code': nsr_resp.status_code, 
                         'message': nsr_resp_json}
        except:
            error = {'http_code': '0', 
                     'message': 'Timeout when contacting NSR repo'}

        self.services[serv_id]['service']['nsr'] = nsr

        if error != None:
            self.error_handling(serv_id, t.GK_CREATE, error)

        return

    def vnf_chain(self, serv_id):
        """
        This method instructs the IA how to chain the functions together.        
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        chain = {}
        chain["service_instance_id"] = serv_id
        chain["nsd"] = self.services[serv_id]['service']['nsd']

        vnfrs = []
        vnfds = []

        for function in self.services[serv_id]['function']:
            vnfrs.append(function['vnfr'])

            vnfd = function['vnfd']
            vnfd['instance_uuid'] = function['id']
            vnfds.append(vnfd)

        chain['vnfrs'] = vnfrs
        chain['vnfds'] = vnfds

        self.manoconn.call_async(self.IA_chain_response,
                                 t.IA_CONF_CHAIN,
                                 yaml.dump(chain),
                                 correlation_id=corr_id)

        LOG.info("Requested the Chaining of the VNFs.")
        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def IA_chain_response(self, ch, method, prop, payload):
        """
        This method handles the IA response to the chain request
        """
        # Get the serv_id of this service
        serv_id = tools.serv_id_from_corr_id(self.services, 
                                             prop.correlation_id)

        message = yaml.load(payload)

        LOG.info("Chaining request completed.")

        if message['message'] != '':
            error = message['message']
            LOG.info('Error occured during chaining: ' + str(error))
            self.error_handling(serv_id, t.GK_CREATE, error)

        self.start_next_task(serv_id)

    def vnf_unchain(self, serv_id):
        """
        This method instructs the IA to unchain the functions in the service.        
        """
        LOG.info("Deconfiguring the chaining of the service")

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        payload = json.dumps({'service_instance_id':serv_id})
        self.manoconn.call_async(self.IA_termination_response,
                                t.IA_DECONF_CHAIN,
                                payload,
                                correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True


    def IA_unchain_response(self, ch, method, prop, payload):
        """
        This method handles the IA response on the unchain request
        """

        # Get the serv_id of this service
        serv_id = tools.serv_id_from_corr_id(self.services, 
                                             prop.correlation_id)

        message = yaml.load(payload)

        if message['request_status'] == 'COMPLETED':
            LOG.info("Response from IA: Service unchaining succeeded.")
        else:
            error = message['message']
            LOG.info("Response from IA: Service unchaining failed: " + error)
            self.error_handling(serv_id, t.GK_KILL, error)
            return

        self.start_next_task(serv_id)

    def terminate_service(self, serv_id):
        """
        This method requests the termination of a service to the IA
        """
        LOG.info('Requesting IA to terminate service')

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        payload = json.dumps({'instance_uuid':serv_id})
        self.manoconn.call_async(self.IA_termination_response,
                                t.IA_REMOVE,
                                payload,
                                correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True


    def IA_termination_response(self, ch, method, prop, payload):
        """
        This method handles the response from the IA on the termination call.
        """

        # Get the serv_id of this service
        serv_id = tools.serv_id_from_corr_id(self.services, 
                                             prop.correlation_id)

        message = yaml.load(payload)

        if message['request_status'] == 'COMPLETED':
            LOG.info("Response from IA: Service termination succeeded.")
        else:
            error = message['message']
            LOG.info("IA response: Service termination failed: " + error)
            self.error_handling(serv_id, t.GK_KILL, error)
            return

        self.start_next_task(serv_id)

    def terminate_ssms(self, serv_id):
        """
        This method contacts the SMR to terminate the running ssms.
        """
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        LOG.info("Setting termination flags for ssms.")

        nsd = self.services[serv_id]['service']['nsd']

        for ssm in nsd['service_specific_managers']:
            if 'options' not in ssm.keys():
                ssm['options'] = []
            ssm['options'].append({'key':'termination', 'value':'true'})

        LOG.info("SSM part of NSD: " + str(nsd['service_specific_managers']))

        payload = yaml.dump({'NSD':nsd})
        self.manoconn.call_async(self.ssm_termination_response,
                                t.SRM_UPDATE,
                                payload,
                                correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def ssm_termination_response(self, ch, method, prop, payload):
        """
        This method handles a response from the SMR on the ssm termination 
        call.
        """
        message = yaml.load(payload)
        LOG.info("Response from SMR: " + str(message))

        self.start_next_task(serv_id)

    def wan_configure(self, serv_id):
        """
        This method configures the WAN of a service
        """

        LOG.info("WAN Configuration")
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        message = {'service_instance_id':serv_id}

        # self.manoconn.call_async(self.wan_configure_response,
        #                          t.IA_CONF_WAN,
        #                          yaml.dump(message),
        #                          correlation_id=corr_id)

        # # Pause the chain of tasks to wait for response
        # self.services[serv_id]['pause_chain'] = True

    def wan_configure_response(self, ch, method, prop, payload):
        """
        This method handles the IA response to the WAN request
        """
        # Get the serv_id of this service
        serv_id = tools.serv_id_from_corr_id(self.services, prop.correlation_id)

        message = yaml.load(payload)
        self.services[serv_id]['status'] = message['status'] 
        self.services[serv_id]['error'] = None

        # TODO: handle negative status
        self.start_next_task(serv_id)

    def wan_deconfigure(self, serv_id):
        """
        This method will deconfigure the WAN
        """

        #TODO: when WIM implementation is finished

        pass

    def wan_deconfigure_response(self, ch, method, prop, payload):
        """
        This method handles responses on the wan_deconfigure call
        """

        #TODO: when WIM implementation is finished

        pass

    def stop_monitoring(self, serv_id):
        """
        This method stops the monitoring of a service.
        """

        url = t.MONITORING_URL + "services/" + serv_id
        LOG.info("Stopping Monitoring by sending on " + url)

        error = None
        try:
            header = {'Content-Type':'application/json'}
            mon_resp = requests.delete(url,
                                       headers=header,
                                       timeout=10.0)
            LOG.info('response from monitoring manager: ' + str(mon_resp))
            monitoring_json = mon_resp.json()

            if (mon_resp.status_code == 200):
                LOG.info('Monitoring delete message accepted')
    
            else:
                LOG.info('Monitoring delete message not accepted')
                LOG.info('Monitoring response: ' + str(monitoring_json))
                error = {'http_code': mon_resp.status_code,
                         'message': mon_resp.json()}

        except:
            LOG.info('timeout on monitoring communication.')
            error = {'http_code': '0', 
                     'message': 'Timeout when contacting monitoring manager'}

        #If an error occured, the workflow is aborted and the GK is informed
        if error != None:
            self.error_handling(serv_id, t.GK_KILL, error)

        return

    def start_monitoring(self, serv_id):
        """
        This method instructs the monitoring manager to start monitoring
        """

        LOG.info("Setting Monitoring")
        service = self.services[serv_id]['service']
        functions = self.services[serv_id]['function']

        mon_mess = tools.build_monitoring_message(service, functions)

        LOG.debug("Monitoring message created: " + yaml.dump(mon_mess))

        error = None
        try:
            header = {'Content-Type':'application/json'}
            mon_resp = requests.post(t.MONITORING_URL + 'service/new',
                                     data=json.dumps(mon_mess),
                                     headers=header,
                                     timeout=10.0)
            monitoring_json = mon_resp.json()

            if (mon_resp.status_code == 200):
                LOG.info('Monitoring message accepted')
    
            else:
                LOG.info('Monitoring message not accepted')
                LOG.info('Monitoring response: ' + str(monitoring_json))
                error = {'http_code': mon_resp.status_code,
                         'message': mon_resp.json()}

        except:
            LOG.info('timeout on monitoring communication.')
            error = {'http_code': '0', 
                     'message': 'Timeout when contacting server'}

        #If an error occured, the workflow is aborted and the GK is informed
        if error != None:
            self.error_handling(serv_id, t.GK_CREATE, error)

        return

    def inform_gk(self, serv_id):
        """
        This method informs the gatekeeper.
        """
        LOG.info("Reporting result to GK")

        message = {}

        message['status'] = 'READY'
        message['error'] = None
        message['timestamp'] = time.time()
        message['nsr'] = self.services[serv_id]['service']['nsr']
        message['vnfrs'] = []

        for function in self.services[serv_id]['function']:
            message['vnfrs'].append(function['vnfr'])


        # TODO: add the VNFRs

        self.manoconn.notify(t.GK_CREATE,
                             yaml.dump(message),
                             correlation_id=self.services[serv_id]['original_corr_id'])


###########
# SLM tasks
###########

    def add_service_to_ledger(self, payload, corr_id):
        """
        This method adds new services with their specifics to the ledger,
        so other functions can use this information.

        :param payload: the payload of the received message
        :param corr_id: the correlation id of the received message
        """

        # Generate an istance uuid for the service
        serv_id = str(uuid.uuid4())

        # Add the service to the ledger and add instance ids
        self.services[serv_id] = {}
        self.services[serv_id]['service'] = {}
        self.services[serv_id]['service']['nsd'] = payload['NSD']
        self.services[serv_id]['service']['id'] = serv_id

        self.services[serv_id]['function'] = []
        for key in payload.keys():
            if key[:4] == 'VNFD':
                vnf_id = str(uuid.uuid4())
                self.services[serv_id]['function'].append({'vnfd': payload[key], 'id':vnf_id})

        # Add to correlation id to the ledger
        self.services[serv_id]['original_corr_id'] = corr_id

        # Add payload to the ledger
        self.services[serv_id]['payload'] = payload

        self.services[serv_id]['infrastructure'] = {}

        # Create the service schedule
        self.services[serv_id]['schedule'] = []

        # Create a log for the task results
        self.services[serv_id]['task_log'] = []

        # Create the SSM dict if SSMs are defined in NSD
        ssm_dict = tools.get_ssm_from_nsd(payload['NSD'])
        self.services[serv_id]['service']['ssm'] = ssm_dict

        print(self.services[serv_id]['service']['ssm'])
                            
        # Create counter for vnfs
        self.services[serv_id]['vnfs_to_deploy'] = 0

        # Create the chain pause and kill flag

        self.services[serv_id]['pause_chain'] = False
        self.services[serv_id]['kill_chain'] = False

        return serv_id

    def recreate_ledger(self, corr_id, serv_id):
        """
        This method recreates an entry in the ledger for a service
        based on the service instance id.

        :param corr_id: the correlation id of the received message
        :param serv_id: the service instance id
        """

        def request_returned_with_error(request):
            code = str(request['error'])
            mess = str(request['content'])
            LOG.info("Retrieving of NSR failed: " + code + " " + mess)
            #TODO: get out of this

        self.services[serv_id] = {}
        self.services[serv_id]['original_corr_id'] = corr_id
        self.services[serv_id]['service'] = {}

        # Retrieve the service record based on the service instance id
        base = t.NSR_REPOSITORY_URL + "ns-instances/"
        request = tools.getRestData(base, serv_id)

        if request['error'] != None:
            request_returned_with_error(request)            
            return

        self.services[serv_id]['service']['nsr'] = request['content']
        LOG.info("Recreating ledger: NSR retrieved.")

        # Retrieve the NSD based on the service record
        nsr = self.services[serv_id]['service']['nsr']
        nsd_id = nsr['descriptor_reference']
        base = t.GK_SERVICES_URL
        LOG.info("Requesting nsd on url " + base)
        request = tools.getRestData(base, nsd_id)

        if request['error'] != None:
            request_returned_with_error(request)            
            return

        self.services[serv_id]['service']['nsd'] = request['content']['nsd']
        LOG.info("Recreating ledger: NSD retrieved.")
        LOG.info(request['content'])

        # Retrieve the function records based on the service record
        self.services[serv_id]['function'] = []
        nsr = self.services[serv_id]['service']['nsr']
        for vnf in nsr['network_functions']:
            base = t.VNFR_REPOSITORY_URL + "vnf-instances/" 
            request = tools.getRestData(base, vnf['vnfr_id'])

            if request['error'] != None:
                request_returned_with_error(request)            
                return

            new_function = {'id': vnf['vnfr_id'], 'vnfr': request['content']}
            self.services[serv_id]['function'].append(new_function)
            LOG.info("Recreating ledger: VNFR retrieved.")

        # Retrieve the VNFDS based on the function records
        for vnf in self.services[serv_id]['function']:
            vnfd_id = vnf['vnfr']['descriptor_reference']
            base = t.GK_FUNCTIONS_URL
            LOG.info(base + vnf['id'])
            request = tools.getRestData(base, vnfd_id)

            if request['error'] != None:
                request_returned_with_error(request)            
                return

            vnf['vnfd'] = request['content']
            LOG.info("Recreating ledger: VNFD retrieved.")
            LOG.info(request['content'])

        # Retrieve the deployed SSMs based on the NSD
        nsd = self.services[serv_id]['service']['nsd']
        ssm_dict = tools.get_ssm_from_nsd(nsd)

        self.services[serv_id]['service']['ssm'] = ssm_dict

        LOG.info('ssm_dict: ' + str(ssm_dict))

        # Retrieve the deployed FSMs based on the VNFD

        # Create the service schedule
        self.services[serv_id]['schedule'] = []

        # Create some necessary fields for the ledger
        self.services[serv_id]['kill_chain'] = False
        self.services[serv_id]['infrastructure'] = {}
        self.services[serv_id]['task_log'] = []
        self.services[serv_id]['vnfs_to_deploy'] = 0
        self.services[serv_id]['pause_chain'] = False

        return

    def validate_deploy_request(self, serv_id):
        """
        This metod checks the format of a received request. All neccesary
        fields should be present, and the available fields should not be
        conflicting with each other.

        :param serv_id: the instance id of the service
        """
        payload = self.services[serv_id]['payload']
        corr_id = self.services[serv_id]['original_corr_id']

        # TODO: check whether correlation_id is already being used.

        # The service request in the yaml file should be a dictionary
        if not isinstance(payload, dict):
            LOG.info("Validation of request completed. Status: Not a Dict")
            response = "Request " + corr_id + ": payload is not a dict."
            self.services[serv_id]['status'] = 'ERROR'
            self.services[serv_id]['error'] = response
            return

        # The dictionary should contain a 'NSD' key
        if 'NSD' not in payload.keys():
            LOG.info("Validation of request completed. Status: No NSD")
            response = "Request " + corr_id + ": NSD is not a dict."
            self.services[serv_id]['status'] = 'ERROR'
            self.services[serv_id]['error'] = response
            return

        # Their should be as many VNFD keys in the dictionary as their
        # are network functions listed to the NSD.
        number_of_vnfds = 0
        for key in payload.keys():
            if key[:4] == 'VNFD':
                number_of_vnfds = number_of_vnfds + 1

        if len(payload['NSD']['network_functions']) != number_of_vnfds:
            LOG.info("Validation of request completed. Status: Number of VNFDs incorrect")
            response = "Request " + corr_id + ": # of VNFDs doesn't match NSD."
            self.services[serv_id]['status'] = 'ERROR'
            self.services[serv_id]['error'] = response
            return

        # Check whether VNFDs are empty.
        for key in payload.keys():
            if key[:4] == 'VNFD':
                if payload[key] is None:
                    LOG.info("Validation of request completed. Status: Empty VNFD")
                    response = "Request " + corr_id + ": empty VNFD."
                    self.services[serv_id]['status'] = 'ERROR'
                    self.services[serv_id]['error'] = response
                    return

        LOG.info("Validation of request completed. Status: Instantiating")
        # If all tests succeed, the status changes to 'INSTANTIATING'
        message = {'status': 'INSTANTIATING', 'error': None}
        self.services[serv_id]['status'] = 'INSTANTIATING'
        self.services[serv_id]['error'] = None
        return

#        except Exception as e:
#            tracebackString = traceback.format_exc(e)
#            self.services[serv_id]['traceback'] = tracebackString

    def SLM_mapping(self, serv_id):
        """
        This method is used if the SLM is responsible for the placement.

        :param serv_id: The instance uuid of the service
        """

        LOG.info("Calculating the placement")
        topology = self.services[serv_id]['infrastructure']['topology']
        NSD = self.services[serv_id]['service']['nsd']
        functions = self.services[serv_id]['function']

        mapping = tools.placement(NSD, functions, topology)

        if mapping is None:
            # The GK should be informed that the placement failed and the
            # deployment was aborted.
            self.error_handling(serv_id, t.GK_CREATE, 'Unable to perform placement.')

        else:
            # Add mapping to ledger
            LOG.info("Placement calculations completed")
            LOG.debug("Calculated SLM placement: " + str(mapping))
            self.services[serv_id]['service']['mapping'] = mapping
            for function in self.services[serv_id]['function']:
                vnf_id = function['id']
                function['vim_uuid'] = mapping[vnf_id]['vim']

        return

    def update_slm_configuration(self, plugin_dict):
        """
        This method checks if an SLM was added or removed from the
        pool of SLMs. If it was, this method updates the configuration
        of the SLM.

        :param plugin_dict: Dictionary of plugins registered in plugin manager
        """

        active_slms = []

        # Substract information on the different SLMs from the dict
        for plugin_uuid in plugin_dict.keys():
#            print(plugin_dict[plugin_uuid]['name'])
            if plugin_dict[plugin_uuid]['name'] == self.name:
#                print('GOT HERE')
                active_slms.append(plugin_uuid)

        # Check if the list of active SLMs is identical to the known list
        active_slms.sort()
#        print('########')
#        print(active_slms)
#        print(self.known_slms)
        if active_slms == self.known_slms:
#            print('GOT HEREE')
            # No action te be taken
            return
        else:
            if self.uuid is None:
                for slm_uuid in active_slms:
                    if slm_uuid not in self.known_slms:
                        self.uuid = slm_uuid
            self.slm_config['old_slm_rank'] = self.slm_config['slm_rank']
            self.slm_config['old_slm_total'] = self.slm_config['slm_total']
            self.slm_config['slm_rank'] = active_slms.index(str(self.uuid))
            self.slm_config['slm_total'] = len(active_slms)
            down = False
            if len(active_slms) < len(self.known_slms):
                down = True

            self.known_slms = active_slms
            # Buffer incoming requests
#            self.bufferAllRequests = True
            # Wait some time to allow different SLMs to get on the same pages
#            time.sleep(self.deltaTnew)
            # Start handling the buffered requests in the new regime
#            self.bufferOldRequests = True
#            self.bufferAllRequests = False

#            for req in self.new_reqs:
#                task = self.thrd_pool.submit(req['mthd'], req['arguments'])

#            time.sleep(self.deltaTold)
            # Start handling the buffered requests from the old regime
#            self.bufferOldRequests = False

#            for req in self.old_reqs:
#                task = self.thrd_pool.submit(req['mthd'], req['arguments'])

            if down:
                self.slm_down()


    ###: Below the old functionality of the SLM. To be removed once transition is done.


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

        nsr['status'] = 'updating'
        try:
            nsr['id'] = nsr['uuid']
        except:
            pass
        nsr['version'] = str(int(nsr['version']) + 1)
        
        #create corr_id for interation with SMR to use as reference one response is received.
        corr_id = str(uuid.uuid4())
        #keep track of running updates, so we can update the records after the response is received.
        self.service_updates_being_handled[corr_id] = {'nsd':request['NSD'], 'nsr':nsr, 'instance_id':request['Instance_id'], 'orig_corr_id':properties.correlation_id, 'vnfrs':vnfr_dict}

        #Change status of NSR to updating.
        second_nsr_dict = {}

        #remove fields that SLM is not allowed to set.
        for key in nsr.keys():  
            if key not in ['uuid', 'created_at', 'updated_at']:
                second_nsr_dict[key] = nsr[key]

#        try:
        link_for_put = NSR_REPOSITORY_URL + 'ns-instances/' + str(request['Instance_id'])
        LOG.info("making put request to change status of NSR to updating")
        nsr_response = requests.put(link_for_put, data=json.dumps(second_nsr_dict), headers={'Content-Type':'application/json'}, timeout=10.0)
        
        if nsr_response.status_code is not 200:
            LOG.info('nsr updated failed, request denied.')
            message = {'status':'ERROR', 'error':'could not update records.'}
            return yaml.dump(message)

        LOG.info(nsr_response.json())
     
#        except:
#            message = {'status':'ERROR', 'error':'time-out on storing the record.'}
#            return yaml.dump(message)
            

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
        message_from_srm = yaml.load(message)

        LOG.info('Update report received from SMR, updating the records...')
        LOG.info('Response from SMR: ' + yaml.dump(message, indent=4))

        if message_from_srm['status'] == 'Updated':
            message_from_srm['status'] = 'UPDATE_COMPLETED'
            #updating the records. As only the nsr changes in the demo, we only update the nsr for now.
            nsr = self.service_updates_being_handled[properties.correlation_id]['nsr']
            instance_id = self.service_updates_being_handled[properties.correlation_id]['instance_id']
            nsd = self.service_updates_being_handled[properties.correlation_id]['nsd']

            nsr['version'] = str(int(nsr['version']) + 1)
            nsr['descriptor_reference'] = nsd['uuid']
            nsr['status'] = 'normal operation'
            #id can be stored as 'id' or 'uuid'
            try:
                nsr['id'] = nsr['uuid']
            except:
                pass

            second_nsr_dict = {}

            #remove fields that SLM is not allowed to set.
            for key in nsr.keys():  
                if key not in ['uuid', 'created_at', 'updated_at']:
                    second_nsr_dict[key] = nsr[key]

            try:
                nsr_response = requests.put(NSR_REPOSITORY_URL + 'ns-instances/' + str(instance_id), data=json.dumps(second_nsr_dict), headers={'Content-Type':'application/json'}, timeout=10.0)
                
                if nsr_response.status_code is not 200:
                    message = {'status':'ERROR', 'error':'could not update records.'}
                    self.manoconn.notify(GK_INSTANCE_UPDATE, yaml.dump(message), correlation_id=self.service_updates_being_handled[properties.correlation_id]['orig_corr_id']) 
                    return       
            except:
                message = {'status':'ERROR', 'error':'time-out on storing the record.'}
                self.manoconn.notify(GK_INSTANCE_UPDATE, yaml.dump(message), correlation_id=self.service_updates_being_handled[properties.correlation_id]['orig_corr_id']) 
                return       
            
            message_from_srm['nsr'] = second_nsr_dict
            LOG.info('Records updated.')

        LOG.info('Reporting back to GK.')
        message_for_gk = message_from_srm
        #The SLM just takes the message from the SMR and forwards it towards the GK
        self.manoconn.notify(GK_INSTANCE_UPDATE, yaml.dump(message_for_gk), correlation_id=self.service_updates_being_handled[properties.correlation_id]['orig_corr_id'])        

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
        new_corr_id, self.service_requests_being_handled = oldtools.replace_old_corr_id_by_new(self.service_requests_being_handled, properties.correlation_id)
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

        request = oldtools.build_message_for_IA(self.service_requests_being_handled[correlation_id])
        LOG.info('Request message for IA built: ' + yaml.dump(request, indent=4))
        #In the service_requests_being_handled dictionary, we replace the old corr_id with the new one, to be able to keep track of the request
        new_corr_id, self.service_requests_being_handled = oldtools.replace_old_corr_id_by_new(self.service_requests_being_handled, correlation_id)
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
            nsr = oldtools.build_nsr(self.service_requests_being_handled[properties.correlation_id], msg)
            LOG.info('nsr built: ' + yaml.dump(nsr, indent=4))
            #Retrieve VNFRs from message and translate
            vnfrs = oldtools.build_vnfrs(self.service_requests_being_handled[properties.correlation_id], msg['vnfrs'])
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
            monitoring_message = oldtools.build_monitoring_message(self.service_requests_being_handled[properties.correlation_id], msg, nsr, vnfrs)
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
    slm = ServiceLifecycleManager()

if __name__ == '__main__':
    main()
