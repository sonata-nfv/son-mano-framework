# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, 5GTANGO
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).
#
# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).

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

from sonmanobase.plugin import ManoBasePlugin
from sonmanobase.logger import TangoLogger
import sonmanobase.messaging as messaging

try:
    from son_mano_slm import slm_helpers as tools
except:
    import slm_helpers as tools

try:
    from son_mano_slm import slm_topics as t
except:
    import slm_topics as t

LOG = TangoLogger.getLogger(__name__, log_level=logging.INFO, log_json=True)

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

        self.publickey = None
        self.token = None
        self.password = '1234'
        self.clientId = 'son-slm'

        self.thrd_pool = pool.ThreadPoolExecutor(max_workers=10)

        self.ssm_connections = {}
        self.ssm_user = 'specific-management'
        self.ssm_pass = 'sonata'
        base = 'amqp://' + self.ssm_user + ':' + self.ssm_pass
        broker = os.environ.get("broker_host").split("@")[-1].split("/")[0]
        self.ssm_url_base = base + '@' + broker + '/'

        # The following can be removed once transition is done
        self.service_requests_being_handled = {}
        self.service_updates_being_handled = {}

        # call super class (will automatically connect to
        # broker and register the SLM to the plugin manger)
        ver = "0.1-dev"
        des = "This is the SLM plugin"

        wait_reg = wait_for_registration
        super(self.__class__, self).__init__(version=ver,
                                             description=des,
                                             auto_register=auto_register,
                                             wait_for_registration=wait_reg,
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

        # Fake policy manager for now
        self.manoconn.subscribe(self.policy_faker, 'policy.operator')

        # The topic on which update requests are posted.
        self.manoconn.subscribe(self.service_update, t.GK_UPDATE)

        # The topic on which monitoring information is received
        self.manoconn.subscribe(self.monitoring_feedback, t.MON_RECEIVE)

        # The topic on which the the SLM receives life cycle scale events
        self.manoconn.subscribe(self.service_instance_scale, t.MANO_SCALE)

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
        LOG.info("SLM started and operational. Registering with the GK...")

        LOG.info("configured nsd path: " + str(t.nsd_path))
        LOG.info("configured vnfd path: " + str(t.vnfd_path))
        LOG.info("configured nsr path: " + str(t.nsr_path))
        LOG.info("configured vnfr path: " + str(t.vnfr_path))
        LOG.info("configured monitoring path: " + str(t.monitoring_path))

#        self.register_slm_with_gk()

    def register_slm_with_gk(self):
        """
        This methods tries to register the SLM with the GK
        """
        counter = 0
        while counter < 3:
            try:
                user = self.clientId
                secr = self.password
                # Get Public key
                url = t.BASE_URL + t.API_VER + t.REG_PATH + t.PUPLIC_KEY_PATH
                self.publickey = tools.get_platform_public_key(url)
                LOG.info("Received key: " + str(self.publickey))

                # Register
                response = tools.client_register(t.GK_REGISTER, user, secr)
                LOG.info("Registration response: " + str(response))

                # Login
                self.token = tools.client_login(t.GK_LOGIN, user, secr)
                LOG.info("Login response: " + str(self.token))
            except:
                pass

            if self.token is None:
                LOG.info("Registration with GK failed, retrying...")
                counter = counter + 1
            else:
                break

        if self.token is None:
            LOG.info("Registration with GK failed, continuing without token.")
        else:
            LOG.info("Registration with GK succeeded, token obtained.")

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

        LOG.info("Service " + serv_id + ": Error occured, killing workflow")
        LOG.info("Service " + serv_id + ": Error: " + str(message))
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
            LOG.info("Service " + serv_id + ": Killing running workflow")

            if (self.services[serv_id]["current_workflow"] == 'instantiation'):
                # If the current workflow is an instantiation workflow, we need
                # to delete the stack, the SSMs/FSMs and the generated records
                # they already exist
                self.roll_back_instantiation(serv_id)

            del self.services[serv_id]
            return

        # Select the next task, only if task list is not empty
        if len(self.services[serv_id]['schedule']) > 0:

            # share state with other SLMs
            next_task = getattr(self,
                                self.services[serv_id]['schedule'].pop(0))

            # Push the next task to the threadingpool
            task = self.thrd_pool.submit(next_task, serv_id)

            # Log if a task fails
            if task.exception() is not None:
                print(task.result())

            # When the task is done, the next task should be started if no flag
            # is set to pause the chain.
            if self.services[serv_id]['pause_chain']:
                self.services[serv_id]['pause_chain'] = False
            else:
                self.start_next_task(serv_id)

        else:
            # share state with other SLMs
            self.slm_share('DONE', self.services[serv_id])

            del self.services[serv_id]

####################
# SLM input - output
####################

    def service_instance_create(self, ch, method, properties, payload):
        """
        This function handles a received message on the *.instance.create
        topic.
        """

        def send_response(error, serv_id=None):
            response = {}
            response['error'] = error

            if error is None:
                response['status'] = 'INSTANTIATING'
            else:
                response['status'] = 'ERROR'

            msg = ' Response on instantiation request: ' + str(response)
            LOG.info('Service ' + str(serv_id) + msg)
            self.manoconn.notify(t.GK_CREATE,
                                 yaml.dump(response),
                                 correlation_id=corr_id)

        # Check if the messages comes from the SLM
        if properties.app_id == self.name:
            LOG.info("Ignoring self-sent message.")
            return

        error = None
        # Extract the correlation id and generate a reduced id
        corr_id = properties.correlation_id
        if corr_id is None:
            error = "Please provide a correlation id."
            send_response(error)
            return

        reduced_id = tools.convert_corr_id(corr_id)

        # Start handling the request
        message = yaml.load(payload)

        if not isinstance(message, dict):
            error = 'Payload is not a dictionary'
            send_response(error)
            return

        if 'NSD' not in message.keys():
            error = 'No NSD key in message'
            send_response(error)
            return

        if 'VNFD0' not in message.keys():
            error = 'No VNFD key in message'
            send_response(error)
            return

        if 'user_data' not in message.keys():
            error = 'No user_data in message'
            send_response(error)
            return

        # Add the service to the ledger
        serv_id = self.add_service_to_ledger(message, corr_id)

        # Add workflow to ledger
        self.services[serv_id]['topic'] = t.GK_CREATE
        self.services[serv_id]["current_workflow"] = 'instantiation'

        # Schedule the tasks that the SLM should do for this request.
        add_schedule = []

        add_schedule.append('validate_deploy_request')
        add_schedule.append('contact_gk')

        # Onboard and instantiate the SSMs, if required.
        if self.services[serv_id]['ssm']:
            add_schedule.append('onboard_ssms')
            add_schedule.append('instant_ssms')

        if 'task' in self.services[serv_id]['ssm'].keys():
            add_schedule.append('trigger_task_ssm')

        add_schedule.append('consolidate_predefined_mapping')
        add_schedule.append('request_topology')
        add_schedule.append('request_policies')

        # Perform the placement
        if 'placement' in self.services[serv_id]['ssm'].keys():
            add_schedule.append('req_placement_from_ssm')
        else:
            add_schedule.append('SLM_mapping')

        add_schedule.append('consolidate_mapping')
        add_schedule.append('network_create')
        add_schedule.append('vnf_deploy')
        add_schedule.append('vnfs_generic_envs')
        add_schedule.append('vnfs_start')
        add_schedule.append('vnf_chain')
        add_schedule.append('wan_configure')
        add_schedule.append('store_nsr')
        add_schedule.append('start_monitoring')
        add_schedule.append('inform_gk_instantiation')

        self.services[serv_id]['schedule'].extend(add_schedule)

        msg = ": New instantiation request received. Instantiation started."
        LOG.info("Service " + serv_id + msg)
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

        def send_response(error, serv_id=None):
            response = {}
            response['error'] = error

            if error is None:
                response['status'] = 'TERMINATING'
            else:
                response['status'] = 'ERROR'

            msg = ' Response on termination request: ' + str(response)
            LOG.info('Service ' + str(serv_id) + msg)
            self.manoconn.notify(t.GK_KILL,
                                 yaml.dump(response),
                                 correlation_id=corr_id)

        # Check if the messages comes from the SLM
        if prop.app_id == self.name:
            LOG.info("Ignoring self-sent message.")
            return

        error = None
        # Extract the correlation id and generate a reduced id
        corr_id = prop.correlation_id
        if corr_id is None:
            error = "Please provide a correlation id."
            send_response(error)
            return

        content = yaml.load(payload)

        if not isinstance(content, dict):
            error = 'Payload is not a dictionary'
            send_response(error)
            return

        if 'service_instance_uuid' not in content.keys():
            error = "Please provide the service_instance_uuid key"
            send_response(error)
            return

        serv_id = content['service_instance_uuid']

        # Checks if service can be terminated
        head = {'Content-Type': 'application/json'}
        req = tools.getRestData(t.nsr_path + '/',
                                serv_id,
                                header=head)

        if req['error'] is not None:
            error = str(req['error']) + ': ' + req['content']
            msg = "error while retrieving NSR. " + error
            send_response(msg, serv_id)
            return

        nsr = req['content']

        if nsr['status'] == 'terminated':
            error = 'nsr already terminated'
            send_response(error, serv_id)
            return

        LOG.info("Termination request received for service " + str(serv_id))

        self.terminate_workflow(serv_id,
                                prop.correlation_id,
                                t.GK_KILL,
                                orig='GK')

    def reconfigure_workflow(self, serv_id):
        """
        This method triggers a reconfiguration workflow.
        """

        LOG.info('Service ' + str(serv_id) + ': reconfigure workflow request')
        self.services[serv_id]['status'] = 'reconfigurating'
        self.services[serv_id]["current_workflow"] = 'reconfigure'

        add_schedule = []
        add_schedule.append("configure_ssm")
        add_schedule.append("vnfs_config")
        add_schedule.append("inform_config_ssm")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info('Service ' + str(serv_id) + ': reconfigure workflow started')
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def rechain_workflow(self, serv_id, payload):
        """
        This method triggers a reconfiguration workflow.
        """

        # Check if the ledger has an entry for this instance
        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Recreating ledger.")
            self.recreate_ledger(corr_id, serv_id)

        self.services[serv_id]['nsd'] = payload['old_nsd']
        self.services[serv_id]['new_nsd'] = payload['new_nsd']

        LOG.info('Service ' + str(serv_id) + ': rechain workflow request')
        self.services[serv_id]["current_workflow"] = 'rechain'

        add_schedule = []
#        add_schedule.append("vnf_unchain")
        add_schedule.append("change_nsd")
        add_schedule.append("vnf_chain")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info('Service ' + str(serv_id) + ': rechain workflow started')
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def migrate_workflow(self, serv_id, payload):
        """
        This method triggers a reconfiguration workflow.
        """

        # Check if the ledger has an entry for this instance
        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Recreating ledger.")
            self.recreate_ledger(corr_id, serv_id)

        for function in self.services[serv_id]['function']:
            function['vim_uuid'] = payload['vim_uuid']
            function['id'] = payload['function_id']

        self.services[serv_id]['ingress'] = payload['ingress']
        self.services[serv_id]['egress'] = payload['egress']

        LOG.info('Service ' + str(serv_id) + ': migrate workflow request')
        self.services[serv_id]["current_workflow"] = 'migrate'

        add_schedule = []
        add_schedule.append('network_create')
        add_schedule.append("vnf_deploy")
        add_schedule.append("vnfs_start")
        add_schedule.append("vnf_chain")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info('Service ' + str(serv_id) + ': migrate workflow started')
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def service_instance_scale(self, ch, method, prop, payload):

        def send_response(error, serv_id, scaling_type=None):
            response = {}
            response['error'] = error
            response['scaling_type'] = scaling_type

            if error is None:
                response['status'] = 'SCALING'
            else:
                response['status'] = 'ERROR'

            msg = ' Response on scaling request: ' + str(response)
            LOG.info('Service ' + str(serv_id) + msg)
            self.manoconn.notify(t.MANO_SCALE,
                                 yaml.dump(response),
                                 correlation_id=corr_id)

        # Check if the message doesn't come from SLM itself
        if prop.app_id == self.name:
            return

        message = yaml.load(payload)

        # Check if payload is ok
        error = None

        corr_id = prop.correlation_id
        if corr_id is None:
            error = 'No correlation id provided in header of request'
            send_response(error, None)
            return

        if not isinstance(message, dict):
            error = 'Payload is not a dictionary'
            send_response(error, None)
            return

        if 'service_instance_uuid' in message.keys():
            serv_id = message['service_instance_uuid']
            LOG.info('Service ' + str(serv_id) + ": Received scaling request")
            LOG.info('Service ' + str(serv_id) + ": " + str(payload))

            if serv_id in self.services.keys():
                error = "Workflow for service still going on, rejected"
                send_response(error, serv_id)
                return
            else:
                # Based on the received payload, the ledger entry is recreated.
                self.recreate_ledger(corr_id, serv_id)

        else:
            error = 'Missing \'service_instance_id\' in request'
            send_response(error, None)
            return

        if 'scaling_type' in message.keys():
            scaling_type = message['scaling_type']
        else:
            error = "Missing \'scaling_type\' in request."
            send_response(error, serv_id)
            return

        if scaling_type not in ['addvnf', 'removevnf', 'ADD_VNF', 'REMOVE_VNF']:
            error = "scaling type \'" + scaling_type + "\' not supported."
            send_response(error, serv_id, scaling_type)
            return

        # Handle the request
        if scaling_type in ['addvnf', 'ADD_VNF']:
            # Check if vnfd id is provided
            if 'vnfd_uuid' not in message.keys():
                error = '\'vnfd_id\' missing from request'
                send_response(error, serv_id, scaling_type)
                return

            # Request vnfd
            head = {'content-type': 'application/x-yaml'}
            req = tools.getRestData(t.vnfd_path + '/',
                                    message['vnfd_uuid'],
                                    header=head)

            if req['error'] is not None:
                send_response(req['error'], serv_id, scaling_type)
                return

            vnfd = req['content']['vnfd']
            vnfd['uuid'] = message['vnfd_uuid']

            # build content for scaling workflow
            content = {}
            content['vnfd'] = vnfd
            content['vim_uuid'] = None
            content['corr_id'] = corr_id
            content['number_of_instances'] = 1

            if 'number_of_instances' in message.keys():
                content['number_of_instances'] = message['number_of_instances']
            if 'constraints' in message.keys():
                if 'vim_uuid' in message['constraints'].keys():
                    content['vim_uuid'] = message['constraints']['vim_uuid']

            # sending response to requesting party
            send_response(error, serv_id, scaling_type)

            # starting scaling workflow
            self.add_vnf_workflow(serv_id, content)

        if scaling_type in ['removevnf', 'REMOVE_VNF']:
            # Check if vnf id is provided
            content = {}
            content['corr_id'] = corr_id

            if 'vnf_uuid' not in message.keys() and 'vnfd_uuid' not in message.keys():
                error = '\'vnf_id\' or \'vnfd_id\' missing from request'
                send_response(error, serv_id, scaling_type)
                return

            if 'vnf_uuid' in message.keys() and 'number_of_instances' in message.keys():
                error = '\'vnf_id\' and \'number_of_instances\' cant appear together'
                send_response(error, serv_id, scaling_type)
                return

            if 'vnf_uuid' in message.keys():
                for vnf in self.services[serv_id]['function']:
                    if vnf['id'] == message['vnf_uuid']:
                        if vnf['vnfr']['status'] == 'terminated':
                            error = 'vnf already terminated'
                            send_response(error, serv_id, scaling_type)
                            return
                        else:
                            send_response(error, serv_id, scaling_type)
                            content['vnf_id'] = message['vnf_uuid']
                            self.remove_vnf_workflow(serv_id, content)
            elif 'vnfd_uuid' in message.keys():
                number = 1
                if 'number_of_instances' in message.keys():
                    number = message['number_of_instances']
                vnf_ids = []
                for vnf in self.services[serv_id]['function']:
                    if vnf['vnfr']['status'] == 'terminated':
                        continue
                    if vnf['vnfr']['descriptor_reference'] == message['vnfd_uuid']:
                        vnf_ids.append(vnf['id'])
                        number = number - 1
                        if number == 0:
                            send_response(error, serv_id, scaling_type)
                            content['vnf_id'] = vnf_ids
                            self.remove_vnf_workflow(serv_id, content)
                if number > 0:
                    error = 'Not enough instances running'
                    send_response(error, serv_id, scaling_type)
                    return
            return

    def remove_vnf_workflow(self, serv_id, payload):

        LOG.info('Service ' + str(serv_id) + ": Starting remove vnf workflow")
        # Check if the ledger has an entry for this instance
        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Recreating ledger.")
            self.recreate_ledger(payload['corr_id'], serv_id)

        self.services[serv_id]['start_time'] = time.time()
        self.services[serv_id]['topic'] = t.MANO_SCALE

        for vnf in self.services[serv_id]['function']:
            if vnf['id'] in payload['vnf_id']:
                continue
            else:
                vnf['stop']['trigger'] = False

        self.services[serv_id]["current_workflow"] = 'removevnf'

        add_schedule = []
        add_schedule.append('consolidate_predefined_mapping')
        add_schedule.append('remove_vnfs_from_mapping')
        add_schedule.append('vnf_remove')
        add_schedule.append('remove_network')
        add_schedule.append('wan_deconfigure')
        add_schedule.append('wan_configure')
        add_schedule.append('update_nsr')
        if 'scale' in self.services[serv_id]['ssm'].keys():
            add_schedule.append("configure_ssm")
            add_schedule.append("vnfs_config")
        add_schedule.append('start_monitoring')
        add_schedule.append("inform_gk")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info('Service ' + str(serv_id) + ': remove vnf workflow started')
        LOG.info('Service ' + str(serv_id) + ': ' + str(add_schedule))
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def add_vnf_workflow(self, serv_id, payload):

        LOG.info('Service ' + str(serv_id) + ": Starting add vnf workflow")
        # Check if the ledger has an entry for this instance
        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Recreating ledger.")
            self.recreate_ledger(payload['corr_id'], serv_id)

        self.services[serv_id]['start_time'] = time.time()
        self.services[serv_id]['topic'] = t.MANO_SCALE
        # for vnf in self.services[serv_id]['function']:
        #     vnf['start']['trigger'] = False
        #     vnf['deployed'] = True

        vnfd_to_add = payload['vnfd']
        flavour = None

        nsd = self.services[serv_id]['nsd']
        for vnf_nsd in nsd['network_functions']:
            if vnf_nsd['vnf_name'] == vnfd_to_add['name'] and \
               vnf_nsd['vnf_vendor'] == vnfd_to_add['vendor'] and \
               vnf_nsd['vnf_version'] == vnfd_to_add['version']:
                if vnf_nsd.get('vnf_flavour'):
                    flavour = vnf_nsd['vnf_flavour']

                    flavour_dict = {}

                    for flavour_name in vnfd_to_add['deployment_flavours']:
                        if flavour_name == flavour:
                            flavour_dict = flavour_name
                            break

                    for key in flavour_dict.keys():
                        if key != 'name':
                            vnfd_to_add[key] = flavour_dict[key] 

        for i in range(payload['number_of_instances']):
            vnf_id = str(uuid.uuid4())
            vnf_base_dict = {'start': {'trigger': True, 'payload': {}},
                             'stop': {'trigger': True, 'payload': {}},
                             'configure': {'trigger': True, 'payload': {}},
                             'scale': {'trigger': True, 'payload': {}},
                             'vnfd': copy.deepcopy(vnfd_to_add),
                             'id': vnf_id,
                             'vim_uuid': payload['vim_uuid'],
                             'flavour': None}

            # fix vdu_id
            for vdu in vnf_base_dict['vnfd']['virtual_deployment_units']:
                vdu['id'] = vdu['id'] + '-' + vnf_id

            self.services[serv_id]['function'].append(vnf_base_dict)

            # Add selected vim to input mapping
            if payload['vim_uuid']:
                fixed_map = {}
                for vnf_nsd in self.services[serv_id]['nsd']['network_functions']:
                    if vnf_nsd['vnf_name'] == vnfd_to_add['name'] and \
                       vnf_nsd['vnf_vendor'] == vnfd_to_add['vendor'] and \
                       vnf_nsd['vnf_version'] == vnfd_to_add['version']:
                        vnf_id = vnf_nsd['vnf_id']
                        break
                fixed_map['vnf_id'] = vnf_id
                fixed_map['vim_id'] = payload['vim_uuid']
                self.services[serv_id]['input_mapping']['vnfs'].append(fixed_map)

        self.services[serv_id]["current_workflow"] = 'addvnf'

        add_schedule = []
        add_schedule.append('consolidate_predefined_mapping')
        add_schedule.append('request_topology')
        add_schedule.append('request_policies')

        # Perform the placement
        if 'placement' in self.services[serv_id]['ssm'].keys():
            add_schedule.append('req_placement_from_ssm')
        else:
            add_schedule.append('SLM_mapping')
        add_schedule.append('consolidate_mapping')
        add_schedule.append('network_create')
        add_schedule.append('vnf_deploy')
        add_schedule.append('vnfs_start')
        add_schedule.append('wan_configure')
        add_schedule.append('update_nsr')
        if 'scale' in self.services[serv_id]['ssm'].keys():
            add_schedule.append("configure_ssm")
            add_schedule.append("vnfs_config")
        add_schedule.append('start_monitoring')
        add_schedule.append("inform_gk")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info('Service ' + str(serv_id) + ': add vnf workflow started')
        LOG.info('Service ' + str(serv_id) + ': ' + str(add_schedule))
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def del_vnf_workflow(self, serv_id, payload):

        pass

    def terminate_workflow(self, serv_id, corr_id=None, topic=None, orig=None):
        """
        This function handles the actual termination
        """

        # Check if the ledger has an entry for this instance
        rec_success = True
        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Service " + str(serv_id) + ": Recreating ledger")
            rec_success = self.recreate_ledger(corr_id, serv_id)
            msg = ": Recreation result: " + str(rec_success)
            LOG.info("Service " + str(serv_id) + msg)

        # Specify workflow in ledger
        self.services[serv_id]['topic'] = topic
        self.services[serv_id]['status'] = 'TERMINATING'
        self.services[serv_id]["current_workflow"] = 'termination'
        # Schedule the tasks that the SLM should do for this request.
        add_schedule = []

        if rec_success:
            if orig == 'GK':
                add_schedule.append('contact_gk')
            add_schedule.append('consolidate_predefined_mapping')
            add_schedule.append("stop_monitoring")
            add_schedule.append("wan_deconfigure")
            add_schedule.append("vnf_unchain")
            add_schedule.append("vnfs_stop")
            add_schedule.append("terminate_service")

            if self.services[serv_id]['ssm']:
                add_schedule.append("terminate_ssms")

            for vnf in self.services[serv_id]['function']:
                if vnf.get('fsm'):
                    add_schedule.append("terminate_fsms")
                    break

            add_schedule.append("update_records_to_terminated")
        if orig == 'GK':
            add_schedule.append("inform_gk")

        self.services[serv_id]['schedule'].extend(add_schedule)

        LOG.info("Termination workflow started for service " + str(serv_id))
        LOG.info(yaml.dump(self.services[serv_id]['schedule']))
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def service_instance_custom(self, serv_id, schedule, payload=None):
        """
        This method creates a customized workflow. It is not called by
        the user through the GK, but from an SSM. The SSM has created
        the task schedule
        """

        LOG.info("Custom workflow requested for service " + str(serv_id))

        if serv_id not in self.services.keys():
            # Based on the received payload, the ledger entry is recreated.
            LOG.info("Recreating ledger.")
            self.recreate_ledger(None, serv_id)

        self.services[serv_id]["current_workflow"] = 'custom'
        self.services[serv_id]['schedule'] = schedule

        if payload:
            for key in payload.keys():
                if key == 'nsd':
                    LOG.info('Service ' + str(serv_id) + ': nsd overwritten')
                    self.services[serv_id]['nsd'] = payload['nsd']

        LOG.info("Custom workflow started for service " + str(serv_id))
        # Start the chain of tasks
        self.start_next_task(serv_id)

        return self.services[serv_id]['schedule']

    def service_update(self, ch, method, prop, payload):

        pass

    def monitoring_feedback(self, ch, method, prop, payload):

       # LOG.info("Monitoring message received")
       # LOG.info(payload)

        try:
            content = json.loads(str(payload))

            content['ssm_type'] = 'monitor'
            uuid = content['serviceID']
            new_payload = yaml.dump(content)

            # Forward the received monitoring message to the SSM
            topic = 'generic.ssm.' + uuid

            ssm_conn = self.ssm_connections[uuid]

            ssm_conn.notify(topic, new_payload)
        except:
            pass

    def from_monitoring_ssm(self, ch, method, prop, payload):
        """
        This method is called every time the SLM receives a message from
        a monitoring SSM.
        """
        content = yaml.load(payload)
        LOG.info("monitoring SSM responded: " + str(content))

        serv_id = content['service_instance_id']

        if serv_id not in self.services.keys():
            ledger_recreation = self.recreate_ledger(None, serv_id)

            if ledger_recreation is None:
                LOG.info("Recreation of ledger failed, aborting mon event")
                return

        # Extract additional content provided by the SSM
        if 'vnf' in content.keys():
            vnfs = content['vnf']
            for vnf in vnfs:
                vnf_id = vnf['id']
                for vnf_slm in self.services[serv_id]['function']:
                    if vnf_id == vnf_slm['id']:
                        for key in vnf.keys():
                            vnf_slm[key] = vnf[key]

        if 'service' in content.keys():
            if 'configure' in content['service'].keys():
                data = content['service']['configure']
                self.services[serv_id]['configure'] = data

        if 'workflow' in content.keys():
            if content['workflow'] == 'termination':
                self.terminate_workflow(serv_id)
            if content['workflow'] == 'pause':
                pass
            if content['workflow'] == 'reconfigure':
                self.reconfigure_workflow(serv_id)
            if content['workflow'] == 'rechain':
                self.rechain_workflow(serv_id, content['data'])
            if content['workflow'] == 'migrate':
                new_serv_id = str(uuid.uuid4())
                self.services[new_serv_id] = {}
                self.services[new_serv_id] = self.services[serv_id].copy()
                self.services[new_serv_id]['old_serv_id'] = serv_id
                self.migrate_workflow(new_serv_id, content['data'])
            if content['workflow'] == 'scale_ns':
                self.add_vnf_workflow(serv_id, content['data'])

        if 'schedule' in content.keys():
            schedule = content['schedule']
            data = None
            if 'data' in content.keys():
                data = content['data']
            LOG.info("schedule found: " + str(schedule))
            self.service_instance_custom(serv_id, schedule, data)

        return

    def resp_topo(self, ch, method, prop, payload):
        """
        This function handles responses to topology requests made to the
        infrastructure adaptor.
        """
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        if type(message) == dict:
            LOG.info("Service " + serv_id + ": VIM topology received from IA.")
            self.services[serv_id]['infrastructure']['vims'] = message

        if type(message) == list:
            LOG.info("Service " + serv_id + ": WIM topology received from IA.")
            self.services[serv_id]['infrastructure']['wims'] = message

        # Deduct from the number of topo responses to expect
        self.services[serv_id]['topo_responses'] -= 1

        # Continue with the scheduled tasks if done
        if self.services[serv_id]['topo_responses'] == 0:
            LOG.info(yaml.dump(self.services[serv_id]['infrastructure']))
            self.start_next_task(serv_id)

    def policy_faker(self, ch, method, prop, payload):

        message = yaml.load(payload)
        if 'policy' in message.keys():
            return

        LOG.info("Policy request received")

        response = {}
        response['policy'] = 'load balanced'
#        response['list'] = ['Athens', 'Ghent']
        topic = 'policy.operator'
        self.manoconn.notify(topic,
                             yaml.dump(response),
                             correlation_id=prop.correlation_id)

    def resp_policies(self, ch, method, prop, payload):
        """
        This function handles responses to topology requests made to the
        infrastructure adaptor.
        """
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        LOG.info("Service " + serv_id + ": Operator Policies received.")
        LOG.debug("Operator Policies: " + str(message))

        # Add topology to ledger
        self.services[serv_id]['operator_policies'] = message

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_onboard(self, ch, method, prop, payload):
        """
        This function handles responses to a request to onboard the ssms
        of a new service.
        """
        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)
        LOG.info("Service " + serv_id + ": Onboarding resp received from SMR.")

        message = yaml.load(payload)

        for key in message.keys():
            if message[key]['error'] == 'None':
                LOG.info("Service " + serv_id + ": SSMs onboarded succesfully")
            else:
                msg = ": SSM onboarding failed: " + message[key]['error']
                LOG.info("Service " + serv_id + msg)
                self.error_handling(serv_id,
                                    t.GK_CREATE,
                                    message[key]['error'])

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_instant(self, ch, method, prop, payload):
        """
        This function handles responses to a request to onboard the ssms
        of a new service.
        """

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)
        msg = ": Instantiating response received from SMR."
        LOG.info("Service " + serv_id + msg)
        LOG.debug(payload)

        message = yaml.load(payload)
        for ssm_type in self.services[serv_id]['ssm'].keys():
            ssm = self.services[serv_id]['ssm'][ssm_type]
            response = message[ssm['id']]
            ssm['instantiated'] = False
            if response['error'] == 'None':
                LOG.info("Service " + serv_id + ": SSM instantiated correct.")
                ssm['instantiated'] = True
            else:
                msg = ": SSM instantiation failed: " + response['error']
                LOG.info("Service " + serv_id + msg)
                self.error_handling(serv_id, t.GK_CREATE, response['error'])

            ssm['uuid'] = response['uuid']

        # Setup broker connection with the SSMs of this service.
        url = self.ssm_url_base + 'ssm-' + serv_id
        LOG.info("Service " + serv_id + ':' + url)
        ssm_conn = messaging.ManoBrokerRequestResponseConnection(self.name,
                                                                 url=url)

        self.ssm_connections[serv_id] = ssm_conn

        # Continue with the scheduled tasks
        self.start_next_task(serv_id)

    def resp_task(self, ch, method, prop, payload):
        """
        This method handles updates of the task schedule by the an SSM.
        """
        # TODO: Test this method

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        LOG.info("Service " + serv_id + ": Response from task ssm: " + payload)

        message = yaml.load(payload)

        if message['status'] == 'COMPLETED':
            self.services[serv_id]['schedule'] = message['schedule']
            msg = ": New schedule: " + str(self.services[serv_id]['schedule'])
            LOG.info("Service " + serv_id + msg)

            # Continue with the scheduled tasks
            self.start_next_task(serv_id)
        else:
            LOG.info("Service " + serv_id + ": Schedule update failed")

    def resp_place(self, ch, method, prop, payload):
        """
        This method handles a placement performed by an SSM.
        """
        # TODO: Test this method

        message = yaml.load(payload)

        is_dict = isinstance(message, dict)
        LOG.debug("Type Dict: " + str(is_dict))

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        mapping = message['mapping']
        error = message['error']

        if error is not None:
            LOG.info("Service " + serv_id + ": Error from place: " + error)
            self.error_handling(serv_id, t.GK_CREATE, error)

        else:
            # Add mapping to ledger
            msg = ": Calculated SSM mapping: " + str(mapping)
            LOG.info("Service " + serv_id + msg)
            self.services[serv_id]['mapping'] = mapping
            for function in self.services[serv_id]['function']:
                vnf_id = function['id']
                function['vim_uuid'] = mapping[vnf_id]['vim']

        # Check if the placement does not contain any loops
        vim_list = tools.get_ordered_vim_list(self.services[serv_id])

        if vim_list is None:
            # the placement contains loops
            msg = 'Placement contains loop, improve Placement SSM.'
            self.error_handling(serv_id,
                                t.GK_CREATE,
                                msg)

            return
        else:
            LOG.info("Service " + serv_id + ": VIM list ordered")
            self.services[serv_id]['ordered_vim_list'] = vim_list

        self.start_next_task(serv_id)

    def resp_ssm_configure(self, ch, method, prop, payload):
        """
        This method handles an ssm configuration response
        """

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        msg = ": Response received from configuration SSM."
        LOG.info("Service " + serv_id + msg)

        content = yaml.load(payload)

        # TODO: check if content is correctly formatted

        if 'vnf' in content.keys():
            vnfs = content['vnf']
            for vnf in vnfs:
                vnf_id = vnf['id']
                for vnf_slm in self.services[serv_id]['function']:
                    if vnf_id == vnf_slm['id']:
                        for key in vnf.keys():
                            vnf_slm[key] = vnf[key]

        self.start_next_task(serv_id)

    def resp_vnf_remove(self, ch, method, prop, payload):
        """
        This method handles a response from the FLM to a vnf removal request.
        """
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)
        msg = ": Message received from FLM on VNF remove call."
        LOG.info("Service " + serv_id + msg)

        topic = self.services[serv_id]["topic"]
        # Inform GK if VNF deployment failed
        if message['error'] is not None:

            LOG.info("Service " + serv_id + ": Removal of VNF failed")
            LOG.debug("Message: " + str(message))
            self.error_handling(serv_id, topic, message['error'])

        else:
            LOG.info("Service " + serv_id + ": VNF correctly removed.")
            for function in self.services[serv_id]['function']:
                if function['id'] == message['vnf_id']:
                    self.services[serv_id]['function'].remove(function)
                    break
                    # base = t.vnfr_path + "/"
                    # request = tools.getRestData(base, message['vnf_id'])

                    # if request['error'] is not None:
                    #     error = 'could not retrieve VNFR: ' + request['error']
                    #     self.error_handling(serv_id, topic, error)

                    # function['vnfr'] = request['content']
                    # del function['vnfr']['updated_at']
                    # del function['vnfr']['created_at']
                    # del function['vnfr']['uuid']
                    # function['vnfr']['id'] = function['id']

        vnfs_to_depl = self.services[serv_id]['vnfs_to_resp'] - 1
        self.services[serv_id]['vnfs_to_resp'] = vnfs_to_depl

        # Only continue if all vnfs are removed
        if vnfs_to_depl == 0:
            self.services[serv_id]['act_corr_id'] = None
            self.start_next_task(serv_id)

    def resp_vnf_depl(self, ch, method, prop, payload):
        """
        This method handles a response from the FLM to a vnf deploy request.
        """
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)
        msg = ": Message received from FLM on VNF deploy call."
        LOG.info("Service " + serv_id + msg)

        # Inform GK if VNF deployment failed
        if message['error'] is not None:

            LOG.info("Service " + serv_id + ": Deployment of VNF failed")
            LOG.debug("Message: " + str(message))
            self.error_handling(serv_id, t.GK_CREATE, message['error'])

        else:
            LOG.info("Service " + serv_id + ": VNF correctly Deployed.")
            for function in self.services[serv_id]['function']:
                if function['id'] == message['vnfr']['id']:
                    function['vnfr'] = message['vnfr']
                    function['deployed'] = True
                    LOG.info("Added vnfr for inst: " + message['vnfr']['id'])

                    ip_mapping = message['ip_mapping']
                    self.services[serv_id]['ip_mapping'].extend(ip_mapping)
                    new_mapping = self.services[serv_id]['ip_mapping']
                    msg = ": IP Mapping extended: " + str(new_mapping)
                    LOG.info("Service " + serv_id + msg)

        vnfs_to_depl = self.services[serv_id]['vnfs_to_resp'] - 1
        self.services[serv_id]['vnfs_to_resp'] = vnfs_to_depl

        # Only continue if all vnfs are deployed
        if vnfs_to_depl == 0:
            self.services[serv_id]['act_corr_id'] = None
            self.start_next_task(serv_id)

    def resp_vnfs_csss(self, ch, method, prop, payload):
        """
        This method handles a response from the FLM to a vnf csss request.
        """
        message = yaml.load(payload)

        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)
        msg = ": Response received from FLM on VNF csss call."
        LOG.info("Service " + serv_id + msg)

        # Inform GK if VNF deployment failed
        if message['error'] is not None:

            LOG.info("Service " + serv_id + ": VNF csss event failed")
            LOG.debug("Message: " + str(message))
            topic = self.services[serv_id]['topic']
            self.services[serv_id]['config_status'] = 'failed'
            self.error_handling(serv_id, topic, message['error'])

        else:
            vnf_id = str(message["vnf_id"])
            self.services[serv_id]['config_status'] = 'ready'
            message = ": VNF " + vnf_id + " correctly handled."
            LOG.info("Service " + serv_id + message)

        vnfs_to_resp = self.services[serv_id]['vnfs_to_resp'] - 1
        self.services[serv_id]['vnfs_to_resp'] = vnfs_to_resp

        # Only continue if all vnfs are done
        if vnfs_to_resp == 0:
            self.services[serv_id]['act_corr_id'] = None
            self.start_next_task(serv_id)

    def resp_prepare(self, ch, method, prop, payload):
        """
        This method handles a response to a prepare request.
        """
        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        response = yaml.load(payload)
        LOG.debug("Response from IA on .prepare call: " + str(response))

        if response['request_status'] == "COMPLETED":
            LOG.info("Service " + serv_id + ": Msg from IA: Infra prepared")
        else:
            msg = ": Error occured while preparing vims, aborting workflow"
            LOG.info("Service " + serv_id + msg)
            self.error_handling(serv_id, t.GK_CREATE, response['message'])

        self.start_next_task(serv_id)

    def resp_remove_networks(self, ch, method, prop, payload):
        """
        This method handles a response to a prepare request.
        """
        # Retrieve the service uuid
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        response = yaml.load(payload)
        LOG.debug("Response from IA on network.remove call: " + str(response))

        if response['request_status'] == "COMPLETED":
            LOG.info("Service " + serv_id + ": Networks removed")
        else:
            msg = ": Error occured while removing network"
            LOG.info("Service " + serv_id + msg)
            self.error_handling(serv_id, t.GK_CREATE, response['message'])

        self.start_next_task(serv_id)

    def contact_gk(self, serv_id):
        """
        This method handles communication towards the gatekeeper.`

        :param serv_id: the instance uuid of the service
        """

        # Get the correlation_id for the message
        corr_id = self.services[serv_id]['original_corr_id']

        # Build the message for the GK
        message = {}
        message['status'] = self.services[serv_id]['status']
        message['error'] = self.services[serv_id]['error']
        message['timestamp'] = time.time()

        if 'add_content' in self.services[serv_id].keys():
            message.update(self.services[serv_id]['add_content'])

        payload = yaml.dump(message)
        self.manoconn.notify(self.services[serv_id]['topic'],
                             payload,
                             correlation_id=corr_id)

    def request_topology(self, serv_id):
        """
        This method is used to request the topology of the available
        infrastructure from the Infrastructure Adaptor.

        :param serv_id: The instance uuid of the service
        """

        # Generate correlation_id for the VIM call, for future reference
        corr_id_vim = str(uuid.uuid4())

        # Generate correlation_id for the WIM call, for future reference
        corr_id_wim = str(uuid.uuid4())

        self.services[serv_id]['act_corr_id'] = [corr_id_vim, corr_id_wim]

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

        # Make sure MANO waits for both responses
        self.services[serv_id]['topo_responses'] = 2

        self.manoconn.call_async(self.resp_topo,
                                 t.IA_VIM_LIST,
                                 None,
                                 correlation_id=corr_id_vim)

        LOG.info("Service " + serv_id + ": VIM topology requested from IA.")

        self.manoconn.call_async(self.resp_topo,
                                 t.IA_WIM_LIST,
                                 None,
                                 correlation_id=corr_id_wim)

        LOG.info("Service " + serv_id + ": WIM topology requested from IA.")

    def request_policies(self, serv_id):
        """
        This method is used to request the operator policies
        in therm of placement.

        :param serv_id: The instance uuid of the service
        """

        # Generate correlation_id for the call, for future reference
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        self.manoconn.call_async(self.resp_policies,
                                 t.OPERATOR_POLICY,
                                 None,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

        LOG.info("Service " + serv_id + ": Operator policies requested.")

    def remove_network(self, serv_id):
        """
        This message sends a message towards the IA if new networks need
        to be removed.

        :param serv_id: The instance uuid of the service
        """
        vim_list = {}
        if 'removed_vls' in self.services[serv_id]:
            vim_list = self.services[serv_id]['removed_vls']

        mapping = self.services[serv_id]['mapping']
        for vl_id in mapping['service']['vl']:
            vl = mapping['service']['vl'][vl_id]
            if 'vim_id' not in vl.keys():
                continue
            vims = vl['vim_id']
            new_vims = []
            for vim in vims:
                vim_still_used = False
                for vnf_id in mapping['function'].keys():
                    vnf = mapping['function'][vnf_id]
                    if vnf['vim_id'] != vim:
                        continue
                    for vl_vnf_id in vnf['vl']:
                        vl_vnf = vnf['vl'][vl_vnf_id]
                        if vl_vnf['id'] == vl['id']:
                            vim_still_used = True
                            new_vims.append(vim)
                if not vim_still_used:
                    if vim not in vim_list.keys():
                        vim_list[vim] = {'vls': []}
                    vim_list[vim]['vls'].append({'id': vl['id']})
            vl['vim_id'] = new_vims

        if not vim_list:
            LOG.info("Service " + serv_id + ": No network update needed.")
            return

        LOG.info("remove networks: " + yaml.dump(vim_list))
        message = {}
        message['instance_id'] = serv_id
        message['vim_list'] = [{'uuid':x, 'virtual_links': \
                               vim_list[x]['vls']} for x in vim_list.keys()]

        # Add correlation id to the ledger for future reference
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        # Send this mapping to the IA
        self.manoconn.call_async(self.resp_remove_networks,
                                 t.IA_REMOVE_NETWORKS,
                                 yaml.dump(message),
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True


    def network_create(self, serv_id):
        """
        This message sends a message towards the IA if new networks need
        to be created.

        :param serv_id: The instance uuid of the service
        """

        LOG.info(yaml.dump(self.services[serv_id]))

        msg = ": Requesting IA to update the networks."
        LOG.info("Service " + serv_id + msg)

        nsd = self.services[serv_id]['nsd']
        vnfs = self.services[serv_id]['function']
        mapping = self.services[serv_id]['mapping']

        # Build network message for IA
        message = {}

        # Add the service instance uuid
        message['instance_id'] = serv_id

        # Build used VIM dictionary
        vims = {}

        for vl_desc_id in mapping['service']['vl']:
            vl = mapping['service']['vl'][vl_desc_id]
            if vl['new'] and 'vim_id' in vl.keys():
                for vim_id in vl['vim_id']:
                    if vim_id not in vims.keys():
                        vims[vim_id] = {'uuid': vim_id,
                                              'virtual_links': []}
                    vl_dict = {'id': vl['id'],
                               'access': True,
                               'vl_id': vl_desc_id}
                    vims[vim_id]['virtual_links'].append(vl_dict)
            if vl['new'] and 'wim_id' in vl.keys():
                for vim_id in vl['vims']:
                    if vim_id not in vims.keys():
                        vims[vim_id] = {'uuid': vim_id,
                                              'virtual_links': []}
                    vl_dict = {'id': vl['id'],
                               'access': True,
                               'vl_id': vl_desc_id}
                    vims[vim_id]['virtual_links'].append(vl_dict)
            if 'update' in vl.keys():
                if not vl['update']:
                    continue
                for vim_id in vl['added_vims']:
                    if vim_id not in vims.keys():
                        vims[vim_id] = {'uuid': vim_id,
                                              'virtual_links': []}
                    vl_dict = {'id': vl['id'],
                               'access': True,
                               'vl_id': vl_desc_id}
                    vims[vim_id]['virtual_links'].append(vl_dict)

        for vnf_id in mapping['function']:
            vnf = mapping['function'][vnf_id]
            for vl_desc_id in vnf['vl']:
                vl = vnf['vl'][vl_desc_id]
                if vl['new'] and 'vim_id' in vl.keys():
                    if vl['vim_id'] not in vims.keys():
                        vims[vl['vim_id']] = {'uuid': vl['vim_id'],
                                              'virtual_links': []}
                    vl_dict = {'id': vl['id'],
                               'access': True,
                               'vl_id': vl_desc_id}
                    vims[vl['vim_id']]['virtual_links'].append(vl_dict)

        # Create the VIM list
        message['vim_list'] = [vims[x] for x in vims]

        msg = ": new PoPs to be used:\n" + yaml.dump(message['vim_list'])
        LOG.info("Service " + serv_id + msg)

        if len(message['vim_list']) > 0:
            # Add correlation id to the ledger for future reference
            corr_id = str(uuid.uuid4())
            self.services[serv_id]['act_corr_id'] = corr_id

            # Send this mapping to the IA
            self.manoconn.call_async(self.resp_prepare,
                                     t.IA_CREATE_NETWORKS,
                                     yaml.dump(message),
                                     correlation_id=corr_id)

            # Pause the chain of tasks to wait for response
            self.services[serv_id]['pause_chain'] = True

        else:
            msg = ": no new networks needed"
            LOG.info("Service " + serv_id + msg)

    def vnf_remove(self, serv_id):
        """
        This method triggeres the removal of a vnf.
        """

        msg = ": Removing VNFs"
        LOG.info("Service " + serv_id + msg)

        functions = self.services[serv_id]['function']
        self.services[serv_id]['vnfs_to_resp'] = 0

        self.services[serv_id]['act_corr_id'] = []

        for function in functions:

            if function['stop']['trigger']:
                vnf_to_dep = self.services[serv_id]['vnfs_to_resp']
                self.services[serv_id]['vnfs_to_resp'] = vnf_to_dep + 1
                corr_id = str(uuid.uuid4())
                self.services[serv_id]['act_corr_id'].append(corr_id)

                message = {}
                message['vnf_id'] = function['id']
                vdu = function['vnfr']['virtual_deployment_units'][0]
                message['vim_id'] = vdu['vnfc_instance'][0]['vim_id']
                message['serv_id'] = serv_id

                msg = ": Requesting the removal of vnf " + function['id']
                LOG.info("Service " + serv_id + msg)
                LOG.debug("Payload of request: " + str(message))
                self.manoconn.call_async(self.resp_vnf_remove,
                                         t.MANO_REMOVE,
                                         yaml.dump(message),
                                         correlation_id=corr_id)

        self.services[serv_id]['pause_chain'] = True

    def vnf_deploy(self, serv_id):
        """
        This method triggeres the deployment of all the vnfs.
        """

        LOG.info("ledger: " + yaml.dump(self.services[serv_id]))
        msg = ": Deploying VNFs"
        LOG.info("Service " + serv_id + msg)

        functions = self.services[serv_id]['function']
        mapping = self.services[serv_id]['mapping']['function']
        self.services[serv_id]['vnfs_to_resp'] = 0

        self.services[serv_id]['act_corr_id'] = []

        for function in functions:

            if mapping[function['id']]['new']:
                vnf_to_dep = self.services[serv_id]['vnfs_to_resp']
                self.services[serv_id]['vnfs_to_resp'] = vnf_to_dep + 1
                corr_id = str(uuid.uuid4())
                self.services[serv_id]['act_corr_id'].append(corr_id)

                LOG.info("vnfd: " + yaml.dump(function['vnfd']))
                tools.append_networkid_to_cp(function['vnfd'],
                                             mapping[function['id']]['vl'])

                message = {}
                message['vnfd'] = function['vnfd']
                message['id'] = function['id']
                message['vim_uuid'] = mapping[function['id']]['vim_id']
                message['serv_id'] = serv_id
                message['public_key'] = self.services[serv_id]['public_key']
                message['private_key'] = self.services[serv_id]['private_key']
                message['flavour'] = function['flavour']

                msg = ": Requesting the deployment of vnf " + function['id']
                LOG.info("Service " + serv_id + msg)
                LOG.debug("Payload of request: " + str(message))
                self.manoconn.call_async(self.resp_vnf_depl,
                                         t.MANO_DEPLOY,
                                         yaml.dump(message),
                                         correlation_id=corr_id)

        self.services[serv_id]['pause_chain'] = True


    def vnfs_generic_envs(self, serv_id):
        """
        This method generates the generic_envs for the CNFs.
        """

        vnfs = self.services[serv_id]['function']
        g_envs = {}
        for vnf in vnfs:
            vnfd = vnf['vnfd']
            vnfr = vnf['vnfr']
            vnf_t = vnfd['name'] + '_' + vnfd['vendor'] + '_' + vnfd['version']
            if 'cloudnative_deployment_units' in vnfr:
                for cdu in vnfr['cloudnative_deployment_units']:
                    if 'load_balancer_ip' in cdu.keys():
                        floating_ip = cdu['load_balancer_ip']['floating_ip']
                        break
                for cp in vnfd['connection_points']:
                    g_envs[vnf_t + '_' + cp['id'] + '_ip'] = floating_ip
                    g_envs[vnf_t + '_' + cp['id'] + '_port'] = cp['port']
                    g_envs[vnf_t + '_' + cp['id'] + '_type'] = 'container'
            if 'virtual_deployment_units' in vnfr:
                for vdu in vnfr['virtual_deployment_units']:
                    for cp in vdu['vnfc_instance'][0]['connection_points']:
                        for vl in vnfd['virtual_links']:
                            ref = vl['connection_points_reference']
                            ref_int = [x for x in ref if ':' not in x]
                            if len(ref) == len(ref_int):
                                pass
                            elif vdu['id'] + ':' + cp['id'] in ref:
                                tag = vnf_t + '_' + cp['id']
                                interface = cp['interface']
                                g_envs[tag + '_ip'] = interface['address']
                                g_envs[tag + '_type'] = 'vm'
                            else:
                                pass

        msg = ': Generic envs: ' + str(g_envs)
        LOG.info("Service " + serv_id + msg)

        for vnf in vnfs:
            vnfd = vnf['vnfd']
            if 'cloudnative_deployment_units' in vnfd:
                list_g_envs = []
                for cdu in vnfd['cloudnative_deployment_units']:
                    list_g_envs.append({'cdu_id': cdu['id'],
                                       'envs': g_envs})
                vnf['generic_envs'] = list_g_envs

        return

    def vnfs_start(self, serv_id):
        """
        This method gives a trigger to the FLM for each VNF that needs
        a FSM start life cycle event.
        """
        msg = ": Triggering VNF start events"
        LOG.info("Service " + serv_id + msg)
        self.vnfs_csss(serv_id, 'start', t.MANO_START)

    def vnfs_stop(self, serv_id):
        """
        This method gives a trigger to the FLM for each VNF that needs
        a FSM stop life cycle event.
        """
        msg = ": Triggering VNF stop events"
        LOG.info("Service " + serv_id + msg)
        self.vnfs_csss(serv_id, 'stop', t.MANO_STOP)

    def vnfs_config(self, serv_id):
        """
        This method gives a trigger to the FLM for each VNF that needs
        a FSM config life cycle event.
        """
        msg = ": Triggering VNF config events"
        LOG.info("Service " + serv_id + msg)
        self.vnfs_csss(serv_id, 'configure', t.MANO_CONFIG)

    def vnfs_scale(self, serv_id):
        """
        This method gives a trigger to the FLM for each VNF that needs
        a FSM scale life cycle event.
        """
        msg = ": Triggering VNF scale events"
        LOG.info("Service " + serv_id + msg)
        self.vnfs_csss(serv_id, 'scale', t.MANO_SCALE)

    def vnfs_csss(self, serv_id, csss_type, topic):
        """
        This generic method gives a trigger to the FLM for each VNF that needs
        a FSM csss life cycle event. Can be used for start, stop and config
        triggers.
        """
        functions = self.services[serv_id]['function']
        self.services[serv_id]['act_corr_id'] = []

        # Counting the number of vnfs that you need a response from
        vnfs_to_resp = 0
        for vnf in functions:
            if vnf[csss_type]['trigger']:
                vnfs_to_resp = vnfs_to_resp + 1
        self.services[serv_id]['vnfs_to_resp'] = vnfs_to_resp

        # stack
        stack = []

        # Actually triggering the FLM
        for vnf in functions:
            if vnf[csss_type]['trigger']:
                # Check if payload was provided
                payload = {}
                payload['vnf_id'] = vnf['id']
                payload['vnfd'] = vnf['vnfd']
                payload['serv_id'] = serv_id
                if bool(vnf[csss_type]['payload']):
                    payload['data'] = vnf[csss_type]['payload']
                # if not, create it
                else:
                    msg = ": Creating general csss message"
                    LOG.info("Service " + serv_id + msg)
                    if csss_type == "configure":
                        nsr = self.services[serv_id]['nsr']
                        vnfrs = []
                        for vnf_new in functions:
                            vnfrs.append(vnf_new['vnfr'])
                        data = {'nsr': nsr, 'vnfrs': vnfrs}

                        keys = str(self.services[serv_id].keys())
                        msg = ": keys in service ledger: " + keys
                        LOG.info("Service " + serv_id + msg)
                        if 'ingress' in self.services[serv_id].keys():
                            msg = ": Adding ingress/egress to csss message"
                            LOG.info("Service " + serv_id + msg)
                            ingress = self.services[serv_id]['ingress']
                            data['ingress'] = ingress
                        if 'egress' in self.services[serv_id].keys():
                            egress = self.services[serv_id]['egress']
                            data['egress'] = egress
                    else:
                        data = {'vnfr': vnf['vnfr'], 'vnfd': vnf['vnfd']}

                    payload['data'] = data

                if 'generic_envs' in vnf.keys():
                    payload['data']['generic_envs'] = vnf['generic_envs']

                corr_id = str(uuid.uuid4())
                self.services[serv_id]['act_corr_id'].append(corr_id)

                msg = " " + csss_type + " event requested for vnf " + vnf['id']
                LOG.info("Service " + serv_id + msg)

                add_stack = {}
                add_stack['topic'] = topic
                add_stack['payload'] = payload
                add_stack['corr_id'] = corr_id
                stack.append(add_stack)

        for vnf in stack:
            self.services[serv_id]['pause_chain'] = True
            self.manoconn.call_async(self.resp_vnfs_csss,
                                     vnf['topic'],
                                     yaml.dump(vnf['payload']),
                                     correlation_id=vnf['corr_id'])

    def onboard_ssms(self, serv_id):
        """
        This method instructs the ssm registry manager to onboard the
        required SSMs.

        :param serv_id: The instance uuid of the service
        """

        corr_id = str(uuid.uuid4())
        # Sending the NSD to the SRM triggers it to onboard the ssms
        msg = {}
        msg['NSD'] = self.services[serv_id]['nsd']
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

        LOG.info("Service " + serv_id + ": SSM on-board trigger sent to SMR.")

    def instant_ssms(self, serv_id):
        """
        This method instructs the ssm registry manager to instantiate the
        required SSMs.

        :param serv_id: The instance uuid of the service
        :param ssm_id: which ssm you want to deploy
        """

        corr_id = str(uuid.uuid4())
        # Sending the NSD to the SRM triggers it to instantiate the ssms

        msg_for_smr = {}
        msg_for_smr['NSD'] = self.services[serv_id]['nsd']
        msg_for_smr['UUID'] = serv_id

        msg = ": Keys in message for SSM instant: " + str(msg_for_smr.keys())
        LOG.info("Service " + serv_id + msg)
        pyld = yaml.dump(msg_for_smr)

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
        ssm_id = self.services[serv_id]['ssm']['task']['uuid']
        topic = "generic.ssm." + str(serv_id)

        # Adding the schedule to the message
        message = {'schedule': self.services[serv_id]['schedule'],
                   'ssm_type': 'task'}

        # Contact SSM
        payload = yaml.dump(message)

        ssm_conn = self.ssm_connections[serv_id]

        ssm_conn.call_async(self.resp_task,
                            topic,
                            payload,
                            correlation_id=corr_id)

        LOG.info("Service " + serv_id + ": task registered on " + str(topic))

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def req_placement_from_ssm(self, serv_id):
        """
        This method requests the placement by an ssm.

        :param serv_id: The instance uuid of the service.
        """

        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        # Check if placement SSM is available
        ssm_place = self.services[serv_id]['ssm']['placement']
        # If not available, fall back on SLM placement
        if ssm_place['instantiated'] is False:
            return self.SLM_mapping(serv_id)
        # build message for placement SSM
        nsd = self.services[serv_id]['nsd']
        top = self.services[serv_id]['infrastructure']['vims']

        vnfds = []
        for function in self.services[serv_id]['function']:
            vnfd_to_add = function['vnfd']
            vnfd_to_add['instance_uuid'] = function['id']
            vnfds.append(function['vnfd'])

        message = {'nsd': nsd,
                   'topology': top,
                   'uuid': serv_id,
                   'vnfds': vnfds}

        message['nap'] = {}

        if self.services[serv_id]['ingress'] is not None:
            message['nap']['ingresses'] = self.services[serv_id]['ingress']
        if self.services[serv_id]['egress'] is not None:
            message['nap']['egresses'] = self.services[serv_id]['egress']

        # Contact SSM
        payload = yaml.dump(message)

        msg = ": Placement requested from SSM: " + str(message.keys())
        LOG.info("Service " + serv_id + msg)

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

        if 'configure' not in self.services[serv_id]['ssm'].keys():
            LOG.info("Configuration SSM requested but not available")
            return

        # ssm = self.services[serv_id]['ssm']
        # if not ssm['configure']['instantiated']:
        #     LOG.info("Configuration SSM not instantiated")
        #     return

        # Building the content message for the configuration ssm
        content = {'service': self.services[serv_id],
                   'functions': self.services[serv_id]['function']}

        if self.services[serv_id]["current_workflow"] == 'instantiation':
            content['ingress'] = self.services[serv_id]['ingress']
            content['egress'] = self.services[serv_id]['egress']

        content['ssm_type'] = 'configure'
        content['workflow'] = self.services[serv_id]["current_workflow"]

        if 'ip_mapping' in self.services[serv_id].keys():
            content['ip_mapping'] = self.services[serv_id]['ip_mapping']

        topic = "generic.ssm." + str(serv_id)

        # TODO: recreate ssm connections when MANO is restarted
        ssm_conn = self.ssm_connections[serv_id]

        ssm_conn.call_async(self.resp_ssm_configure,
                            topic,
                            yaml.dump(content),
                            correlation_id=corr_id)

        msg = ": Call sent to configuration SSM."
        LOG.info("Service " + serv_id + msg)

        # Pause the chain of tasks to wait for response
        self.services[serv_id]['pause_chain'] = True

    def inform_config_ssm(self, serv_id):
        """
        Sent the status to the configuration SSM.
        """

        corr_id = str(uuid.uuid4())

        msg = ": Sending status to config SSM"
        LOG.info("Service " + serv_id + msg)

        content = {}
        content['ssm_type'] = 'configure'
        content['workflow'] = 'status'
        content['status'] = self.services[serv_id]['config_status']

        topic = "generic.ssm." + str(serv_id)

        ssm_conn = self.ssm_connections[serv_id]

        ssm_conn.notify(topic,
                        yaml.dump(content),
                        correlation_id=corr_id)

    def slm_share(self, status, content):

        message = {'status': status,
                   'state': content,
                   'corr_id': content['original_corr_id'],
                   'slm_id': self.uuid}

        payload = yaml.dump(message)
        self.manoconn.notify('mano.inter.slm', payload)

    def update_nsr(self, serv_id):

        old_nsr = self.services[serv_id]['nsr']
        version = str(int(old_nsr['version']) + 1)

        nsd = self.services[serv_id]['nsd']

        vnfr_ids = []
        for function in self.services[serv_id]['function']:
            vnfr_ids.append(function['id'])

        sid = old_nsr.get('sla_id')
        pid = old_nsr.get('policy_id')
        vls = self.services[serv_id]['mapping']['service']['vl']
        status = 'normal operation'

        nsr = tools.build_nsr(status, nsd, vnfr_ids, serv_id, vls, self.services[serv_id]['flavour'], sid, pid)

        nsr['id'] = serv_id
        nsr['version'] = version

        LOG.info(str(yaml.dump(nsr, default_flow_style=False)))

        error = None

        url = t.nsr_path + '/' + serv_id
        LOG.info("Service " + serv_id + ": " + str(url))
        header = {'Content-Type': 'application/json'}

        nsr_resp = requests.put(url,
                                data=json.dumps(nsr),
                                headers=header,
                                timeout=1.0)
        nsr_resp_json = str(nsr_resp.json())

        if (nsr_resp.status_code == 200):
            msg = ": NSR update accepted"
            LOG.info("Service " + serv_id + msg)
        else:
            msg = ": NSR update not accepted: " + nsr_resp_json
            LOG.info("Service " + serv_id + msg)
            error = {'http_code': nsr_resp.status_code,
                     'message': nsr_resp_json}
        # except:
        #     error = {'http_code': '0',
        #              'message': 'Timeout when contacting NSR repo'}

        # if error is not None:
        #     self.error_handling(serv_id, t.GK_CREATE, error)

        return

    def store_nsr(self, serv_id):

        LOG.info(yaml.dump(self.services[serv_id]['mapping']))
        # TODO: get request_status from response from IA on chain
        status = 'normal operation'

        if status == 'normal operation':
            LOG.info("Service " + serv_id + ": Update status of the VNFR")
            for function in self.services[serv_id]['function']:
                function['vnfr']['status'] = "normal operation"
                function['vnfr']['version'] = '2'

                url = t.vnfr_path + '/' + function['id']
                LOG.info("Service " + serv_id + ": URL VNFR update: " + url)

                error = None
                try:
                    header = {'Content-Type': 'application/json'}
                    vnfr_resp = requests.put(url,
                                             data=json.dumps(function['vnfr']),
                                             headers=header,
                                             timeout=1.0)
                    vnfr_resp_json = str(vnfr_resp.json())
                    if (vnfr_resp.status_code == 200):
                        msg = ": VNFR update accepted for " + function['id']
                        LOG.info("Service " + serv_id + msg)
                    else:
                        msg = ": VNFR update not accepted: " + vnfr_resp_json
                        LOG.info("Service " + serv_id + msg)
                        error = {'http_code': vnfr_resp.status_code,
                                 'message': vnfr_resp_json}
                except:
                    error = {'http_code': '0',
                             'message': 'Timeout when contacting VNFR repo'}

                if error is not None:
                    self.error_handling(serv_id, t.GK_CREATE, error)
                    return

        nsd = self.services[serv_id]['nsd']

        vnfr_ids = []
        for function in self.services[serv_id]['function']:
            vnfr_ids.append(function['id'])

        sid = self.services[serv_id]['sla_id']
        pid = self.services[serv_id]['policy_id']
        vls = self.services[serv_id]['mapping']['service']['vl']
        nsr = tools.build_nsr(status, nsd, vnfr_ids, serv_id, vls, self.services[serv_id]['flavour'], sid, pid)
        LOG.info("NSR to be stored: " + yaml.dump(nsr))

        error = None

        try:
            header = {'Content-Type': 'application/json'}
            nsr_resp = requests.post(t.nsr_path,
                                     data=json.dumps(nsr),
                                     headers=header,
                                     timeout=1.0)
            nsr_resp_json = nsr_resp.json()
            if (nsr_resp.status_code == 200):
                msg = ": NSR accepted and stored for instance " + serv_id
                LOG.info("Service " + serv_id + msg)
            else:
                msg = ": NSR not accepted: " + str(nsr_resp_json)
                LOG.info("Service " + serv_id + msg)
                error = {'http_code': nsr_resp.status_code,
                         'message': nsr_resp_json}
        except:
            error = {'http_code': '0',
                     'message': 'Timeout when contacting NSR repo'}

        self.services[serv_id]['nsr'] = nsr

        if error is not None:
            self.error_handling(serv_id, t.GK_CREATE, error)

        return

    def change_nsd(self, serv_id):

        LOG.info("Service " + serv_id + ": Updating NSD.")

        new_nsd = self.services[serv_id]['new_nsd']
        self.services[serv_id]['nsd'] = new_nsd

    def vnf_chain(self, serv_id):
        """
        This method instructs the IA how to chain the functions together.
        """

        return

        # nsd = self.services[serv_id]['nsd']

        # if 'forwarding_graphs' not in nsd:
        #     msg = ": No fowarding graph, no chaining"
        #     LOG.info("Service " + serv_id + msg)
        #     return

        # corr_id = str(uuid.uuid4())
        # self.services[serv_id]['act_corr_id'] = corr_id

        # chain = {}
        # chain["service_instance_id"] = serv_id
        # chain["nsd"] = nsd

        # vnfrs = []
        # vnfds = []

        # for function in self.services[serv_id]['function']:
        #     vnfrs.append(function['vnfr'])

        #     vnfd = function['vnfd']
        #     vnfd['instance_uuid'] = function['id']
        #     vnfds.append(vnfd)

        # chain['vnfrs'] = vnfrs
        # chain['vnfds'] = vnfds

        # # Add egress and ingress fields
        # chain['nap'] = {}
        # nap_empty = True

        # if self.services[serv_id]['ingress'] is not None:
        #     chain['nap']['ingresses'] = self.services[serv_id]['ingress']
        #     nap_empty = False
        # if self.services[serv_id]['egress'] is not None:
        #     chain['nap']['egresses'] = self.services[serv_id]['egress']
        #     nap_empty = False

        # # Check if `nap` is empty
        # if nap_empty:
        #     chain.pop('nap')

        # LOG.info(str(yaml.dump(chain, default_flow_style=False)))
        # self.manoconn.call_async(self.IA_chain_response,
        #                          t.IA_CONF_CHAIN,
        #                          yaml.dump(chain),
        #                          correlation_id=corr_id)

        # LOG.info("Service " + serv_id + ": Requested to chain the VNFs.")
        # # Pause the chain of tasks to wait for response
        # self.services[serv_id]['pause_chain'] = True

    def IA_chain_response(self, ch, method, prop, payload):
        """
        This method handles the IA response to the chain request
        """
        # Get the serv_id of this service
        serv_id = tools.servid_from_corrid(self.services,
                                           prop.correlation_id)

        message = yaml.load(payload)

        LOG.info("Service " + serv_id + ": Chaining request completed.")

        if message['message'] != '':
            error = message['message']
            LOG.info('Error occured during chaining: ' + str(error))
            self.error_handling(serv_id, t.GK_CREATE, error)

        self.start_next_task(serv_id)

    def vnf_unchain(self, serv_id):
        """
        This method instructs the IA to unchain the functions in the service.
        """

        return

        # nsd = self.services[serv_id]['nsd']
        # if 'forwarding_graphs' not in nsd:
        #     msg = ": No forwarding graph, no unchaining"
        #     LOG.info("Service " + serv_id + msg)
        #     return

        # msg = ": Deconfiguring the chaining of the service"
        # LOG.info("Service " + serv_id + msg)

        # corr_id = str(uuid.uuid4())
        # self.services[serv_id]['act_corr_id'] = corr_id

        # payload = json.dumps({'service_instance_id': serv_id})
        # self.manoconn.call_async(self.IA_unchain_response,
        #                          t.IA_DECONF_CHAIN,
        #                          payload,
        #                          correlation_id=corr_id)

        # # Pause the chain of tasks to wait for response
        # self.services[serv_id]['pause_chain'] = True

    def IA_unchain_response(self, ch, method, prop, payload):
        """
        This method handles the IA response on the unchain request
        """

        # Get the serv_id of this service
        serv_id = tools.servid_from_corrid(self.services,
                                           prop.correlation_id)

        message = yaml.load(payload)

        if message['request_status'] == 'COMPLETED':
            msg = ": Response from IA: Service unchaining succeeded."
            LOG.info("Service " + serv_id + msg)
        else:
            error = message['message']
            msg = ": Response from IA: Service unchaining failed: " + error
            LOG.info("Service " + serv_id + msg)
            self.error_handling(serv_id, t.GK_KILL, error)
            return

        self.start_next_task(serv_id)

    def terminate_service(self, serv_id):
        """
        This method requests the termination of a service to the IA
        """
        LOG.info("Service " + serv_id + ": Requesting IA to terminate service")

        functions = self.services[serv_id]['function']
        self.services[serv_id]['vims_to_resp'] = 0

        self.services[serv_id]['act_corr_id'] = []

        vims_completed = []

        for vnf in functions:
            vim_id = vnf['vim_uuid']
            if vim_id not in vims_completed:
                corr_id = str(uuid.uuid4())
                vims_completed.append(vim_id)
                self.services[serv_id]['act_corr_id'] = corr_id
                self.services[serv_id]['vims_to_resp'] += 1

                payload = json.dumps({'instance_uuid': serv_id,
                                      'vim_uuid': vim_id})
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
        serv_id = tools.servid_from_corrid(self.services,
                                           prop.correlation_id)

        message = yaml.load(payload)

        if message['request_status'] == 'COMPLETED':
            msg = ": Response from IA: Service termination succeeded."
            LOG.info("Service " + serv_id + msg)
        else:
            error = message['message']
            msg = ": IA response: Service termination failed: " + error
            LOG.info("Service " + serv_id + msg)
            self.error_handling(serv_id, t.GK_KILL, error)
            return

        self.services[serv_id]['vims_to_resp'] -= 1
        if self.services[serv_id]['vims_to_resp'] == 0:
            self.start_next_task(serv_id)

    def terminate_ssms(self, serv_id, require_resp=False):
        """
        This method contacts the SMR to terminate the running ssms.
        """

        if self.services[serv_id]['ssm']:
            corr_id = str(uuid.uuid4())
            self.services[serv_id]['act_corr_id'] = corr_id

            LOG.info("Service " + serv_id + ": Setting kill flag for ssms.")

            nsd = self.services[serv_id]['nsd']

            for ssm in nsd['service_specific_managers']:
                if 'options' not in ssm.keys():
                    ssm['options'] = []
                ssm['options'].append({'key': 'termination', 'value': 'true'})

            msg = ": SSM part of NSD: " + str(nsd['service_specific_managers'])
            LOG.info("Service " + serv_id + msg)

            payload = yaml.dump({'NSD': nsd, 'UUID': serv_id})

            if require_resp:
                self.manoconn.call_async(self.ssm_termination_response,
                                         t.SSM_TERM,
                                         payload,
                                         correlation_id=corr_id)

                # Pause the chain of tasks to wait for response
                self.services[serv_id]['pause_chain'] = True

            else:
                self.manoconn.call_async(self.no_resp_needed,
                                         t.SSM_TERM,
                                         payload)

    def ssm_termination_response(self, ch, method, prop, payload):
        """
        This method handles a response from the SMR on the ssm termination
        call.
        """
        # Get the serv_id of this service
        serv_id = tools.servid_from_corrid(self.services,
                                           prop.correlation_id)

        message = yaml.load(payload)
        LOG.info("Response from SMR: " + str(message))

        self.start_next_task(serv_id)

    def terminate_fsms(self, serv_id, require_resp=True):
        """
        This method contacts the SMR to terminate the running ssms.
        """
        for vnf in self.services[serv_id]['function']:

            if 'function_specific_managers' in vnf['vnfd'].keys():

                # If the vnf has fsms, continue with this process.
                corr_id = str(uuid.uuid4())
                self.services[serv_id]['act_corr_id'] = corr_id

                LOG.info("Service " + serv_id +
                         ": Setting termination flag for fsms.")

                LOG.info(str(vnf['vnfd']))
                for fsm in vnf['vnfd']['function_specific_managers']:
                    if 'options' not in fsm.keys():
                        fsm['options'] = []
                    fsm['options'].append({'key': 'termination',
                                          'value': 'true'})

                vnfd = vnf['vnfd']
                fsm_segment = str(vnfd['function_specific_managers'])
                msg = ": FSM in VNFD: " + fsm_segment
                LOG.info("Service " + serv_id + msg)

                payload = yaml.dump({'VNFD': vnf['vnfd'], 'UUID': vnf['id']})

                self.manoconn.call_async(self.no_resp_needed,
                                         t.FSM_TERM,
                                         payload)

    def fsm_termination_response(self, ch, method, prop, payload):
        """
        This method handles a response from the SMR on the ssm termination
        call.
        """
        serv_id = tools.servid_from_corrid(self.services,
                                           prop.correlation_id)

        message = yaml.load(payload)
        LOG.info("Response from SMR: " + str(message))

        self.start_next_task(serv_id)

    def no_resp_needed(self, ch, method, prop, payload):
        """
        Dummy response method when other component will send a response, but
        SLM does not need it
        """

        pass

    def update_records_to_terminated(self, serv_id):
        """
        This method updates the records of the service and function instances
        to reflect that they have been terminated.
        """

        error = None

        nsr = self.services[serv_id]['nsr']

        # Updating the version number
        old_version = int(nsr['version'])
        cur_version = old_version + 1
        nsr['version'] = str(cur_version)

        # Updating the record
        nsr_id = serv_id
        nsr['status'] = "terminated"
        nsr['id'] = nsr_id

        # Put it
        url = t.nsr_path + '/' + nsr_id
        header = {'Content-Type': 'application/json'}

        LOG.info("Service " + serv_id + ": NSR update: " + url)

        try:
            nsr_resp = requests.put(url,
                                    data=json.dumps(nsr),
                                    headers=header,
                                    timeout=1.0)
            nsr_resp_json = str(nsr_resp.json())

            if (nsr_resp.status_code == 200):
                msg = ": NSR update accepted for " + nsr_id
                LOG.info("Service " + serv_id + msg)
            else:
                msg = ": NSR update not accepted: " + nsr_resp_json
                LOG.info("Service " + serv_id + msg)
                error = {'http_code': nsr_resp.status_code,
                         'message': nsr_resp_json}
        except:
            error = {'http_code': '0',
                     'message': 'Timeout when contacting NSR repo'}

        for vnf in self.services[serv_id]['function']:
            vnfr = vnf["vnfr"]
            vnfr_id = vnf["id"]

            # Updating version number
            old_version = int(vnfr['version'])
            cur_version = old_version + 1
            vnfr['version'] = str(cur_version)

            # Updating the record
            vnfr['status'] = "terminated"
            vnfr["id"] = vnfr_id

            # Put it
            url = t.vnfr_path + '/' + vnfr_id
            header = {'Content-Type': 'application/json'}

            LOG.info("Service " + serv_id + ": VNFR update: " + url)

            try:
                vnfr_resp = requests.put(url,
                                         data=json.dumps(vnfr),
                                         headers=header,
                                         timeout=1.0)
                vnfr_resp_json = str(vnfr_resp.json())

                if (vnfr_resp.status_code == 200):
                    msg = ": VNFR update accepted for " + vnfr_id
                    LOG.info("Service " + serv_id + msg)
                else:
                    msg = ": VNFR update not accepted: " + vnfr_resp_json
                    LOG.info("Service " + serv_id + msg)
                    error = {'http_code': vnfr_resp.status_code,
                             'message': vnfr_resp_json}
            except:
                error = {'http_code': '0',
                         'message': 'Timeout when contacting VNFR repo'}

        if error is not None:
            self.error_handling(serv_id, t.GK_KILL, error)

    def wan_configure(self, serv_id):
        """
        This method configures the WAN of a service
        """

        LOG.info("Service " + serv_id + ": WAN Configuration")

        self.services[serv_id]['vls_to_resp'] = 0
        self.services[serv_id]['act_corr_id'] = []
        nsd = self.services[serv_id]['nsd']
        vnfs = self.services[serv_id]['function']

        vl_map = self.services[serv_id]['mapping']['service']['vl']
        vnf_map = self.services[serv_id]['mapping']['function']

        for vl in nsd['virtual_links']:
            if vl['id'] in vl_map.keys():
                if 'wim_id' not in vl_map[vl['id']].keys():
                    continue
                for vl_for_wim in vl_map[vl['id']]['pairs']:
                    if not vl_for_wim['new']:
                        continue
                    LOG.info("Service " + serv_id + ": new VL for WAN identified")
                    message = {}
                    message['service_instance_id'] = serv_id
                    message['vl_id'] = vl['id']
                    message['wim_uuid'] = vl_map[vl['id']]['wim_id']
                    message['bidirectional'] = True
                    if 'qos_requirements' in vl.keys():
                        message['qos'] = vl['qos_requirements']

                    LOG.info(yaml.dump(vl_for_wim))
                    vl_for_wim['naps'] = []
                    for ref in vl_for_wim['refs']:
                        if ':' not in ref:
                            index = int(ref.split('+')[-1])
                            if 'ingress' in vl_for_wim.keys():
                                nap = self.services[serv_id]['ingress'][index]['nap']
                            if 'egress' in vl_for_wim.keys():
                                nap = self.services[serv_id]['egress'][index]['nap']
                        else:
                            nap = tools.find_ip_from_ref(ref.split('_')[0],
                                                         nsd,
                                                         vnfs,
                                                         vnf_map,
                                                         vnf_id=ref.split('_')[-1][-36:])
                        vl_for_wim['naps'].append(nap)

                    message['ingress'] = {}
                    first_node = vl_for_wim['nodes'][0]
                    first_nap = vl_for_wim['naps'][0]
                    message['ingress']['location'] = first_node
                    message['ingress']['nap'] = first_nap
                    message['egress'] = {}
                    sec_node = vl_for_wim['nodes'][1]
                    sec_nap = vl_for_wim['naps'][1]
                    message['egress']['location'] = sec_node
                    message['egress']['nap'] = sec_nap

                    msg = ": message for WAN: " + str(message)
                    LOG.info("Service " + serv_id + msg)

                    corr_id = str(uuid.uuid4())
                    self.services[serv_id]['act_corr_id'].append(corr_id)
                    self.services[serv_id]['vls_to_resp'] += 1

                    # Pause the chain of tasks to wait for response
                    self.services[serv_id]['pause_chain'] = True

                    self.manoconn.call_async(self.wan_configure_response,
                                             t.IA_CONF_WAN,
                                             yaml.dump(message),
                                             correlation_id=corr_id)


    def wan_configure_response(self, ch, method, prop, payload):
        """
        This method handles the IA response to the WAN request
        """
        # Get the serv_id of this service
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        message = yaml.load(payload)

        LOG.info("Service " + serv_id + ": WAN configure request completed.")

        if message['request_status'] != 'COMPLETED':
            error = message['message']
            LOG.info('Error occured during WAN: ' + str(error))
            self.error_handling(serv_id, t.GK_CREATE, error)

        self.services[serv_id]['vls_to_resp'] -= 1

        if self.services[serv_id]['vls_to_resp'] == 0:
            self.start_next_task(serv_id)

    def wan_deconfigure(self, serv_id):
        """
        This method will deconfigure the WAN
        """

        LOG.info("Service " + serv_id + ": WAN Deconfiguration")

        self.services[serv_id]['vls_to_resp'] = 0
        self.services[serv_id]['act_corr_id'] = []

        vls = self.services[serv_id]['mapping']['service']['vl']

        for vl_id in vls.keys():
            vl = vls[vl_id]
            if 'wim_id' in vl.keys():
                message = {}
                message['wim_uuid'] = vl['wim_id']
                message['service_instance_id'] = serv_id
                message['vl_id'] = vl_id

                msg = ": message for WAN: " + str(message)
                LOG.info("Service " + serv_id + msg)

                corr_id = str(uuid.uuid4())
                self.services[serv_id]['act_corr_id'].append(corr_id)
                self.services[serv_id]['vls_to_resp'] += 1

                # Pause the chain of tasks to wait for response
                self.services[serv_id]['pause_chain'] = True

                self.manoconn.call_async(self.wan_deconfigure_response,
                                         t.IA_DECONF_WAN,
                                         yaml.dump(message),
                                         correlation_id=corr_id)

    def wan_deconfigure_response(self, ch, method, prop, payload):
        """
        This method handles responses on the wan_deconfigure call
        """

        # Get the serv_id of this service
        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)

        message = yaml.load(payload)

        LOG.info("Service " + serv_id + ": WAN deconfigure request completed.")

        if message['request_status'] != 'COMPLETED':
            error = message['message']
            LOG.info('Error occured during WAN: ' + str(error))
            self.error_handling(serv_id, t.GK_CREATE, error)

        self.services[serv_id]['vls_to_resp'] -= 1

        if self.services[serv_id]['vls_to_resp'] == 0:
            self.start_next_task(serv_id)

    def stop_monitoring(self, serv_id):
        """
        This method stops the monitoring of a service.
        """

        url = t.monitoring_path + "/services/" + serv_id
        msg = ": Stopping Monitoring by sending on " + url
        LOG.info("Service " + serv_id + msg)

        error = None
        # try:
        header = {'Content-Type': 'application/json'}
        mon_resp = requests.delete(url,
                                   headers=header,
                                   timeout=10.0)
        msg = ": response from monitoring manager: " + str(mon_resp)
        LOG.info("Service " + serv_id + msg)

        if (mon_resp.status_code == 204):
            LOG.info("Service " + serv_id + ": Monitoring DEL msg accepted")
        elif (mon_resp.status_code == 404):
            LOG.info("Service " + serv_id + ": No such service in monitoring")
        else:
            monitoring_json = mon_resp.json()
            LOG.info("Service " + serv_id + ": Monitoring DEL msg not acceptd")
            msg = ": Monitoring response: " + str(monitoring_json)
            LOG.info("Service " + serv_id + msg)
            error = {'http_code': mon_resp.status_code,
                     'message': monitoring_json}

        # except:
        #     LOG.info('timeout on monitoring communication.')
        #     error = {'http_code': '0',
        #              'message': 'Timeout when contacting monitoring manager'}

        # If an error occured, the workflow is aborted and the GK is informed
        if error is not None:
            self.error_handling(serv_id, t.GK_KILL, error)

        return

    def start_monitoring(self, serv_id):
        """
        This method instructs the monitoring manager to start monitoring
        """

        # # Disabling monitoring for cloudnative services
        # if self.services[serv_id]['cnf']:
        #     msg = ": No monitoring because of CNF presence."
        #     LOG.info("Service " + serv_id + msg)
        #     return

        # Configure the Monitoring SSM, if present
        if 'monitor' in self.services[serv_id]['ssm'].keys():
            LOG.info("Service " + serv_id + ": Sending descriptors to Mon SSM")
            message = {}
            message['nsd'] = self.services[serv_id]['nsd']
            message['nsr'] = self.services[serv_id]['nsr']
            vnfs = []
            for vnf in self.services[serv_id]['function']:
                vnfs.append({'vnfd': vnf['vnfd'],
                             'id': vnf['id'],
                             'vnfr': vnf['vnfr']})
            message['vnfs'] = vnfs

            if 'ingress' in self.services[serv_id].keys():
                message['ingress'] = self.services[serv_id]['ingress']
            else:
                message['ingress'] = None
            if 'egress' in self.services[serv_id].keys():
                message['egress'] = self.services[serv_id]['egress']
            else:
                message['egress'] = None

            message['ssm_type'] = 'monitor'
            topic = 'generic.ssm.' + serv_id

            ssm_conn = self.ssm_connections[serv_id]

            ssm_conn.notify(topic, yaml.dump(message))

            # subscribe to messages from the monitoring SSM
            topic = t.FROM_MON_SSM + serv_id
            ssm_conn.subscribe(self.from_monitoring_ssm, topic)

        LOG.info("Service " + serv_id + ": Setting up Monitoring Manager")
        service = self.services[serv_id]
        functions = self.services[serv_id]['function']
        userdata = self.services[serv_id]['user_data']

        mon_mess = tools.build_monitoring_message(service, functions, userdata)

        LOG.info("Monitoring message created: \n" + yaml.dump(mon_mess))

        error = None
        try:
            header = {'Content-Type': 'application/json'}
            mon_resp = requests.post(t.monitoring_path + '/services',
                                     data=json.dumps(mon_mess),
                                     headers=header,
                                     timeout=10.0)
            if (mon_resp.status_code == 200):
                LOG.info("Service " + serv_id + ": Monitoring started")

            else:
                LOG.info("Service " + serv_id + ": Monitoring msg not accepted")
                LOG.info("Service " + serv_id + ": Monitoring code " + str(mon_resp.status_code)) 

                msg = ": Monitoring response: " + str(mon_resp.text)
                LOG.info("Service " + serv_id + msg)
                error = {'http_code': mon_resp.status_code,
                         'message': mon_resp.text}
        except:
            LOG.info("Service " + serv_id + ": timeout on monitoring server.")
            error = {'http_code': '0',
                     'message': 'Timeout when contacting server'}

        # If an error occured, the workflow is aborted and the GK is informed
        if error is not None:
            self.error_handling(serv_id, t.GK_CREATE, error)

        return

    def inform_gk_instantiation(self, serv_id):
        """
        This method informs the gatekeeper.
        """
        LOG.info("Service " + serv_id + ": Reporting result to GK")

        message = {}

        message['status'] = 'READY'
        message['error'] = None
        message['timestamp'] = time.time()
        message['sla_id'] = self.services[serv_id]['sla_id']
        message['policy_id'] = self.services[serv_id]['policy_id']
        message['nsr'] = self.services[serv_id]['nsr']
        message['vnfrs'] = []

        for function in self.services[serv_id]['function']:
            message['vnfrs'].append(function['vnfr'])

        LOG.debug("Payload of message " + str(message))

        orig_corr_id = self.services[serv_id]['original_corr_id']
        self.manoconn.notify(t.GK_CREATE,
                             yaml.dump(message),
                             correlation_id=orig_corr_id)

    def inform_gk(self, serv_id):
        """
        This method informs the gatekeeper.
        """
        topic = self.services[serv_id]['topic']

        LOG.info("Service " + serv_id + ": Reporting result on " + topic)

        message = {}

        message['status'] = 'READY'
        message['workflow'] = self.services[serv_id]['current_workflow']
        message['error'] = None
        message['timestamp'] = time.time()
        message['nsr'] = self.services[serv_id]['nsr']
        message['vnfrs'] = []

        for function in self.services[serv_id]['function']:
            message['vnfrs'].append(function['vnfr'])

        if 'start_time' in self.services[serv_id]:
            start_time = self.services[serv_id]['start_time']
            message['duration'] = time.time() - start_time

        LOG.debug("Payload of message " + str(message))

        orig_corr_id = self.services[serv_id]['original_corr_id']
        self.manoconn.notify(topic,
                             yaml.dump(message),
                             correlation_id=orig_corr_id)


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
        self.services[serv_id]['nsd'] = payload['NSD']

        self.services[serv_id]['id'] = serv_id
        self.services[serv_id]['cnf'] = False

        msg = ": NSD uuid is " + str(payload['NSD']['uuid'])
        LOG.info("Service " + serv_id + msg)

        msg = ": NSD name is " + str(payload['NSD']['name'])
        LOG.info("Service " + serv_id + msg)

        nsd = self.services[serv_id]['nsd']

        # Adjust for flavour
        self.services[serv_id]['flavour'] = None
        if 'flavor' in payload.keys():
            if payload['flavor']:
                self.services[serv_id]['flavour'] = payload['flavor']
        elif 'flavour' in payload.keys():
            if payload['flavour']:
                self.services[serv_id]['flavour'] = payload['flavour']
        msg = str(self.services[serv_id]['flavour'])
        LOG.info("The selected flavour is: " + msg)

        if self.services[serv_id]['flavour']:
            flavour_dict = {}
            for flavour in nsd['deployment_flavours']:
                if flavour['name'] == self.services[serv_id]['flavour']:
                    flavour_dict = flavour
                    break

            for key in flavour_dict.keys():
                if key != 'name':
                    nsd[key] = flavour_dict[key] 

            if 'deployment_flavours' in nsd:
                del nsd['deployment_flavours']

        self.services[serv_id]['function'] = []
        for key in payload.keys():
            if key[:4] == 'VNFD':
                vnf_id = str(uuid.uuid4())
                msg = "VNFD instance id generated: " + vnf_id
                LOG.info("Service " + serv_id + msg)
                vnfd = payload[key]
                vnf_base = {'start': {'trigger': True, 'payload': {}},
                            'stop': {'trigger': True, 'payload': {}},
                            'configure': {'trigger': True, 'payload': {}},
                            'scale': {'trigger': True, 'payload': {}},
                            'vnfd': vnfd,
                            'id': vnf_id,
                            'flavour':None}

                for vnf_nsd in nsd['network_functions']:
                    if vnf_nsd['vnf_name'] == vnfd['name'] and \
                       vnf_nsd['vnf_vendor'] == vnfd['vendor'] and \
                       vnf_nsd['vnf_version'] == vnfd['version']:
                        if vnf_nsd.get('vnf_flavour'):
                            vnf_base['flavour'] = vnf_nsd['vnf_flavour']

                            flavour_dict = {}

                            for flavour in vnfd['deployment_flavours']:
                                if flavour['name'] == vnf_base['flavour']:
                                    flavour_dict = flavour
                                    break

                            for key in flavour_dict.keys():
                                if key != 'name':
                                    vnfd[key] = flavour_dict[key] 

                if 'virtual_deployment_units' in vnf_base['vnfd'].keys():
                    for vdu in vnf_base['vnfd']['virtual_deployment_units']:
                        vdu['id'] = vdu['id'] + '-' + vnf_id
                if 'cloudnative_deployment_units' in vnf_base['vnfd'].keys():
                    self.services[serv_id]['cnf'] = True
                    for vdu in vnf_base['vnfd']['cloudnative_deployment_units']:
                        vdu['id'] = vdu['id'] + '-' + vnf_id
                self.services[serv_id]['function'].append(vnf_base)

        # Add to correlation id to the ledger
        self.services[serv_id]['original_corr_id'] = corr_id

        # Add payload to the ledger
        self.services[serv_id]['payload'] = payload

        self.services[serv_id]['infrastructure'] = {}

        # Create the service schedule
        self.services[serv_id]['schedule'] = []

        # Create the SSM dict if SSMs are defined in NSD
        ssm_dict = tools.get_sm_from_descriptor(payload['NSD'])
        self.services[serv_id]['ssm'] = ssm_dict

        print(self.services[serv_id]['ssm'])

        # Create counter for vnfs
        self.services[serv_id]['vnfs_to_resp'] = 0
        self.services[serv_id]['vims_to_resp'] = 0

        # Create the chain pause and kill flag
        self.services[serv_id]['pause_chain'] = False
        self.services[serv_id]['kill_chain'] = False

        # Create IP Mapping
        self.services[serv_id]['ip_mapping'] = []

        # Add ingress and egress fields
        self.services[serv_id]['ingress'] = None
        self.services[serv_id]['egress'] = None

        if 'ingresses' in payload.keys():
            if payload['ingresses']:
                if payload['ingresses'] != '[]':
                    self.services[serv_id]['ingress'] = payload['ingresses']

        if 'egresses' in payload.keys():
            if payload['egresses']:
                if payload['ingresses'] != '[]':
                    self.services[serv_id]['egress'] = payload['egresses']

        # Add user data to ledger
        self.services[serv_id]['user_data'] = payload['user_data']

        # Add user defined mapping input to ledger
        self.services[serv_id]['input_mapping'] = {'vnfs':[], 'vls':[]}
        int_map = self.services[serv_id]['input_mapping']
        if 'mapping' in payload.keys():
            ext_map = payload['mapping']
            if 'network_functions' in ext_map.keys():
                int_map['vnfs'] = ext_map['network_functions']
            if 'virtual_links' in ext_map.keys():
                int_map['vls'] = ext_map['virtual_links']

        # Add keys to ledger
        try:
            keys = payload['user_data']['customer']['keys']
            self.services[serv_id]['public_key'] = keys['public']
            self.services[serv_id]['private_key'] = keys['private']
        except:
            msg = ": extracting keys failed " + str(payload['user_data'])
            LOG.info("Service " + serv_id + msg)
            self.services[serv_id]['public_key'] = None
            self.services[serv_id]['private_key'] = None

        LOG.info("Public key: " + str(self.services[serv_id]['public_key']))

        # Add customer constraints to ledger

        if 'policies' in payload['user_data']['customer'].keys():
            policies = payload['user_data']['customer']['policies']
            self.services[serv_id]['customer_policies'] = policies
        else:
            self.services[serv_id]['customer_policies'] = {}

        # Add policy and sla id
        self.services[serv_id]['sla_id'] = None
        self.services[serv_id]['policy_id'] = None

        customer = payload['user_data']['customer']
        if 'sla_id' in customer.keys():
            if customer['sla_id'] != '':
                self.services[serv_id]['sla_id'] = customer['sla_id']

        if 'policy_id' in customer.keys():
            if customer['policy_id'] != '':
                self.services[serv_id]['policy_id'] = customer['policy_id']

        return serv_id

    def recreate_ledger(self, corr_id, serv_id):
        """
        This method recreates an entry in the ledger for a service
        based on the service instance id.

        :param corr_id: the correlation id of the received message
        :param serv_id: the service instance id
        """

        def request_returned_with_error(request, file_type):
            code = str(request['error'])
            err = str(request['content'])
            msg = "Retrieving of " + file_type + ": " + code + " " + err
            LOG.info("Service " + serv_id + ': ' + msg)
            self.services[serv_id]['error'] = msg

        # base of the ledger
        self.services[serv_id] = {}
        self.services[serv_id]['original_corr_id'] = corr_id
        self.services[serv_id]['schedule'] = []
        self.services[serv_id]['kill_chain'] = False
        self.services[serv_id]['infrastructure'] = {}
        self.services[serv_id]['vnfs_to_resp'] = 0
        self.services[serv_id]['vims_to_resp'] = 0
        self.services[serv_id]['pause_chain'] = False
        self.services[serv_id]['error'] = None
        self.services[serv_id]['ip_mapping'] = []
        self.services[serv_id]['ingress'] = None
        self.services[serv_id]['egress'] = None
        self.services[serv_id]['public_key'] = None
        self.services[serv_id]['private_key'] = None
        self.services[serv_id]['cnf'] = False

        self.services[serv_id]['user_data'] = {}
        self.services[serv_id]['user_data']['customer'] = {}
        self.services[serv_id]['user_data']['developer'] = {}
        self.services[serv_id]['user_data']['customer']['email'] = None
        self.services[serv_id]['user_data']['customer']['phone'] = None
        self.services[serv_id]['user_data']['developer']['email'] = None
        self.services[serv_id]['user_data']['developer']['phone'] = None
        self.services[serv_id]['customer_policies'] = {}
        self.services[serv_id]['input_mapping'] = {'vnfs':[], 'vls':[]}

        # Retrieve the service record based on the service instance id
        base = t.nsr_path + "/"
        LOG.info("Requesting NSR for: " + str(base) + str(serv_id))
        request = tools.getRestData(base, serv_id)

        if request['error'] is not None:
            request_returned_with_error(request, 'NSR')
            return None

        self.services[serv_id]['nsr'] = request['content']
        del self.services[serv_id]['nsr']["uuid"]
        del self.services[serv_id]['nsr']["updated_at"]
        del self.services[serv_id]['nsr']["created_at"]
        LOG.info("Service " + serv_id + ": Recreating ledger: NSR retrieved.")

        # Retrieve the NSD
        nsr = self.services[serv_id]['nsr']
        self.services[serv_id]['nsr']['id'] = serv_id
        nsd_uuid = nsr['descriptor_reference']

        head = {'content-type': 'application/x-yaml'}
        LOG.info("Request NSD for: " + str(t.nsd_path + '/') + str(nsd_uuid))
        request = tools.getRestData(t.nsd_path + '/', nsd_uuid, header=head)

        if request['error'] is not None:
            request_returned_with_error(request, 'NSD')
            return None

        self.services[serv_id]['nsd'] = request['content']['nsd']
        self.services[serv_id]['nsd']['uuid'] = nsd_uuid
        LOG.info("Service " + serv_id + ": Recreating ledger: NSD retrieved.")

        nsd = self.services[serv_id]['nsd']

        # adjust for flavour
        self.services[serv_id]['flavour'] = nsr.get('flavour')

        if self.services[serv_id]['flavour']:
            flavour_dict = {}
            for flavour in nsd['deployment_flavours']:
                if flavour['name'] == self.services[serv_id]['flavour']:
                    flavour_dict = flavour
                    break

            for key in flavour_dict.keys():
                if key != 'name':
                    nsd[key] = flavour_dict[key] 

        if 'deployment_flavours' in nsd:
            del nsd['deployment_flavours']

        # Retrieve the function records based on the service record
        self.services[serv_id]['function'] = []
        nsr = self.services[serv_id]['nsr']
        for vnf in nsr['network_functions']:
            base = t.vnfr_path + "/"
            request = tools.getRestData(base, vnf['vnfr_id'])

            if request['error'] is not None:
                request_returned_with_error(request, 'VNFR')
                return None

            if 'virtual_deployment_units' in request['content'].keys():
                vdu = request['content']['virtual_deployment_units'][0]
                vim_id = vdu['vnfc_instance'][0]['vim_id']

            if 'cloudnative_deployment_units' in request['content'].keys():
                self.services[serv_id]['cnf'] = True
                vdu = request['content']['cloudnative_deployment_units'][0]
                vim_id = vdu['vim_id']
            
            new_function = {'id': vnf['vnfr_id'],
                            'start': {'trigger': True, 'payload': {}},
                            'stop': {'trigger': True, 'payload': {}},
                            'configure': {'trigger': True, 'payload': {}},
                            'scale': {'trigger': True, 'payload': {}},
                            'vnfr': request['content'],
                            'vim_uuid': vim_id,
                            'flavour': request['content'].get('flavour')}

            del new_function['vnfr']['updated_at']
            del new_function['vnfr']['created_at']
            del new_function['vnfr']['uuid']

            new_function['vnfr']['id'] = vnf['vnfr_id']

            self.services[serv_id]['function'].append(new_function)
            msg = ": Recreating ledger: VNFR retrieved."
            LOG.info("Service " + serv_id + msg)

        # Retrieve the VNFDS based on the function records
        for vnf in self.services[serv_id]['function']:
            vnfd_id = vnf['vnfr']['descriptor_reference']

            req = tools.getRestData(t.vnfd_path + '/', vnfd_id, header=head)

            if req['error'] is not None:
                request_returned_with_error(req, 'VNFD')
                return None

            vnf['vnfd'] = req['content']['vnfd']
            vnf['vnfd']['uuid'] = vnfd_id

            if 'virtual_deployment_units' in vnf['vnfd'].keys():
                for vdu in vnf['vnfd']['virtual_deployment_units']:
                    vdu['id'] = vdu['id'] + '-' + vnf['id']
            if 'cloudnative_deployment_units' in vnf['vnfd'].keys():
                for vdu in vnf['vnfd']['cloudnative_deployment_units']:
                    vdu['id'] = vdu['id'] + '-' + vnf['id']

            LOG.info("Service " + serv_id + ": Recreate: VNFD retrieved.")

            if vnf['flavour']:
                flavour_dict = {}

                for flavour in vnf['vnfd']['deployment_flavours']:
                    if flavour['name'] == vnf['flavour']:
                        flavour_dict = flavour
                        break

                for key in flavour_dict.keys():
                    if key != 'name':
                        vnf['vnfd'][key] = flavour_dict[key] 

        LOG.info("Serice " +
                 serv_id + ": Recreating ledger: VNFDs retrieved.")

        # Retrieve the deployed SSMs based on the NSD
        nsd = self.services[serv_id]['nsd']
        ssm_dict = tools.get_sm_from_descriptor(nsd)

        self.services[serv_id]['ssm'] = ssm_dict

        # Recreate connection with SSM
        if bool(ssm_dict) and serv_id not in self.ssm_connections.keys():
            url = self.ssm_url_base + 'ssm-' + serv_id
            ssm_conn = messaging.ManoBrokerRequestResponseConnection(self.name,
                                                                     url=url)

            self.ssm_connections[serv_id] = ssm_conn


        # Retrieve the deployed FSMs based on the VNFD
        for vnf in self.services[serv_id]['function']:
            vnfd = vnf['vnfd']
            fsm_dict = tools.get_sm_from_descriptor(vnfd)
            vnf['fsm'] = fsm_dict

        LOG.info(yaml.dump(self.services[serv_id]))
        return True

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
            msg = ": Validation of request completed. Status: Not a Dict"
            LOG.info("Service " + serv_id + msg)
            response = "Request " + corr_id + ": payload is not a dict."
            self.services[serv_id]['status'] = 'ERROR'
            self.services[serv_id]['error'] = response
            return

        # The dictionary should contain a 'NSD' key
        if 'NSD' not in payload.keys():
            msg = ": Validation of request completed. Status: No NSD"
            LOG.info("Service " + serv_id + msg)
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
            msg = ": Validation request completed. Number of VNFDs incorrect"
            LOG.info("Service " + serv_id + msg)
            response = "Request " + corr_id + ": # of VNFDs doesn't match NSD."
            self.services[serv_id]['status'] = 'ERROR'
            self.services[serv_id]['error'] = response
            return

        # Check whether VNFDs are empty.
        for key in payload.keys():
            if key[:4] == 'VNFD':
                if payload[key] is None:
                    msg = ": Validation request completed. Empty VNFD"
                    LOG.info("Service " + serv_id + msg)
                    response = "Request " + corr_id + ": empty VNFD."
                    self.services[serv_id]['status'] = 'ERROR'
                    self.services[serv_id]['error'] = response
                    return

        msg = ": Validation of request completed. Status: Instantiating"
        LOG.info("Service " + serv_id + msg)
        # If all tests succeed, the status changes to 'INSTANTIATING'
        message = {'status': 'INSTANTIATING', 'error': None}
        self.services[serv_id]['status'] = 'INSTANTIATING'
        self.services[serv_id]['error'] = None
        return

    def SLM_mapping(self, serv_id):
        """
        This method is used if the MANO is responsible for the placement.

        :param serv_id: The instance uuid of the service
        """
        corr_id = str(uuid.uuid4())
        self.services[serv_id]['act_corr_id'] = corr_id

        LOG.info("Service " + serv_id + ": Calculating the placement")
        topology = {}
        topology['vims'] = self.services[serv_id]['infrastructure']['vims']
        topology['wims'] = self.services[serv_id]['infrastructure']['wims']
        NSD = self.services[serv_id]['nsd']
        functions = self.services[serv_id]['function']
        operator_policies = self.services[serv_id]['operator_policies']
        customer_policies = self.services[serv_id]['customer_policies']
        predefined_mapping = self.services[serv_id]['mapping']

        content = {'nsd': NSD,
                   'functions': functions,
                   'topology': topology,
                   'serv_id': serv_id,
                   'operator_policies': operator_policies,
                   'customer_policies': customer_policies,
                   'vnf_single_pop': True,
                   'predefined_mapping': predefined_mapping}

        content['nap'] = {}
        content['nap']['ingresses'] = self.services[serv_id]['ingress']
        content['nap']['egresses'] = self.services[serv_id]['egress']

        self.manoconn.call_async(self.resp_mapping,
                                 t.MANO_PLACE,
                                 yaml.dump(content),
                                 correlation_id=corr_id)

        self.services[serv_id]['pause_chain'] = True
        LOG.info("Service " + serv_id + ": Placement request sent")

    def resp_mapping(self, ch, method, prop, payload):
        """
        This method handles the response on a mapping request
        """
        content = yaml.load(payload)
        mapping = content["mapping"]

        serv_id = tools.servid_from_corrid(self.services, prop.correlation_id)
        LOG.info("Service " + serv_id + ": Placement response received")

        if mapping is None or mapping == {}:
            # The GK should be informed that the placement failed and the
            # deployment was aborted.
            LOG.info("Service " + serv_id + ": Placement not possible")
            self.error_handling(serv_id,
                                t.GK_CREATE,
                                'Unable to perform placement.')

            return

        else:
            # Add mapping to ledger
            LOG.info("Service " + serv_id + ": Placement completed")
            LOG.debug("Calculated SLM placement: " + str(mapping))
            self.services[serv_id]['calculated_mapping'] = mapping

        LOG.info(yaml.dump(self.services[serv_id]['calculated_mapping']))
        LOG.info(yaml.dump(self.services[serv_id]['mapping']))
        self.start_next_task(serv_id)

    def consolidate_mapping(self, serv_id):
        """
        This method merges the consolidated predefined mapping with the
        additional mapping calculations done by the placement plugin.
        """

        LOG.info(yaml.dump(self.services[serv_id]))

        calc_map = self.services[serv_id]['calculated_mapping']
        pred_map = self.services[serv_id]['mapping']

        mapping = pred_map

        for vnf_id in pred_map['function'].keys():
            if pred_map['function'][vnf_id]['vim_id'] is None:
                mapping['function'][vnf_id]['vim_id'] = calc_map['du'][vnf_id]
                mapping['function'][vnf_id]['new'] = True
                for vnf in self.services[serv_id]['function']:
                    vnf['vim_uuid'] = mapping['function'][vnf['id']]['vim_id']
        for vl_id in calc_map['vl'].keys():
            vl = calc_map['vl'][vl_id]
            if vl_id not in mapping['service']['vl'].keys():
                mapping['service']['vl'][vl_id] = {}
                mapping['service']['vl'][vl_id]['new'] = True
                name = serv_id + '_ns_' + vl_id
                mapping['service']['vl'][vl_id]['id'] = name
                if 'vim_id' in vl[0].keys():
                    mapping['service']['vl'][vl_id]['vim_id'] = vl[0]['vim_id'] 
                if 'wim_id' in vl[0].keys():
                    mapping['service']['vl'][vl_id]['wim_id'] = vl[0]['wim_id']
                    mapping['service']['vl'][vl_id]['pairs'] = vl
                    vims = []
                    for vl_det in vl:
                        vl_det['new'] = True
                        if ':' in vl_det['refs'][0]:
                            vims.append(vl_det['nodes'][0])
                        if ':' in vl_det['refs'][1]:
                            vims.append(vl_det['nodes'][1])
                    mapping['service']['vl'][vl_id]['vims'] = list(set(vims))

            else:
                vl_old = mapping['service']['vl'][vl_id]
                if 'vim_id' in vl_old.keys():
                    LOG.info("vl_new" + yaml.dump(vl))
                    LOG.info("vl_old" + yaml.dump(vl_old))
                    added_vims = list(set(vl[0]['vim_id'])\
                                      - set(vl_old['vim_id']))
                    if len(added_vims) > 0:
                        vl_old['update'] = True
                        vl_old['added_vims'] = added_vims
                        vl_old['vim_id'] = vl[0]['vim_id']
                if 'wim_id' in vl_old.keys():
                    LOG.info("vl_new" + yaml.dump(vl))
                    LOG.info("vl_old" + yaml.dump(vl_old))
                    vims = []
                    for pair in vl:
                        if ':' in pair['refs'][0]:
                            vims.append(pair['nodes'][0])
                        if ':' in pair['refs'][1]:
                            vims.append(pair['nodes'][1])
                        new_pair = True
                        for old_pair in vl_old['pairs']:
                            if set(old_pair['refs']) == set(pair['refs']):
                                new_pair = False
                                break
                        if new_pair:
                            vl_old['update'] = True
                            pair['new'] = True
                            vl_old['pairs'].append(pair)
                    net_vims = list(set(vims))
                    vl_old['added_vims'] = list(set(net_vims) - set(vl_old['vims']))

        self.services[serv_id]['mapping'] = mapping

        # Loop over all the new VNFs, and add their virtual links. Check
        # if this virtual link maps on a nsd virtual link.
        nsd = self.services[serv_id]['nsd']
        for vnf_id in mapping['function'].keys():
            vnf_map = mapping['function'][vnf_id]
            if not vnf_map['new']:
                continue
            # find VNFD
            for vnf in self.services[serv_id]['function']:
                if vnf['id'] == vnf_id:
                    vnfd = vnf['vnfd']
                    break
            for vl in vnfd['virtual_links']:
                res = tools.vnfd_vl_maps_on_nsd_vl(nsd, vnfd, vl)
#                nsd_vl_on_vim = False
                if res[1] in mapping['service']['vl'].keys():
                    nsd_vl = mapping['service']['vl'][res[1]]
#                    nsd_vl_on_vim = 'vim_id' in nsd_vl.keys()
                # if res[0] and nsd_vl_on_vim and \
                #    vnf_map['vim_id'] in nsd_vl['vim_id']:
                if res[0]:
                    vnf_map['vl'][vl['id']] = {}
                    vnf_map['vl'][vl['id']]['id'] = nsd_vl['id']
                    vnf_map['vl'][vl['id']]['vim_id'] = vnf_map['vim_id']
                    vnf_map['vl'][vl['id']]['new'] = False
                    vnf_map['vl'][vl['id']]['fip'] = False
                    if 'wim_id' in nsd_vl.keys():
                        vnf_map['vl'][vl['id']]['fip'] = True
                    elif len(nsd_vl['vim_id']) > 1:
                        vnf_map['vl'][vl['id']]['fip'] = True
                    else:
                        for new_nsd_vl in nsd['virtual_links']:
                            if new_nsd_vl['id'] == res[1]:
                                refs = new_nsd_vl['connection_points_reference']
                                break
                        for ref in refs:
                            if ':' not in ref:
                                vnf_map['vl'][vl['id']]['fip'] = True
                                break
                else:
                    vnf_map['vl'][vl['id']] = {}
                    vnf_map['vl'][vl['id']]['id'] = vnf_id + '_vnf_' + vl['id']
                    vnf_map['vl'][vl['id']]['vim_id'] = vnf_map['vim_id']
                    vnf_map['vl'][vl['id']]['new'] = True
                    vnf_map['vl'][vl['id']]['fip'] = False

        msg = ": Final mapping " + yaml.dump(mapping)
        LOG.info("Service " + serv_id + msg)
        return

    def consolidate_predefined_mapping(self, serv_id):
        """
        This method combines the various mapping inputs in a final mapping.
        Input can come from the user (in the instantiation request), records 
        (decided during instantation) or the placement plugin.
        """

        LOG.info(yaml.dump(self.services[serv_id]))
        service = self.services[serv_id]
        functions = self.services[serv_id]['function']

        # Build the mapping template
        mapping = {}
        mapping['service'] = {'vl': {}}
        mapping['function'] = {}

        for vnf in self.services[serv_id]['function']:
            mapping['function'][vnf['id']] = {'vim_id': None,
                                              'vl': {},
                                              'new': True}

        # if this service was already deployed, and this method is called from
        # a workflow updating the service (scaling, migration, termination), 
        # mapping information should be first obtained from the records.
        if 'nsr' in self.services[serv_id].keys():
            nsr = self.services[serv_id]['nsr']
            for vl in nsr['virtual_links']:
                desc = vl['descriptor_reference']
                mapping['service']['vl'][desc] = {}
                mapping['service']['vl'][desc]['id'] = vl['id']
                mapping['service']['vl'][desc]['new'] = False
                if 'vim_id' in vl.keys():
                    mapping['service']['vl'][desc]['vim_id'] = vl['vim_id']
                if 'wim_id' in vl.keys():
                    mapping['service']['vl'][desc]['wim_id'] = vl['wim_id']
                    mapping['service']['vl'][desc]['pairs'] = []
                    vims = []
                    for path in vl['paths']:
                        new_path = {}
                        new_path['new'] = False
                        new_path['refs'] = [path['nodes'][0]['ref'],
                                            path['nodes'][1]['ref']]
                        new_path['nodes'] = [path['nodes'][0]['location'], 
                                             path['nodes'][1]['location']]
                        new_path['naps'] = [path['nodes'][0]['nap'], 
                                            path['nodes'][1]['nap']]
                        mapping['service']['vl'][desc]['pairs'].append(new_path)
                        if ':' in new_path['refs'][0]:
                            vims.append(new_path['nodes'][0])
                        if ':' in new_path['refs'][1]:
                            vims.append(new_path['nodes'][1])
                        mapping['service']['vl'][desc]['vims'] = list(set(vims))

                        # extract ingress and egress info
                        if ':' not in path['nodes'][0]['ref']:
                            if not self.services[serv_id]['ingress']:
                                self.services[serv_id]['ingress'] = []
                            entry = {'location': path['nodes'][0]['location'],
                                     'nap': path['nodes'][0]['nap']}
                            self.services[serv_id]['ingress'].append(entry)

                        if ':' not in path['nodes'][1]['ref']:
                            if not self.services[serv_id]['egress']:
                                self.services[serv_id]['egress'] = []
                            entry = {'location': path['nodes'][1]['location'],
                                     'nap': path['nodes'][1]['nap']}
                            self.services[serv_id]['egress'].append(entry)


        for vnf in self.services[serv_id]['function']:
            if 'vnfr' in vnf.keys():
                vnf_map = mapping['function'][vnf['id']]
                vnfr = vnf['vnfr']
                if 'virtual_deployment_units' in vnfr.keys():
                    vdu = vnfr['virtual_deployment_units'][0]
                    vim_id = vdu['vnfc_instance'][0]['vim_id']
                else:
                    cdu = vnfr['cloudnative_deployment_units'][0]
                    vim_id = cdu['vim_id']
                vnf_map['vim_id'] = vim_id
                vnf_map['new'] = False
                for vl in vnfr['virtual_links']:
                    desc = vl['descriptor_reference']
                    vnf_map['vl'][desc] = {}
                    vnf_map['vl'][desc]['id'] = vl['id']
                    vnf_map['vl'][desc]['new'] = False
                    vnf_map['vl'][desc]['vim_id'] = vl['vim_id']

        msg = ": mapping after records: " + yaml.dump(mapping)
        LOG.info("Service " + serv_id + msg)

        # Fill out any mapping information received from the inst request.
        for vnf_input in service['input_mapping']['vnfs']:
            vim_id = vnf_input['vim_id']
            nsd = service['nsd']
            for vnf_nsd in nsd['network_functions']:
                if vnf_nsd['vnf_id'] == vnf_input['vnf_id']:
                    for vnf in functions:
                        vnf['vim_uuid'] = vim_id
                        if mapping['function'][vnf['id']]['vim_id'] != None:
                            continue
                        vnfd = vnf['vnfd']
                        if vnf_nsd['vnf_name'] == vnfd['name'] and \
                           vnf_nsd['vnf_vendor'] == vnfd['vendor'] and \
                           vnf_nsd['vnf_version'] == vnfd['version']:
                            mapping['function'][vnf['id']]['vim_id'] = vim_id
                            mapping['function'][vnf['id']]['new'] = True
                            break

        for vl_input in service['input_mapping']['vls']:
            vl = None
            for vl_nsd in service['nsd']['virtual_links']:
                if vl_nsd['id'] == vl_input['vl_id']:
                    vl = vl_nsd
                    break
            if vl is None:
                msg = ": vl_id (" + vl_input['vl_id'] + ") not in nsd, ignored"
                LOG.info("Service " + serv_id + msg)
                continue

            if vl['id'] in mapping['service']['vl'].keys():
                msg = ": vl_id (" + vl_input['vl_id'] + ") already has mapping"
                LOG.info("Service " + serv_id + msg)
                continue

            mapping['service']['vl'][vl['id']] = {}                
            mapping['service']['vl'][vl['id']]['id'] = vl_input['external_net']
            mapping['service']['vl'][vl['id']]['new'] = False
            mapping['service']['vl'][vl['id']]['fixed'] = True
            mapping['service']['vl'][vl['id']]['vim_id'] = [vl_input['vim_id']]

        msg = ": mapping after user input: " + yaml.dump(mapping)
        LOG.info("Service " + serv_id + msg)

        # Check if the placement step is still needed, if not, remove it from 
        # the schedule
        placement_needed = False
        for vl in service['nsd']['virtual_links']:
            if 'qos_requirements' in vl.keys():
                if vl['id'] not in mapping['service']['vl'].keys():
                    placement_needed = True
                    break

        for vnf_id in mapping['function'].keys():
            if mapping['function'][vnf_id]['new']:
                placement_needed = True
                break

        if not placement_needed:
            LOG.info("Service " + serv_id + ": Placement plugin not needed")
            schedule = self.services[serv_id]['schedule']
            for x in ['request_topology', 'request_policies', \
                      'SLM_mapping', 'req_placement_from_ssm', \
                      'consolidate_mapping']:
                try:
                    schedule.remove(x)
                except:
                    pass

        self.services[serv_id]['mapping'] = mapping

        return


    def remove_vnfs_from_mapping(self, serv_id):
        """
        Adjust mapping to removed vnfs
        """

        remove_networks = {}
        update_wan_needed = False
        mapping = self.services[serv_id]['mapping']
        functions = self.services[serv_id]['function']
        for vnf in functions:
            if not vnf['stop']['trigger']:
                continue
            vnf_id = vnf['id']
            vim_id = mapping['function'][vnf_id]['vim_id']
            dus = []
            if 'virtual_deployment_units' in vnf['vnfr']:
                dus = vnf['vnfr']['virtual_deployment_units']
            if 'cloudnative_deployment_units' in vnf['vnfr']:
                dus = vnf['vnfr']['cloudnative_deployment_units']
            du_ids = []
            for du in dus:
                du_ids.append(du['id'] + '-' + vnf_id)

            for vl_id in mapping['function'][vnf_id]['vl']:
                vl = mapping['function'][vnf_id]['vl'][vl_id]
                if '_vnf_' in vl['id'] and not '_ns_' in vl['id']:
                    if vim_id not in remove_networks.keys():
                        remove_networks[vim_id] = {'vls': []}
                    remove_networks[vim_id]['vls'].append({'id': vl['id']})

            del mapping['function'][vnf_id]

            for vl_id in mapping['service']['vl']:
                vl = mapping['service']['vl'][vl_id]
                if 'wim_id' in vl.keys():
                    obs_pairs = []
                    for pair in vl['pairs']:
                        pair['new'] = True
                        refs = [x.split(':')[-1] for x in pair['refs']]
                        for du_ref in du_ids:
                            if du_ref in refs:
                                obs_pair.append(vl['pairs'].index(pair))
                                update_wan_needed = True
                                break
                    inv_obs_pairs = obs_pair[::-1]
                    for index in inv_obs_pairs:
                        del vl['pairs'][index]

        if not update_wan_needed:
            self.services[serv_id]['schedule'].remove('wan_configure')
            self.services[serv_id]['schedule'].remove('wan_deconfigure')

        self.services[serv_id]['removed_vls'] = remove_networks

        LOG.info('mapping after removal: ' + yaml.dump(mapping))
        LOG.info('removed networks mapping: ' + yaml.dump(remove_networks))

        return

    def roll_back_instantiation(self, serv_id):
        """
        This method tries to roll back the instantiation workflow if an error
        occured. It will send messages to the SMR and the IA to remove deployed
        SSMs, FSMs and stacks. It will instruct the Repositories to delete the
        records.
        """

        # Kill the stack
        corr_id = str(uuid.uuid4())
        payload = json.dumps({'instance_uuid': serv_id})
        self.manoconn.notify(t.IA_REMOVE,
                             payload,
                             reply_to=t.IA_REMOVE,
                             correlation_id=corr_id)

        # Kill the SSMs and FSMs
        self.terminate_ssms(serv_id, require_resp=False)

        self.terminate_fsms(serv_id, require_resp=False)

        LOG.info("Instantiation aborted, cleanup completed")

        # TODO: Delete the records


def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    TangoLogger.getLogger("son-mano-base:messaging", logging.INFO, log_json=True)
    TangoLogger.getLogger("son-mano-base:plugin", logging.INFO, log_json=True)
#    logging.getLogger("amqp-storm").setLevel(logging.DEBUG)
    # create our service lifecycle manager
    slm = ServiceLifecycleManager()

if __name__ == '__main__':
    main()
