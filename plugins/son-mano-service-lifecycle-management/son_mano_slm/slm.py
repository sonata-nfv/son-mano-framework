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
import json
import sys
import concurrent.futures as pool
import slm_topics as t
import slm_helpers as h
import psutil

from sonmanobase.plugin import ManoBasePlugin
try:
    from son_mano_slm import slm_helpers as tools
except:
    import slm_helpers as tools

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:slm")
LOG.setLevel(logging.DEBUG)


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

        # Create the ledger
        self.services = {}

        # Create a configuration dict that contains config info of SLM
        # Setting the number of SLMs and the rank of this SLM
        self.slm_config = {}
        self.slm_config['slm_rank'] = 0
        self.slm_config['slm_total'] = 1
        self.slm_config['old_slm_rank'] = 0
        self.slm_config['old_slm_total'] = 1

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

        # The following can be removed once transition is done
        self.service_requests_being_handled = {}
        self.service_updates_being_handled = {}

        # call super class (will automatically connect to
        # broker and register the SLM to the plugin manger)
        ver = "0.1-dev"
        des = "This is the SLM plugin"
        super(self.__class__, self).__init__(version=ver, description=des)

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

        # Subscription to service deploy requests.
        self.manoconn.subscribe(self.pre1_service_instance_create,
                                t.GK_CREATE)

        # Subscription to service update requests.
        self.manoconn.register_async_endpoint(
            self.on_gk_service_update,
            t.GK_INSTANCE_UPDATE)

        # Subscription to plugin status information
        self.manoconn.subscribe(self.plugin_status,
        						t.PL_STATUS)

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

    def on_registration_ok(self):
        """
        This method is called when the SLM is registered to the plugin mananger
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")

        # This SLM is currently the only known SLM
        self.known_slms.append(str(self.uuid))

        topic = str(self.uuid) + 'service.instance.create'

        self.manoconn.subscribe(self.pre2_service_instance_create, topic)


##########################
# SLM Threading management
##########################

    def start_next_task(self, serv_id):
        """
        This method makes sure that the next task in the schedule is started
        when a task is finished, or when the first task should begin.

        :param serv_id: the instance uuid of the service that is being handled.
        :param first: indicates whether this is the first task in a chain.
        """

        # Select the next task, only if task list is not empty
        if len(self.services[serv_id]['schedule']) > 0:
            next_task = self.services[serv_id]['schedule'].pop(0)

            # Push the next task to the threadingpool
            task = self.thrd_pool.submit(next_task, serv_id)

            # Log the result of the task, for future reference
            new_log = [next_task, task.result()]
            self.services[serv_id]['task_log'].append(new_log)

            # Log if a task fails
            if task.exception() is not None:
                print(task.result())

            # When the task is done, the next task should be started if no flag
            # is set to pause the chain.
            if not self.services[serv_id]['pause_chain']:
                self.start_next_task(serv_id)

            self.services[serv_id]['pause_chain'] = False

####################
# SLM input - output
####################

    def plugin_status(self, ch, method, properties, payload):
        """
        This method is called when the plugin manager broadcasts new
        information on the plugins.
        """

        message = yaml.load(payload)

        # If the plugin configuration has changed, it needs to be checked
        # whether the number of SLMs has changed.
        self.update_slm_configuration(message['plugin_dict'])


    def pre1_service_instance_create(self, ch, method, properties, payload):
        """
        This function handles a received message on the service.instance.create
        topic. It determines what to do with this request: handle it, buffer it
        or discard it.
        """

        # Don't trigger on message originating from this plugin
        if properties.app_id == self.name:
            return

        # Convert the uuid into an integer that can be used for distributed
        # load balancing through the use of the modulo operator
        corr_id = properties.correlation_id
        reduced_id = self.convert_corr_id(corr_id) 

        # Check if the request should be handled by this SLM in the current,
        # or in the old regime
        cur_reg = (reduced_id % self.slm_config['slm_total'] == self.slm_config['slm_rank'])
        old_reg = (reduced_id % self.slm_config['old_slm_total'] == self.slm_config['old_slm_rank'])

        # If this request is not handled by this SLM, discard it
        if not (cur_reg or old_reg):
            return

        # If the SLM is in a buffering state, store it
        if self.bufferAllRequests:
            arguments = ch, method, properties, payload
            if cur_reg:
                self.new_reqs[corr_id] = {'mthd': self.service_instance_create,
                                          'arg': arguments}
                return
            else:
                self.old_reqs[corr_id] = {'mthd': self.service_instance_create,
                                          'arg': arguments}
                return

        if self.bufferOldRequests:
            arguments = ch, method, properties, payload
            self.old_reqs[corr_id] = {'mthd': self.service_instance_create,
                                      'arg': arguments}
            return

        # If the request should not be handled by this SLM in the current 
        # regime, it is discarded.
        if not cur_reg:
            return

        # If the SLM is not in a buffer state, and the request should be
        # handled by this SLM, the request can be handled.
        self.service_instance_create(ch, method, properties, payload)

    def pre2_service_instance_create(self, ch, method, properties, payload):
        """
        This function handles forwarded requests that other SLMs received on
        the service.instance.create topic, but couldn't handle due to exhausted
        resources, after which they forwarded it to this SLM.
        """

#        print("RECEIVED FORWARD: " + str(properties.correlation_id))
        # Check if this request has made a round trip. If it was forwarded
        # through all the active SLMs, all SLM resources are exhausted and
        # a new SLM should be deployed.
        corr_id = properties.correlation_id
        reduced_id = self.convert_corr_id(corr_id) 

        cur_reg = (reduced_id % self.slm_config['slm_total'] == self.slm_config['slm_rank'])

        #if cur_reg:
#            print('ROUNDTRIP')
            # TODO: deploy a new SLM. Until this functionality is added,
            # the SLM keeps handling the requests.
#            return

        # Start handling the request
        self.service_instance_create(ch, method, properties, payload)


    def service_instance_create(self, ch, method, properties, payload):
        """
        This function handles a received message on the service.instance.create
        topic.
        """

        # If the resources of this SLM are exhausted, forward the request to 
        # another SLM.
        cpu = psutil.cpu_percent()

        if cpu > 80.0:
            #Forward the request towards the following SLM in the list
            print("FORWARDING: " + str(properties.correlation_id))
            own_slm_rank = self.slm_config['slm_rank']
            next_slm_rank = (own_slm_rank + 1) % self.slm_config['slm_total']
            next_slm_uuid = self.known_slms[next_slm_rank]
            topic = str(next_slm_uuid) + 'service.instance.create'

            self.manoconn.notify(topic,
                                 payload,
                                 correlation_id=properties.correlation_id)

            return


        # Converting the request into a set of tasks.
        message = yaml.load(payload)
        corr_id = properties.correlation_id

        # Add the service to the ledger
        serv_id = self.add_service_to_ledger(message, corr_id)

        # Schedule the tasks that the SLM should do for this request.
        add_schedule = []
        add_schedule.append(self.validate_deploy_request)
        add_schedule.append(self.contact_gk)

        if 'service_specific_managers' in self.services[serv_id]['NSD']:
            add_schedule.append(self.onboard_ssms)
            add_schedule.append(self.instant_ssms)
            add_schedule.append(self.trigger_master_ssm)

        add_schedule.append(self.request_topology)
        add_schedule.append(self.placement)

        add_schedule.append(self.req_vnfs_deployment)

        add_schedule.append(self.dummy)

        self.services[serv_id]['schedule'].extend(add_schedule)

        # Start the chain of tasks
        self.start_next_task(serv_id)

    def resp_topo(self, ch, method, prop, payload):
        """
        This function handles responses to topology requests made to the
        infrastructure adaptor.
        """

        message = yaml.load(payload)
#        print(message)
#        print(prop.correlation_id)
#        print(prop.app_id)

        # Retrieve the service uuid
        serv_id = h.serv_id_from_corr_id(self.services, prop.correlation_id)

        # Add topology to ledger
        self.services[serv_id]['topology'] = message['topology']

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_onboard(self, ch, method, prop, payload):
        """
        This function handles responses to a request to onboard the ssms
        of a new service.
        """

        # Retrieve the service uuid
        serv_id = h.serv_id_from_corr_id(self.services, prop.correlation_id)

        message = yaml.load(payload)

        # TODO: What to do if onboarding fails?

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_instant(self, ch, method, prop, payload):
        """
        This function handles responses to a request to onboard the ssms
        of a new service.
        """

        # Retrieve the service uuid
        serv_id = h.serv_id_from_corr_id(self.services, prop.correlation_id)

        message = yaml.load(payload)

        # TODO: What to do inf instantiation of SSM fails?
        # TODO: SRM should respond with a list of SSM uuids, so the SLM
        # knows which topics to use to contact the SSMs

        self.services[serv_id]['SSMs'] = [message['uuid']]

        # Add SSM uuids to ledger with their names.
        ssm_list = self.services[serv_id]['NSD']['service_specific_managers']

        for i in range(0, len(ssm_list)):
            self.services[serv_id]['SSMs'][ssm_list[i]['id']] = message[i]

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_task(self, ch, method, prop, payload):
        """
        This method handles updates of the task schedule by the an SSM.
        """

        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = h.serv_id_from_corr_id(self.services, prop.correlation_id)

        # Convert method string names into method pointers and add to ledger
        schedule = [getattr(self, x['task']) for x in message]
        self.services[serv_id]['schedule'] = schedule

        # Add attributes for these methods to the ledger.
        for task in message:
            if task['attributes'] != None:
                self.services[serv_id][task['task']] = task['attributes']

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_place(self, ch, method, prop, payload):
        """
        This method handles a placement performed by an SSM.
        """

        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = h.serv_id_from_corr_id(self.services, prop.correlation_id)

        # Add placement information to the ledger
        self.services[serv_id]['placement'] = message['placement']

        self.start_next_task(serv_id)

    def resp_vnf_depl(self, ch, method, prop, payload):
        """
        This method handles a response from the FLM to a vnf deploy request.
        """

        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = h.serv_id_from_corr_id(self.services, prop.correlation_id)

        
        # TODO: implement what to do if deployment failed
        # TODO: store the instance uuids of the vnfs for future reference

        vnfs_to_depl = self.services[serv_id]['vnfs_to_deploy'] - 1 
        self.services[serv_id]['vnfs_to_deploy'] = vnfs_to_depl

        # Only continue if all vnfs are deployed
        if vnfs_to_depl == 0:
            self.services[serv_id]['act_corr_id'] = None
            self.start_next_task(serv_id)

    def contact_gk(self, serv_id):
        """
        This method handles communication towards the gatekeeper.`

        :param serv_id: the instance uuid of the service
        """

        # Get the message for the gk
        message = self.services[serv_id]['msg_gk']

        # Get the correlation_id for the message
        corr_id = self.services[serv_id]['corr_id']

        # Add a timestamp to the message.
        message['timestamp'] = time.time()

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

    def onboard_ssms(self, serv_id):
        """
        This method instructs the ssm registry manager to onboard the
        required SSMs.

        :param serv_id: The instance uuid of the service
        """

        corr_id = str(uuid.uuid4())
        # Sending the NSD to the SRM triggers it to onboard the ssms
        pyld = yaml.dump(self.services[serv_id]['NSD'])
        self.manoconn.call_async(self.resp_onboard,
                                 t.SRM_ONBOARD,
                                 pyld,
                                 correlation_id=corr_id)

        # Add correlation id to the ledger for future reference
        self.services[serv_id]['act_corr_id'] = corr_id

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def instant_ssms(self, serv_id):
        """
        This method instructs the ssm registry manager to instantiate the
        required SSMs.

        :param serv_id: The instance uuid of the service
        """

        corr_id = str(uuid.uuid4())        
        # Instantiating all the SSMs by sending 'NSD' to the SRM
        # TODO: Is this the correct workflow? SRM already has 'NSD'
        # Maybe we should use another trigger.
        pyld = yaml.dump(self.services[serv_id]['NSD'])

        self.manoconn.call_async(self.resp_instant,
                                 t.SRM_INSTANT,
                                 pyld,
                                 correlation_id=corr_id)

        # Add correlation id to the ledger for future reference
        self.services[serv_id]['act_corr_id'] = corr_id

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def trigger_master_ssm(self, serv_id):
        """
        This method contacts the master SSM and allows it to update
        the task schedule.

        :param serv_id: the instance uuid of the service
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        # Select the master SSM and create topic to reach it on
        nsd = self.services[serv_id]['NSD']
        master_ssm = nsd['service_specific_managers'][0]['id']
        master_ssm_uuid = self.services[serv_id]['SSMs'][master_ssm]
        topic = 'ssm.management.' + str(master_ssm_uuid) + '.task'

        # Convert schedule of method pointers into list of method string names
        schedule_pointer = self.services[serv_id]['schedule']
        schedule_string = [x.__name__ for x in schedule_pointer]
        message = {'schedule': schedule_string}

        # Contact SSM
        payload = yaml.dump(message)
        self.manoconn.call_async(self.resp_task,
                                 topic,
                                 payload,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def req_placement_from_ssm(self, serv_id):
        """
        This method requests the placement by an ssm.

        :param serv_id: The instance uuid of the service.
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        # build message for placement SSM
        nsd = self.services[serv_id]['NSD']
        top = self.services[serv_id]['topology']
        message = {'NSD': nsd, 'Topology': top}

        # Create topic to reach placement SSM on. This topic is set
        # by the master ssm
        func_name = sys._getframe().f_code.co_name
        ssm = self.services[serv_id][func_name]['ssm']
        ssm_uuid = str(self.services[serv_id]['SSMs'][ssm])
        topic = 'ssm.management.' + ssm_uuid + '.place'

        # Contact SSM
        payload = yaml.dump(message)
        self.manoconn.call_async(self.resp_place,
                                 topic,
                                 payload,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def req_vnfs_deployment(self, serv_id):
        """
        This method triggeres the deployment of all the vnfs.
        """

        self.services[serv_id]['act_corr_id'] = []
        for key in self.services[serv_id]:
            if key[:4] == 'VNFD':
                vnfd = self.services[serv_id][key]
                # TODO: get mapping for this vnf
                mapping = []

                corr_id = str(uuid.uuid4())
                self.services[serv_id]['act_corr_id'].append(corr_id)

                self.req_vnf_deployment(vnfd, mapping, corr_id)
                amount_vnfs = self.services[serv_id]['vnfs_to_deploy']
                self.services[serv_id]['vnfs_to_deploy'] = amount_vnfs + 1

        self.services[serv_id]['pause_chain'] = True

    def req_vnf_deployment(self, vnfd, mapping, corr_id):
        """
        This method triggers the deployment of one vnf.
        """

        message = {'vnfd':vnfd, 'mapping':mapping}
        payload = yaml.dump(message)
        self.manoconn.call_async(self.resp_vnf_depl,
                                 t.VNF_CREATE, 
                                 payload, 
                                 correlation_id=corr_id)

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

        # Add the service to the ledger
        self.services[serv_id] = payload

        # Add instance ids for service and vnfs
        self.services[serv_id]['NSD']['instance_uuid'] = serv_id
        for key in payload.keys():
            if key[:4] == 'VNFD':
                vnf_id = str(uuid.uuid4())
                self.services[serv_id][key]['instance_uuid'] = vnf_id

        # Add to correlation id to the ledger
        self.services[serv_id]['corr_id'] = corr_id

        # Add payload to the ledger
        self.services[serv_id]['payload'] = payload

        # Create the service schedule
        self.services[serv_id]['schedule'] = []

        # Create a log for the task results
        self.services[serv_id]['task_log'] = []

        # Create the SSM dict
        self.services[serv_id]['SSMs'] = {}

        # Create counter for vnfs
        self.services[serv_id]['vnfs_to_deploy'] = 0

        # Create the chain pause flag

        self.services[serv_id]['pause_chain'] = False

        return serv_id

    def validate_deploy_request(self, serv_id):
        """
        This metod checks the format of a received request. All neccesary
        fields should be present, and the available fields should not be
        conflicting with each other.

        :param serv_id: the instance id of the service
        """
        payload = self.services[serv_id]['payload']
        corr_id = self.services[serv_id]['corr_id']

        # TODO: check whether correlation_id is already being used.

        # The service request in the yaml file should be a dictionary
        if not isinstance(payload, dict):
            response = "Request " + corr_id + ": payload is not a dict."
            message = {'status': 'ERROR', 'error': response}
            self.services[serv_id]['msg_gk'] = message
            return

        # The dictionary should contain a 'NSD' key
        if 'NSD' not in payload.keys():
            response = "Request " + corr_id + ": NSD is not a dict."
            message = {'status': 'ERROR', 'error': response}
            self.services[serv_id]['msg_gk'] = message
            return

        # Their should be as many VNFD keys in the dictionary as their
        # are network functions listed to the NSD.
        number_of_vnfds = 0
        for key in payload.keys():
            if key[:4] == 'VNFD':
                number_of_vnfds = number_of_vnfds + 1

        if len(payload['NSD']['network_functions']) != number_of_vnfds:
            response = "Request " + corr_id + ": # of VNFDs doesn't match NSD."
            message = {'status': 'ERROR', 'error': response}
            self.services[serv_id]['msg_gk'] = message
            return

        # Check whether VNFDs are empty.
        for key in payload.keys():
            if key[:4] == 'VNFD':
                if payload[key] is None:
                    response = "Request " + corr_id + ": empty VNFD."
                    message = {'status': 'ERROR', 'error': response}
                    self.services[serv_id]['msg_gk'] = message
                    return

        # If all tests succeed, the status changes to 'INSTANTIATING'
        message = {'status': 'INSTANTIATING', 'error': None}
        self.services[serv_id]['msg_gk'] = message
        return

#        except Exception as e:
#            tracebackString = traceback.format_exc(e)
#            self.services[serv_id]['traceback'] = tracebackString

    def placement(self, serv_id):
        """
        This method manages the placement of the service.

        :param serv_id: The instance uuid of the service
        """

        placement = ['test']

        self.services[serv_id]['placement'] = placement

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
            # Reconfigure the SLM
            print(self.uuid)
            print(active_slms)
            self.slm_config['old_slm_rank'] = self.slm_config['slm_rank']
            self.slm_config['old_slm_total'] = self.slm_config['slm_total']
            self.slm_config['slm_rank'] = active_slms.index(str(self.uuid))
            self.slm_config['slm_total'] = len(active_slms)

            self.known_slms = active_slms
            # Buffer incoming requests
            self.bufferAllRequests = True
            # Wait some time to allow different SLMs to get on the same pages
            time.sleep(self.deltaTnew)
            # Start handling the buffered requests in the new regime
            self.bufferOldRequests = True
            self.bufferAllRequests = False

            for req in self.new_reqs:
                task = self.thrd_pool.submit(req['mthd'], req['arguments'])

            time.sleep(self.deltaTold)
            # Start handling the buffered requests from the old regime
            self.bufferOldRequests = False

            for req in self.old_reqs:
                task = self.thrd_pool.submit(req['mthd'], req['arguments'])


    def convert_corr_id(self, corr_id):
        """
        This method converts the correlation id into an integer that is 
        small enough to be used with a modulo operation.

        :param corr_id: The correlation id as a String
        """ 

        #Select the final 4 digits of the string
        reduced_string = corr_id[-4:]
        reduced_int = int(reduced_string, 16)
        return reduced_int


    def dummy(self, serv_id):

        print(self.services[serv_id]['placement'])

        return














































































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
