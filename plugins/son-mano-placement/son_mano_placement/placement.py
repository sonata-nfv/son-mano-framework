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
import pulp
import threading
import sys
import concurrent.futures as pool
# import psutil

from sonmanobase.plugin import ManoBasePlugin

try:
    from son_mano_placement import placement_helpers as tools
except:
    import placement_helpers as tools

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:placement")
LOG.setLevel(logging.INFO)


class PlacementPlugin(ManoBasePlugin):
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

        # call super class (will automatically connect to
        # broker and register the Placement plugin to the plugin manger)
        ver = "0.1-dev"
        des = "This is the Placement plugin"

        super(self.__class__, self).__init__(version=ver,
                                             description=des,
                                             auto_register=auto_register,
                                             wait_for_registration=wait_for_registration,
                                             start_running=start_running)

    def __del__(self):
        """
        Destroy Placement plugin instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics that Placement Plugin subscribes on.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()

        # The topic on which deploy requests are posted.
        topic = 'mano.service.place'
        self.manoconn.subscribe(self.placement_request, topic)

        LOG.info("Subscribed to topic: " + str(topic))

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
        LOG.info("Placement plugin started and operational.")

    def deregister(self):
        """
        Send a deregister request to the plugin manager.
        """
        LOG.info('Deregistering Placement plugin with uuid ' + str(self.uuid))
        message = {"uuid": self.uuid}
        self.manoconn.notify("platform.management.plugin.deregister",
                             json.dumps(message))
        os._exit(0)

    def on_registration_ok(self):
        """
        This method is called when the Placement plugin
        is registered to the plugin mananger
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")

