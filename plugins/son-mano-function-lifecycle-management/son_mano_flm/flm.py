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
# import psutil

from sonmanobase.plugin import ManoBasePlugin
import sonmanobase.messaging as messaging

try:
    from son_mano_flm import flm_helpers as tools
except:
    import flm_helpers as tools

try:
    from son_mano_flm import flm_topics as t
except:
    import flm_topics as t

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:flm")
LOG.setLevel(logging.INFO)


class FunctionLifecycleManager(ManoBasePlugin):
    """
    This class implements the Function lifecycle manager.
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
        self.functions = {}

        self.thrd_pool = pool.ThreadPoolExecutor(max_workers=10)

        self.flm_ledger = {}

        self.fsm_connections = {}
        self.fsm_user = 'specific-management'
        self.fsm_pass = 'sonata'
        base = 'amqp://' + self.fsm_user + ':' + self.fsm_pass
        self.fsm_url_base = base + '@son-broker:5672/'

        # call super class (will automatically connect to
        # broker and register the FLM to the plugin manger)
        ver = "0.1-dev"
        des = "This is the FLM plugin"

        super(self.__class__, self).__init__(version=ver,
                                             description=des,
                                             auto_register=auto_register,
                                             wait_for_registration=wait_for_registration,
                                             start_running=start_running)

    def __del__(self):
        """
        Destroy FLM instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics that FLM subscribes on.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()

        # The topic on which deploy requests are posted.
        self.manoconn.subscribe(self.function_instance_create, t.VNF_DEPLOY)

        # The topic on which start requests are posted.
        self.manoconn.subscribe(self.function_instance_start, t.VNF_START)

        # The topic on which configurre requests are posted.
        self.manoconn.subscribe(self.function_instance_config, t.VNF_CONFIG)

        # The topic on which stop requests are posted.
        self.manoconn.subscribe(self.function_instance_stop, t.VNF_STOP)

        # The topic on which stop requests are posted.
        self.manoconn.subscribe(self.function_instance_scale, t.VNF_SCALE)

        # The topic on which terminate requests are posted.
        self.manoconn.subscribe(self.function_instance_kill, t.VNF_KILL)

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
        LOG.info("FLM started and operational.")

    def deregister(self):
        """
        Send a deregister request to the plugin manager.
        """
        LOG.info('Deregistering FLM with uuid ' + str(self.uuid))
        message = {"uuid": self.uuid}
        self.manoconn.notify("platform.management.plugin.deregister",
                             json.dumps(message))
        os._exit(0)

    def on_registration_ok(self):
        """
        This method is called when the FLM is registered to the plugin mananger
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")

##########################
# FLM Threading management
##########################

    def get_ledger(self, func_id):

        return self.functions[func_id]

    def get_functions(self):

        return self.functions

    def set_functions(self, functions_dict):

        self.functions = functions_dict

        return

    def start_next_task(self, func_id):
        """
        This method makes sure that the next task in the schedule is started
        when a task is finished, or when the first task should begin.

        :param func_id: the inst uuid of the function that is being handled.
        :param first: indicates whether this is the first task in a chain.
        """

        # If the kill field is active, the chain is killed
        if self.functions[func_id]['kill_chain']:
            LOG.info("Function " + func_id + ": Killing running workflow")
            # TODO: delete FSMs, records, stop
            # TODO: Or, jump into the kill workflow.
            del self.functions[func_id]
            return

        # Select the next task, only if task list is not empty
        if len(self.functions[func_id]['schedule']) > 0:

            # share state with other FLMs
            next_task = getattr(self,
                                self.functions[func_id]['schedule'].pop(0))

            # Push the next task to the threadingpool
            task = self.thrd_pool.submit(next_task, func_id)

            # Log if a task fails
            if task.exception() is not None:
                print(task.result())

            # When the task is done, the next task should be started if no flag
            # is set to pause the chain.
            if self.functions[func_id]['pause_chain']:
                self.functions[func_id]['pause_chain'] = False
            else:
                self.start_next_task(func_id)

        else:
            del self.functions[func_id]

####################
# FLM input - output
####################

    def flm_error(self, func_id, error=None):
        """
        This method is used to report back errors to the SLM
        """
        if error is None:
            error = self.functions[func_id]['error']
        LOG.info("Function " + func_id + ": error occured: " + error)
        LOG.info("Function " + func_id + ": informing SLM")

        message = {}
        message['status'] = "failed"
        message['error'] = error
        message['timestamp'] = time.time()

        corr_id = self.functions[func_id]['orig_corr_id']
        topic = self.functions[func_id]['topic']

        self.manoconn.notify(topic,
                             yaml.dump(message),
                             correlation_id=corr_id)

        # Kill the current workflow
        self.functions[func_id]['kill_chain'] = True

    def function_instance_create(self, ch, method, properties, payload):
        """
        This function handles a received message on the *.function.create
        topic.
        """

        # Don't trigger on self created messages
        if self.name == properties.app_id:
            return

        LOG.info("Function instance create request received.")
        message = yaml.load(payload)

        # Extract the correlation id
        corr_id = properties.correlation_id

        func_id = message['id']

        # Add the function to the ledger
        self.add_function_to_ledger(message, corr_id, func_id, t.VNF_DEPLOY)

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        # Onboard and instantiate the FSMs, if required.
        if self.functions[func_id]['fsm']:
            add_schedule.append('onboard_fsms')
            add_schedule.append('instant_fsms')

            if 'task' in self.functions[func_id]['fsm'].keys():
                add_schedule.append('trigger_task_fsm')

        add_schedule.append("deploy_vnf")
        add_schedule.append("store_vnfr")
        add_schedule.append("inform_slm_on_deployment")

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New instantiation request received. Instantiation started."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

    def function_instance_start(self, ch, method, properties, payload):
        """
        This method starts the vnf start workflow
        """

        # Don't trigger on self created messages
        if self.name == properties.app_id:
            return

        LOG.info("Function instance start request received.")
        message = yaml.load(payload)

        # Extract the correlation id
        corr_id = properties.correlation_id

        func_id = message['vnf_id']

        # recreate the ledger
        self.recreate_ledger(message, corr_id, func_id, t.VNF_START)

        # Check if VNFD defines a start FSM, if not, no action can be taken
        if 'start' not in self.functions[func_id]['fsm'].keys():
            msg = ": No start FSM provided, start event ignored."
            LOG.info("Function " + func_id + msg)

            self.functions[func_id]['message'] = msg
            self.respond_to_request(func_id)

            del self.functions[func_id]
            return

        # If a start FSM is present, continu with workflow
        # add the payload for the FSM
        self.functions[func_id]['start'] = message['data']

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        add_schedule.append("trigger_start_fsm")
        add_schedule.append("respond_to_request")

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New start request received."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

    def function_instance_config(self, ch, method, properties, payload):
        """
        This method starts the vnf config workflow
        """

        # Don't trigger on self created messages
        if self.name == properties.app_id:
            return

        LOG.info("Function instance config request received.")
        message = yaml.load(payload)

        # Extract the correlation id
        corr_id = properties.correlation_id

        func_id = message['vnf_id']

        # recreate the ledger
        self.recreate_ledger(message, corr_id, func_id, t.VNF_CONFIG)

        # Check if VNFD defines a start FSM, if not, no action can be taken
        if 'configure' not in self.functions[func_id]['fsm'].keys():
            msg = ": No config FSM provided, config event ignored."
            LOG.info("Function " + func_id + msg)

            self.functions[func_id]['message'] = msg
            self.respond_to_request(func_id)

            del self.functions[func_id]
            return

        # add the payload for the FSM
        self.functions[func_id]['configure'] = message['data']

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        add_schedule.append("trigger_configure_fsm")
        add_schedule.append("respond_to_request")

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New config request received."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

    def function_instance_stop(self, ch, method, properties, payload):
        """
        This method starts the vnf stop workflow
        """

        # Don't trigger on self created messages
        if self.name == properties.app_id:
            return

        LOG.info("Function instance stop request received.")
        message = yaml.load(payload)

        # Extract the correlation id
        corr_id = properties.correlation_id

        func_id = message['vnf_id']

        # recreate the ledger
        self.recreate_ledger(message, corr_id, func_id, t.VNF_STOP)

        # Check if VNFD defines a stop FSM, if not, no action can be taken
        if 'stop' not in self.functions[func_id]['fsm'].keys():
            msg = ": No stop FSM provided, start event ignored."
            LOG.info("Function " + func_id + msg)

            self.functions[func_id]['message'] = msg
            self.respond_to_request(func_id)

            del self.functions[func_id]
            return

        # add the payload for the FSM
        self.functions[func_id]['stop'] = message['data']

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        add_schedule.append("trigger_stop_fsm")
        add_schedule.append("respond_to_request")

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New stop request received."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

    def function_instance_scale(self, ch, method, properties, payload):
        """
        This method starts the vnf scale workflow
        """

        # Don't trigger on self created messages
        if self.name == properties.app_id:
            return

        LOG.info("Function instance scale request received.")
        message = yaml.load(payload)

        # Extract the correlation id
        corr_id = properties.correlation_id

        func_id = message['vnf_id']

        # recreate the ledger
        self.recreate_ledger(message, corr_id, func_id, t.VNF_SCALE)

        # Check if VNFD defines a stop FSM, if not, no action can be taken
        if 'scale' not in self.functions[func_id]['fsm'].keys():
            msg = ": No scale FSM provided, scale event ignored."
            LOG.info("Function " + func_id + msg)

            self.functions[func_id]['message'] = msg
            self.respond_to_request(func_id)

            del self.functions[func_id]
            return

        # add the payload for the FSM
        self.functions[func_id]['scale'] = message['data']

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        add_schedule.append("trigger_scale_fsm")
        # TODO: add interaction with Mistral when FSM responds (using the
        # content of the response)
        add_schedule.append("update_vnfr_after_scale")
        add_schedule.append("respond_to_request")

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New scale request received."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

    def function_instance_kill(self, ch, method, properties, payload):
        """
        This method starts the vnf kill workflow
        """

        # Don't trigger on self created messages
        if self.name == properties.app_id:
            return

        LOG.info("Function instance kill request received.")
        message = yaml.load(payload)

        # Extract the correlation id
        corr_id = properties.correlation_id

        func_id = message['id']

        # recreate the ledger
        self.recreate_ledger(message, corr_id, func_id, t.VNF_KILL)

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        # TODO: add the relevant methods for the kill workflow

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New kill request received."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

    def onboard_fsms(self, func_id):
        """
        This method instructs the fsm registry manager to onboard the
        required FSMs.

        :param func_id: The instance uuid of the function
        """

        corr_id = str(uuid.uuid4())
        # Sending the vnfd to the SRM triggers it to onboard the fsms
        msg = {'VNFD': self.functions[func_id]['vnfd']}
        pyld = yaml.dump(msg)
        self.manoconn.call_async(self.resp_onboard,
                                 t.SRM_ONBOARD,
                                 pyld,
                                 correlation_id=corr_id)

        # Add correlation id to the ledger for future reference
        self.functions[func_id]['act_corr_id'] = corr_id

        # Pause the chain of tasks to wait for response
        self.functions[func_id]['pause_chain'] = True

        LOG.info("Function " + func_id + ": FSM on-board trigger sent to SMR.")

    def resp_onboard(self, ch, method, prop, payload):
        """
        This method handles the response from the SMR on the fsm onboard call
        """

        func_id = tools.funcid_from_corrid(self.functions, prop.correlation_id)
        LOG.info("Function " + func_id + ": Onboard resp received from SMR.")

        message = yaml.load(payload)

        for key in message.keys():
            if message[key]['error'] == 'None':
                LOG.info("Function " + func_id + ": FSMs onboarding succesful")
            else:
                msg = ": FSM onboarding failed: " + message[key]['error']
                LOG.info("Function " + func_id + msg)
                self.fm_error(func_id,
                              t.GK_CREATE,
                              error=message[key]['error'])

        # Continue with the scheduled tasks
        self.start_next_task(func_id)

    def instant_fsms(self, func_id):
        """
        This method instructs the fsm registry manager to instantiate the
        required FSMs.

        :param func_id: The instance uuid of the function
        """

        corr_id = str(uuid.uuid4())
        # Sending the NSD to the SRM triggers it to instantiate the ssms

        msg_for_smr = {}
        msg_for_smr['VNFD'] = self.functions[func_id]['vnfd']
        msg_for_smr['UUID'] = func_id

        if self.functions[func_id]['private_key']:
            msg_for_smr['private_key'] = self.functions[func_id]['private_key']

        msg = ": Keys in message for FSM instant: " + str(msg_for_smr.keys())
        LOG.info("Function " + func_id + msg)
        pyld = yaml.dump(msg_for_smr)

        self.manoconn.call_async(self.resp_instant,
                                 t.SRM_INSTANT,
                                 pyld,
                                 correlation_id=corr_id)

        # Add correlation id to the ledger for future reference
        self.functions[func_id]['act_corr_id'] = corr_id

        # Pause the chain of tasks to wait for response
        self.functions[func_id]['pause_chain'] = True

        LOG.info("FSM instantiation trigger sent to SMR")

    def resp_instant(self, ch, method, prop, payload):
        """
        This method handles responses to a request to onboard the fsms
        of a new function.
        """

        # Retrieve the function uuid
        func_id = tools.funcid_from_corrid(self.functions, prop.correlation_id)
        msg = ": Instantiating response received from SMR."
        LOG.info("Function " + func_id + msg)
        LOG.debug(payload)

        message = yaml.load(payload)
        for fsm_type in self.functions[func_id]['fsm'].keys():
            fsm = self.functions[func_id]['fsm'][fsm_type]
            response = message[fsm['id']]
            fsm['instantiated'] = False
            if response['error'] == 'None':
                LOG.info("Function " + func_id + ": FSM instantiated correct.")
                fsm['instantiated'] = True
            else:
                msg = ": FSM instantiation failed: " + response['error']
                LOG.info("Function " + func_id + msg)
                self.flm_error(func_id, error=response['error'])

            fsm['uuid'] = response['uuid']

        # Setup broker connection with the SSMs of this service.
        url = self.fsm_url_base + 'fsm-' + func_id
        fsm_conn = messaging.ManoBrokerRequestResponseConnection(self.name,
                                                                 url=url)

        self.fsm_connections[func_id] = fsm_conn

        # Continue with the scheduled tasks
        self.start_next_task(func_id)

    def deploy_vnf(self, func_id):
        """
        This methods requests the deployment of a vnf
        """

        function = self.functions[func_id]

        outg_message = {}
        outg_message['vnfd'] = function['vnfd']
        outg_message['vnfd']['instance_uuid'] = function['id']
        outg_message['vim_uuid'] = function['vim_uuid']
        outg_message['service_instance_id'] = function['serv_id']
        if function['public_key']:
            outg_message['public_key'] = function['public_key']

        payload = yaml.dump(outg_message)

        corr_id = str(uuid.uuid4())
        self.functions[func_id]['act_corr_id'] = corr_id

        LOG.info("IA contacted for function deployment.")
        LOG.debug("Payload of request: " + payload)
        # Contact the IA
        self.manoconn.call_async(self.IA_deploy_response,
                                 t.IA_DEPLOY,
                                 payload,
                                 correlation_id=corr_id)

        # Pause the chain of tasks to wait for response
        self.functions[func_id]['pause_chain'] = True

    def IA_deploy_response(self, ch, method, prop, payload):
        """
        This method handles the response from the IA on the
        vnf deploy request.
        """

        LOG.info("Response from IA on vnf deploy call received.")
        LOG.debug("Payload of request: " + str(payload))

        inc_message = yaml.load(payload)

        func_id = tools.funcid_from_corrid(self.functions, prop.correlation_id)

        self.functions[func_id]['status'] = inc_message['request_status']

        if inc_message['request_status'] == "COMPLETED":
            LOG.info("Vnf deployed correctly")
            self.functions[func_id]["ia_vnfr"] = inc_message["vnfr"]
            self.functions[func_id]["error"] = None

        else:
            LOG.info("Deployment failed: " + inc_message["message"])
            self.functions[func_id]["error"] = inc_message["message"]
            topic = self.functions[func_id]['topic']
            self.flm_error(func_id, topic)
            return

        self.start_next_task(func_id)

    def store_vnfr(self, func_id):
        """
        This method stores the vnfr in the repository
        """

        function = self.functions[func_id]

        # Build the record
        vnfr = tools.build_vnfr(function['ia_vnfr'], function['vnfd'])
        self.functions[func_id]['vnfr'] = vnfr
        LOG.info(yaml.dump(vnfr))

        # Store the record
#            try:
        url = t.VNFR_REPOSITORY_URL + 'vnf-instances'
        header = {'Content-Type': 'application/json'}
        vnfr_response = requests.post(url,
                                      data=json.dumps(vnfr),
                                      headers=header,
                                      timeout=1.0)
        LOG.info("Storing VNFR on " + url)
        LOG.debug("VNFR: " + str(vnfr))

        if (vnfr_response.status_code == 200):
            LOG.info("VNFR storage accepted.")
        # If storage fails, add error code and message to rply to gk
        else:
            error = {'http_code': vnfr_response.status_code,
                     'message': vnfr_response.json()}
            self.functions[func_id]['error'] = error
            LOG.info('vnfr to repo failed: ' + str(error))
        # except:
        #     error = {'http_code': '0',
        #              'message': 'Timeout contacting VNFR server'}
        #     LOG.info('time-out on vnfr to repo')

        return

    def update_vnfr_after_scale(self, func_id):
        """
        This method updates the vnfr after a vnf scale event
        """

        # TODO: for now, this method only updates the version
        # number of the record. Once the mistral interaction
        # is added, other fields of the record might need upates
        # as well

        error = None
        vnfr = self.functions[func_id]['vnfr']
        vnfr_id = func_id

        # Updating version number
        old_version = int(vnfr['version'])
        cur_version = old_version + 1
        vnfr['version'] = str(cur_version)

        # Updating the record
        vnfr["id"] = vnfr_id
        del vnfr["uuid"]
        del vnfr["updated_at"]
        del vnfr["created_at"]

        # Put it
        url = t.VNFR_REPOSITORY_URL + 'vnf-instances/' + vnfr_id
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
            LOG.info("record update failed: " + str(error))
            self.functions[func_id]["error"] = error
            self.flm_error(func_id)

    def inform_slm_on_deployment(self, func_id):
        """
        In this method, the SLM is contacted to inform on the vnf
        deployment.
        """
        LOG.info("Informing the SLM of the status of the vnf deployment")

        function = self.functions[func_id]

        message = {}
        message["vnfr"] = function["vnfr"]
        message["status"] = function["status"]
        message["error"] = function["error"]

        corr_id = self.functions[func_id]['orig_corr_id']
        self.manoconn.notify(t.VNF_DEPLOY,
                             yaml.dump(message),
                             correlation_id=corr_id)

    def trigger_task_fsm(self, func_id):
        """
        This method triggers the task FSM.
        """
        LOG.info("Triggering task FSM.")

        # Generating the message for the FSM
        message = {}
        message['schedule'] = self.functions[func_id]['schedule']
        message['fsm_type'] = 'task'

        # Topic needs to be added, so the task FSM knows for which workflow
        # the schedule needs to be adapted.
        message['topic'] = topic

        # Generating the corr_id
        corr_id = str(uuid.uuid4())
        self.functions[func_id]['act_corr_id'] = corr_id

        fsm_conn = self.fsm_connections[func_id]

        # Making the call
        fsm_conn.call_async(self.fsm_task_response,
                            topic,
                            yaml.dump(payload),
                            correlation_id=corr_id)

        # Pause the chain
        self.functions[func_id]['pause_chain'] = True

    def fsm_task_response(self, ch, method, prop, payload):
        """
        This method handles a response from a task FSM.
        """
        response = yaml.load(response)

        func_id = tools.funcid_from_corrid(self.functions, prop.correlation_id)

        LOG.info("Response from task FSM received")

        if response['status'] == "COMPLETED":
            LOG.info("FSM finished successfully")
            self.functions[func_id]['schedule'] = response['schedule']

        else:
            LOG.info("task FSM failed: " + response['error'])
            self.functions[func_id]["error"] = response['error']
            self.flm_error(func_id)
            return

        self.start_next_task(func_id)

    def trigger_start_fsm(self, func_id):
        """
        This method is called to trigger the start FSM.
        """
        self.trigger_fsm(func_id, 'start')

    def trigger_stop_fsm(self, func_id):
        """
        This method is called to trigger the stop FSM.
        """
        self.trigger_fsm(func_id, 'stop')

    def trigger_scale_fsm(self, func_id):
        """
        This method is called to trigger the scale FSM.
        """
        self.trigger_fsm(func_id, 'scale')

    def trigger_configure_fsm(self, func_id):
        """
        This method is called to trigger the configure FSM.
        """
        self.trigger_fsm(func_id, 'configure')

    def trigger_fsm(self, func_id, fsm_type):
        """
        This is a generic method for triggering start/stop/configure FSMs.
        """
        LOG.info("Triggering " + fsm_type + " FSM.")

        # Generating the payload for the call
        payload = {}
        payload["content"] = self.functions[func_id][fsm_type]
        payload['fsm_type'] = fsm_type

        # Creating the topic
        topic = 'generic.fsm.' + func_id

        # Generating the corr_id
        corr_id = str(uuid.uuid4())
        self.functions[func_id]['act_corr_id'] = corr_id
        self.functions[func_id]['active_fsm'] = fsm_type

        fsm_conn = self.fsm_connections[func_id]

        # Making the call
        fsm_conn.call_async(self.fsm_generic_response,
                            topic,
                            yaml.dump(payload),
                            correlation_id=corr_id)

        # Pause the chain
        self.functions[func_id]['pause_chain'] = True

    def fsm_generic_response(self, ch, method, prop, payload):
        """
        This method handles a response to a generic FSM trigger call
        """
        response = yaml.load(payload)

        func_id = tools.funcid_from_corrid(self.functions, prop.correlation_id)
        fsm_type = self.functions[func_id]['active_fsm']

        LOG.info("Response from " + fsm_type + " FSM received")

        if response['status'] == "COMPLETED":
            LOG.info("FSM finished successfully")

        else:
            LOG.info(fsm_type + " FSM failed: " + response['error'])
            self.functions[func_id]["error"] = response['error']
            self.flm_error(func_id)
            return

        self.start_next_task(func_id)

    def respond_to_request(self, func_id):
        """
        This method creates a response message for the sender of requests.
        """

        message = {}
        message["timestamp"] = time.time()
        message["error"] = self.functions[func_id]['error']
        message["vnf_id"] = func_id

        if self.functions[func_id]['error'] is None:
            message["status"] = "COMPLETED"
        else:
            message["status"] = "FAILED"

        if self.functions[func_id]['message'] is not None:
            message["message"] = self.functions[func_id]['message']

        LOG.info("Generating response to the workflow request")

        corr_id = self.functions[func_id]['orig_corr_id']
        topic = self.functions[func_id]['topic']
        self.manoconn.notify(topic,
                             yaml.dump(message),
                             correlation_id=corr_id)

###########
# FLM tasks
###########

    def add_function_to_ledger(self, payload, corr_id, func_id, topic):
        """
        This method adds new functions with their specifics to the ledger,
        so other functions can use this information.

        :param payload: the payload of the received message
        :param corr_id: the correlation id of the received message
        :param func_id: the instance uuid of the function defined by SLM.
        """

        # Add the function to the ledger and add instance ids
        self.functions[func_id] = {}
        self.functions[func_id]['vnfd'] = payload['vnfd']
        self.functions[func_id]['id'] = func_id

        # Add the topic of the call
        self.functions[func_id]['topic'] = topic

        # Add to correlation id to the ledger
        self.functions[func_id]['orig_corr_id'] = corr_id

        # Add payload to the ledger
        self.functions[func_id]['payload'] = payload

        # Add the service uuid that this function belongs to
        self.functions[func_id]['serv_id'] = payload['serv_id']

        # Add the VIM uuid
        self.functions[func_id]['vim_uuid'] = payload['vim_uuid']

        # Create the function schedule
        self.functions[func_id]['schedule'] = []

        # Create the FSM dict if FSMs are defined in VNFD
        fsm_dict = tools.get_fsm_from_vnfd(payload['vnfd'])
        self.functions[func_id]['fsm'] = fsm_dict

        print(self.functions[func_id]['fsm'])

        # Create the chain pause and kill flag

        self.functions[func_id]['pause_chain'] = False
        self.functions[func_id]['kill_chain'] = False

        # Create payload fields for FSMs
        self.functions[func_id]['start'] = None
        self.functions[func_id]['stop'] = None
        self.functions[func_id]['configure'] = None

        self.functions[func_id]['act_corr_id'] = None
        self.functions[func_id]['message'] = None

        # Add error field
        self.functions[func_id]['error'] = None

        # Add keys
        self.functions[func_id]['public_key'] = payload['public_key']
        self.functions[func_id]['private_key'] = payload['private_key']

        return func_id

    def recreate_ledger(self, payload, corr_id, func_id, topic):
        """
        This method adds already existing functions with their specifics
        back to the ledger, so other methods can use this information.

        :param payload: the payload of the received message
        :param corr_id: the correlation id of the received message
        :param func_id: the instance uuid of the function defined by SLM.
        """

        # Add the function to the ledger and add instance ids
        self.functions[func_id] = {}

        # TODO: add the real vnfr here
        vnfr = {}
        self.functions[func_id]['vnfr'] = vnfr

        if 'vnfd' in payload.keys():
            vnfd = payload['vnfd']
        else:
            # TODO: retrieve VNFD from CAT based on func_id
            vnfd = {}
        self.functions[func_id]['vnfd'] = vnfd

        self.functions[func_id]['id'] = func_id

        # Add the topic of the call
        self.functions[func_id]['topic'] = topic

        # Add to correlation id to the ledger
        self.functions[func_id]['orig_corr_id'] = corr_id

        # Add payload to the ledger
        self.functions[func_id]['payload'] = payload

        # Add the service uuid that this function belongs to
        self.functions[func_id]['serv_id'] = payload['serv_id']

        # Add the VIM uuid
        self.functions[func_id]['vim_uuid'] = ''

        # Create the function schedule
        self.functions[func_id]['schedule'] = []

        # Create the FSM dict if FSMs are defined in VNFD
        fsm_dict = tools.get_fsm_from_vnfd(vnfd)
        self.functions[func_id]['fsm'] = fsm_dict

        # Create the chain pause and kill flag

        self.functions[func_id]['pause_chain'] = False
        self.functions[func_id]['kill_chain'] = False

        # Create payload fields for FSMs
        self.functions[func_id]['start'] = None
        self.functions[func_id]['stop'] = None
        self.functions[func_id]['configure'] = None
        self.functions[func_id]['act_corr_id'] = None
        self.functions[func_id]['message'] = None

        # Add error field
        self.functions[func_id]['error'] = None

        return func_id


def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
#    logging.getLogger("amqp-storm").setLevel(logging.DEBUG)
    # create our function lifecycle manager
    flm = FunctionLifecycleManager()

if __name__ == '__main__':
    main()
