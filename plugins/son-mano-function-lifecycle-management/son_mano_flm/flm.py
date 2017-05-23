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
This is SONATA's Function lifecycle management plugin
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
        self.manoconn.subscribe(self.function_instance_create, t.MANO_DEPLOY)

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
        LOG.info("FLM started and operational")

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

        # Extract the correlation id and generate a reduced id
        corr_id = properties.correlation_id

        func_id = message['id']

        # Add the function to the ledger
        self.add_function_to_ledger(message, corr_id, func_id)

        # Schedule the tasks that the FLM should do for this request.
        add_schedule = []

        # Onboard and instantiate the FSMs, if required.
        if self.functions[func_id]['fsm'] is not None:
            add_schedule.append('onboard_fsms')
            add_schedule.append('instant_fsms')

        add_schedule.append("deploy_vnf")
        add_schedule.append("store_vnfr")
        add_schedule.append("inform_slm_on_deployment")

        self.functions[func_id]['schedule'].extend(add_schedule)

        msg = ": New instantiation request received. Instantiation started."
        LOG.info("Function " + func_id + msg)
        # Start the chain of tasks
        self.start_next_task(func_id)

        return self.functions[func_id]['schedule']

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
            # TODO: error-handling
            LOG.info("Deployment failed: " + inc_message["message"])
            self.functions[func_id]["error"] = inc_message["message"]

        self.start_next_task(func_id)

    def store_vnfr(self, func_id):
        """
        This method stores the vnfr in the repository
        """

        function = self.functions[func_id]

        # Build the record
        vnfr = tools.build_vnfr(function['ia_vnfr'], function['vnfd'])
        self.functions[func_id]['vnfr'] = vnfr

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
        self.manoconn.notify(t.MANO_DEPLOY,
                             yaml.dump(message),
                             correlation_id=corr_id)

###########
# FLM tasks
###########

    def add_function_to_ledger(self, payload, corr_id, func_id):
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