##########################
# Placement
##########################

    def placement_request(self, ch, method, prop, payload):
        """
        This method handles a placement request
        """

        if prop.app_id == self.name:
            return

        content = yaml.load(payload)
        LOG.info("Placement request for service: " + content['serv_id'])

        serv_id = content['serv_id']
        top = content['topology']
        nsd = content['nsd']
        vnfs = content['functions']
        op_pol = content['operator_policies']
        cu_pol = content['customer_policies']
        ingress = content['nap']['ingresses']
        egress = content['nap']['egresses']

        #Check if topology is not empty
        if len(top) == 0:
            response = {}
            response['mapping'] = None
            response['error'] = 'Empty topology list'
        else:            
            vnf_single_pop = False
            if "vnf_single_pop" in content.keys():
                vnf_single_pop = content["vnf_single_pop"]

            # Convert memory information on topology to GB, from MB.
            for pop in top:
                pop['memory_used'] = pop['memory_used'] / 1024.0
                pop['memory_total'] = pop['memory_total'] / 1024.0

            # Extract weights
            operator_weight = 1.0
            developer_weight = 0.0
            if 'weights' in op_pol.keys():
                operator_weight = op_pol['weights']['operator']
                developer_weight = op_pol['weights']['developer']

            # # Solve first for only operator or developer influence, to calibrate
            # operator_optimal_value = self.placement(serv_id, nsd, vnfs, top, op_pol, cu_pol, ingress, egress, operator_weight=1.0, developer_weight=0.0, vnf_single_pop=vnf_single_pop)[2]
            # developer_optimal_value = self.placement(serv_id, nsd, vnfs, top, op_pol, cu_pol, ingress, egress, operator_weight=0.0, developer_weight=1.0, vnf_single_pop=vnf_single_pop)[2]

            # operator_weight = abs(operator_weight / operator_optimal_value)
            # developer_weight = abs(developer_weight / developer_optimal_value)

            placement = self.placement(serv_id, nsd, vnfs, top, op_pol, cu_pol, ingress, egress, operator_weight=operator_weight, developer_weight=developer_weight, vnf_single_pop=vnf_single_pop)
            LOG.info("Placement calculated:" + str(placement))

            response = {}
            response['mapping'] = {}
            response['error'] = placement[1]
            if placement[1] is None:
                for vnf_id in placement[0]:
                    response['mapping'][vnf_id] = {'vim':placement[0][vnf_id]}

        LOG.info(str(response))
        topic = 'mano.service.place'

        self.manoconn.notify(topic,
                             yaml.dump(response),
                             correlation_id=prop.correlation_id)

        LOG.info("Placement response sent for service: " + content['serv_id'])

    def placement(self, serv_id, nsd, vnfs, top, op_policy, cu_policy, ingress, egress, operator_weight=1.0, developer_weight=0.0, customer_weight=0.0, vnf_single_pop=False):
        """
        This is the default placement algorithm that is used if the SLM
        is responsible to perform the placement
        """
        LOG.info(str(serv_id) + ": Embedding started for service")
        LOG.info(str(serv_id) + ": Topology: " + str(top))
        LOG.info(str(serv_id) + ": Customer Policies: " + str(cu_policy))
        LOG.info(str(serv_id) + ": Operator Policies: " + str(op_policy))
        if vnf_single_pop:
            LOG.info(str(serv_id) + ": VNF single PoP activated.")

        if not isinstance(op_policy, dict):
            LOG.info(str(serv_id) + ": operator_policies is not a dict")
            return "Operator policies are not a dictionary", "ERROR"
        if not isinstance(cu_policy, dict):
            LOG.info(str(serv_id) + ": customer_policies is not a dict")
            return "Customer policies are not a dictionary", "ERROR"

        # Make a list of the images (VNF can have multiple VDU) that require
        # mapping.
        images_to_map = tools.get_image_list(vnfs)
        LOG.info(str(serv_id) + ": List of images: " + str(images_to_map))

        # Create list of decision variables. Per image to map, we have n
        #  decisionvariables if n is the number of PoPs that can be mapped on.
        LOG.info(str(serv_id) + ": Creating decision variables")
        range_images = range(len(images_to_map))
        range_top = range(len(top))
        decision_vars = [(x, y) for x in range_images for y in range_top]

        # The decision variables are 1 if VNF x is mapped on PoP y, 0 if not.
        # Decision variables are thus binary.
        LOG.info(str(serv_id) + ": Creating ILP problem")
        variables = pulp.LpVariable.dicts('variables',
                                          decision_vars,
                                          lowBound=0,
                                          upBound=1,
                                          cat=pulp.LpInteger)

        # We solve the problem as a minimization problem.
        lpProblem = pulp.LpProblem("Placement", pulp.LpMinimize)

        # Create objective based on customer policies
        # TODO: At this point, we don't have soft customer objectives
        customer_objective = 0

        # Create objective based on developer policies
        source_ip = None
        dest_ip = None
        if ingress:
            source_ip = ingress[0]['nap']
        if egress:
            dest_ip = egress[0]['nap']
        developr_objective = tools.calculate_developer_objective(nsd,
                                                                 vnfs,
                                                                 source_ip,
                                                                 dest_ip,
                                                                 images_to_map,
                                                                 top,
                                                                 variables,
                                                                 decision_vars,
                                                                 LOG,
                                                                 serv_id)

        # Create objective based on operator policies
        operator_objective = tools.calculate_operator_objective(variables,
                                                                images_to_map,
                                                                top,
                                                                decision_vars,
                                                                op_policy,
                                                                LOG,
                                                                serv_id,
                                                                )

        lpProblem += operator_weight * operator_objective[0] + developer_weight * developr_objective[0] + customer_objective * customer_weight

        # Add additional constraints created by developer policy model
        # translation
        for constraint in developr_objective[1]:
            lpProblem += constraint

        # Add additional constraints created by operator policy model
        # translation
        for constraint in operator_objective[1]:
            lpProblem += constraint

        # Set hard constraints
        # PoP resources can not be violated
        for vim in range(len(top)):
            lpProblem += top[vim]['core_used'] + sum(images_to_map[x[0]]['cpu'] * variables[x] for x in decision_vars if x[1] == vim) <= top[vim]['core_total']
            lpProblem += top[vim]['memory_used'] + sum(images_to_map[x[0]]['ram'] * variables[x] for x in decision_vars if x[1] == vim) <= top[vim]['memory_total']

        # Every VNF should be assigned to one PoP
        for vnf in range(len(images_to_map)):
            lpProblem += sum(variables[x] for x in decision_vars if x[0] == vnf) == 1

        # Add blacklist from customers. If PoP is on blacklist, no VNFs can be on it.
        if 'blacklist' in cu_policy.keys():
            blacklist = cu_policy['blacklist']
            LOG.info(str(serv_id) + ": Customer blacklist: " + str(blacklist))
        else:
            LOG.info(str(serv_id) + ": No customer blacklist provided.")
            blacklist = []

        for index in range(len(top)):
            if top[index]['vim_name'] in blacklist:
                lpProblem+= sum(variables[x] for x in decision_vars if x[1] == index) == 0

        # set constraints for single PoP VNFs
        if vnf_single_pop:
            for vdu_index_1 in range(len(images_to_map)):
                for vdu_index_2 in range(len(images_to_map)):
                    if vdu_index_1 < vdu_index_2:
                        if images_to_map[vdu_index_1]['function_id'] == images_to_map[vdu_index_2]['function_id']:
                            for pop_index in range(len(top)):
                                lpProblem += variables[(vdu_index_1, pop_index)] == variables[(vdu_index_2, pop_index)]

        # Solve the problem
        lpProblem.solve()

        # Check the feasibility of the result
        LOG.info(str(serv_id) + ": Result: " + str(pulp.LpStatus[lpProblem.status]))
        if str(pulp.LpStatus[lpProblem.status]) != "Optimal":
            LOG.info(str(serv_id) + ": Placement was not possible")
            return {}, "Placement was not possible. Result: " + str(pulp.LpStatus[lpProblem.status]), 1.0

        # Interprete the results and build the repsonse
        mapping = {}
        for combo in decision_vars:
            if (variables[combo].value()) == 1:
                LOG.info('VNF' + str(images_to_map[combo[0]]['id']) + ' is mapped on PoP' + str(top[combo[1]]['vim_uuid']))

                if vnf_single_pop:
                    if images_to_map[combo[0]]['function_id'] not in mapping.keys():
                        function_id = images_to_map[combo[0]]['function_id']
                        mapping[function_id] = top[combo[1]]['vim_uuid']
                else:
                    mapping[images_to_map[combo[0]]['id']] = top[combo[1]]['vim_uuid']

        LOG.info(str(serv_id) + ": Resulting message: " + str(mapping))

        LOG.info(lpProblem.objective)
        LOG.info(lpProblem.objective.value())
        if lpProblem.objective.value() is not None:
            optimal_value = lpProblem.objective.value()
        else:
            optimal_value = 1.0
        return mapping, None, optimal_value


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
    placement = PlacementPlugin()

if __name__ == '__main__':
    main()
