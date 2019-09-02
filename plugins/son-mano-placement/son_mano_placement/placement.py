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
from sonmanobase.logger import TangoLogger

try:
    from son_mano_placement import placement_helpers as tools
except:
    import placement_helpers as tools

# Logger
json_logger = False
if os.environ.get("json_logger"):
    json_logger = True

LOG = TangoLogger.getLogger(__name__, log_level=logging.INFO, log_json=json_logger)
TangoLogger.getLogger("son-mano-base:messaging", logging.INFO, log_json=json_logger)
TangoLogger.getLogger("son-mano-base:plugin", logging.INFO, log_json=json_logger)

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
        This will automatically connect to the broker.

        After the connection is done, the 'on_lifecycle_start' method is called.
        :return:
        """

        # call super class (will automatically connect to
        # broker and register the Placement plugin to the plugin manger)
        ver = "0.1-dev"
        des = "This is the Placement plugin"

        super(self.__class__, self).__init__(version=ver,
                                             description=des,
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
        input_vims = content['topology']['vims']['vim_list']
        input_wims = content['topology']['wims']
        nsd = content['nsd']
        vnfs = content['functions']
        op_pol = content['operator_policies']
        cu_pol = content['customer_policies']
        ingress = content['nap']['ingresses']
        egress = content['nap']['egresses']
        pre_map = content['predefined_mapping']

        # Translating payload into inputs for or placement process

        # Build list of vnfds
        vnfds = []
        for vnf in vnfs:
            vnfds.append(vnf['vnfd'])

        # Build list of deployment units
        dus = []
        for vnf in vnfs:
            desc = vnf['vnfd']
            if 'cloudnative_deployment_units' in desc.keys():
                cdus = desc['cloudnative_deployment_units']
                for cdu in cdus:
                    new_du = {}
                    new_du['type'] = 'container'
                    new_du['cpu'] = 0
                    new_du['ram'] = 0
                    new_du['id'] = cdu['id']
                    new_du['nf_id'] = vnf['id']
                    vim = pre_map['function'][vnf['id']]['vim_id']
                    if vim is not None:
                        new_du['placement_needed'] = False
                        new_du['vim'] = vim
                    dus.append(new_du)
            if 'virtual_deployment_units' in desc.keys():
                vdus = desc['virtual_deployment_units']
                for vdu in vdus:
                    new_du = {}
                    new_du['type'] = 'vm'
                    req = vdu['resource_requirements']
                    new_du['cpu'] = req['cpu']['vcpus']
                    new_du['ram'] = req['memory']['size']
                    if req['memory']['size_unit'] == 'MB':
                        new_du['ram'] = new_du['ram'] / 1024.0
                    new_du['id'] = vdu['id']
                    new_du['nf_id'] = vnf['id']
                    vim = pre_map['function'][vnf['id']]['vim_id']
                    if vim is not None:
                        if not pre_map['function'][vnf['id']]['new']:
                            new_du['cpu'] = 0
                            new_du['ram'] = 0
                        new_du['placement_needed'] = False
                        new_du['vim'] = vim
                    dus.append(new_du)

        LOG.info(serv_id + ': list of dus ' + str(dus))
        # print(yaml.dump(dus))

        # Build vim list
        vims = []
        vim_ids = []
        for vim in input_vims:
            new_vim = {}
            new_vim['core_used'] = vim['core_used']
            new_vim['core_total'] = vim['core_total']
            new_vim['memory_used'] = vim['memory_used'] / 1024.0
            new_vim['memory_total'] = vim['memory_total'] / 1024.0
            new_vim['id'] = vim['vim_uuid']
            new_vim['type'] = vim['type']
            new_vim['latency'] = 0
            new_vim['bandwidth'] = 1000
            vims.append(new_vim)
            vim_ids.append(vim['vim_uuid'])

        LOG.info(serv_id + ': list of vims ' + str(vims))
        # print(yaml.dump(vims))

        # Build wim list
        wims = []
        for wim in input_wims:
            if 'qos' in wim.keys():
                for pair in wim['qos']:
                    new_wim = {}
                    new_wim['vim_1'] = pair['node_1']
                    new_wim['vim_2'] = pair['node_2']
                    new_wim['id'] = wim['uuid']
                    new_wim['bandwidth'] = int(pair['bandwidth'])
                    new_wim['latency'] = int(pair['latency'])

                    if pair['node_1'] in vim_ids or pair['node_2'] in vim_ids:
                        wims.append(new_wim)

        LOG.info(serv_id + ': list of wims ' + str(wims))
        # print(yaml.dump(wims))

        # build endpoint list
        eps = []
        if ingress is not None:
            for ep in ingress:
                if 'location' in ep.keys():
                    new_ep = {}
                    new_ep['type'] = 'ingress'
                    new_ep['id'] = ep['location']
                    new_ep['pos'] = ingress.index(ep)
                    new_ep['wims'] = []
                    for wim in wims:
                        if new_ep['id'] in [wim['vim_1'], wim['vim_2']]:
                            new_ep['wims'].append(wim['id'])
                    new_ep['wims'] = list(set(new_ep['wims']))
                    eps.append(new_ep)
        if egress is not None:
            for ep in egress:
                if 'location' in ep.keys():
                    new_ep = {}
                    new_ep['type'] = 'egress'
                    new_ep['id'] = ep['location']
                    new_ep['pos'] = egress.index(ep)
                    new_ep['wims'] = []
                    for wim in wims:
                        if new_ep['id'] in [wim['vim_1'], wim['vim_2']]:
                            new_ep['wims'].append(wim['id'])
                    eps.append(new_ep)

        LOG.info(serv_id + ': list of eps ' + str(eps))
        # print(yaml.dump(eps))

        # build virtual link list that require qos considerations
        vls = []
        nsd_vls = nsd['virtual_links']

        # add vls coming from the nsd
        for nsd_vl in nsd_vls:
            vl_id = nsd_vl['id']
            refs = nsd_vl['connection_points_reference']
            LOG.info("special refs:" + str(refs))
            vl_inout = None

            all_nodes = []
            for ref in refs:
                node_id, ref_res, in_out = tools.map_ref_on_id(ref, nsd, vnfds, eps)
                LOG.info("node_id: " + str(node_id) + ' for ref: ' + str(ref))
                all_nodes.extend([{'ref': ref_res[x], 'node': node_id[x]} for x in range(len(node_id))])
                if in_out:
                    vl_inout = in_out
            len_nodes = len(all_nodes)

            vim_wim_id = None
            qos_req = None
            placement_needed = True

            # Handle fixed VIM based networks and predefined WIM networks
            if vl_id in pre_map['service']['vl'].keys():
                if 'vim_id' in pre_map['service']['vl'][vl_id].keys() \
                   and 'fixed' in pre_map['service']['vl'][vl_id].keys():
                    vim_wim_id = pre_map['service']['vl'][vl_id]['vim_id']
                    placement_needed = False

                    if len_nodes == 1:
                        all_nodes.append(all_nodes[0])
                        len_nodes = len(all_nodes)

                elif 'wim_id' in pre_map['service']['vl'][vl_id].keys():
                    vim_wim_id = pre_map['service']['vl'][vl_id]['wim_id']
                    placement_needed = False

            elif 'qos_requirements' in nsd_vl.keys():
                qos_req = nsd_vl['qos_requirements']

            if vim_wim_id or qos_req:
                for i in range(len_nodes):
                    for j in range(len_nodes):
                        if i < j:
                            new_vl = {}
                            identifier = '_' + str(i)  + '_' + str(j)
                            new_vl['id'] = nsd_vl['id'] + identifier
                            new_vl['refs'] = [all_nodes[i]['ref'], all_nodes[j]['ref']]
                            new_vl['nodes'] = []
                            new_vl['nodes'].append(all_nodes[i]['node'])
                            new_vl['nodes'].append(all_nodes[j]['node'])
                            new_vl['bandwidth'] = 0
                            new_vl['latency'] = 1000
                            if vim_wim_id:
                                new_vl['vim_wim'] = vim_wim_id
                            if qos_req:
                                if 'minimum_bandwidth' in qos_req.keys():
                                    new_vl['bandwidth'] = int(qos_req['minimum_bandwidth']['bandwidth'])
                                if 'latency' in qos_req.keys():
                                    new_vl['latency'] = int(qos_req['latency'])
                            if not placement_needed:
                                new_vl['placement_needed'] = False
                            if vl_inout:
                                if vl_inout == 'ingress':
                                    new_vl['ingress'] = True
                                if vl_inout == 'egress':
                                    new_vl['egress'] = True

                            vls.append(new_vl)

        # add vls coming from vnfds, between deployment units
        for vnf in vnfs:
            for vl in vnf['vnfd']['virtual_links']:
                if 'qos_requirements' in vl.keys():
                    new_vl = {}
                    new_vl['id'] = vnf['id'] + ':' + vl['id']
                    qos_req = vl['qos_requirements']
                    if 'minimum_bandwidth' in qos_req.keys():
                        new_vl['bandwidth'] = int(qos_req['minimum_bandwidth'])
                    else:
                        new_vl['bandwidth'] = 0
                    if 'latency' in qos_req.keys():
                        new_vl['latency'] = int(qos_req['latency'])
                    else:
                        new_vl['latency'] = 1000
                    new_vl['nodes'] = []
                    for ref in vl['connection_points_reference']:
                        if 'cloudnative_deployment_units' in vnfd.keys():
                            for cdu in vnfd['cloudnative_deployment_units']:
                                if cdu['id'].startswith(ref.split(':')[0]):
                                    new_vl['nodes'].append(cdu['id'])
                                    break
                        if 'virtual_deployment_units' in vnfd.keys():
                            for vdu in vnfd['virtual_deployment_units']:
                                if vdu['id'].startswith(ref.split(':')[0]):
                                    new_vl['nodes'].append(vdu['id'])
                                    break
                    if vl['id'] in pre_map['function'][vnf['id']]['vl'].keys():
                        pre_vl = pre_map['function'][vnf['id']]['vl']
                        new_vl['placement_needed'] = False
                        if 'vim_id' in pre_vl.keys():
                            new_vl['vim_wim'] = pre_vl['vim_id']
                        if 'wim_id' in pre_vl.keys():
                            new_vl['vim_wim'] = pre_vl['wim_id']
                    vls.append(new_vl)

        LOG.info(serv_id + ': list of vls ' + yaml.dump(vls))
#        print(yaml.dump(vls))

        # build constraint dictionary
        const = {}
        const['op_constraint'] = op_pol
        const['cu_constraint'] = cu_pol
        const['dev_constraint'] = {}

        LOG.info(serv_id + ': list of constraints ' + str(const))

        # force dus of same vnf/cnf on same pop or not
        sng = False
        if "vnf_single_pop" in content.keys():
            sng = content["vnf_single_pop"]

        # Extract weights
        op_weight = 1.0
        dev_weight = 0.0
        cu_weight = 0.0
        if 'weights' in op_pol.keys():
            op_weight = op_pol['weights']['operator']
            dev_weight = op_pol['weights']['developer']
        wghts = [op_weight, dev_weight, cu_weight]

        LOG.info(serv_id + ': list of weights ' + str(wghts))

        # Calculate the placement
        res = self.placement(dus, vls, vims, wims, eps, const, wghts, sng=sng)
        LOG.info(serv_id + ": Placement result:" + str(res))

        # Build the response message
        # Since this is used for the sonata MANO, where dus of the same VNF or
        # CNF are deployed on the same VIM, the response can be on the vnf
        # level
        response = {}
        response['mapping'] = {}
        response['error'] = res[1]
        if res[1] is None:
            dus_map = {}
            for vnf in vnfs:
                for du in dus:
                    if du['nf_id'] == vnf['id']:
                        vim_id = res[0]['dus'][du['id']]
                        dus_map[vnf['id']] = vim_id
                        break
            response['mapping']['du'] = dus_map

            vls_map = {}
            for vl in vls:
                vim_wim_id = res[0]['vls'][vl['id']]
                for vim in vims:
                    if vim['id'] == vim_wim_id:
                        orig_id = vl['id'].split('_')[0]
                        if orig_id not in vls_map.keys():                            
                            vls_map[orig_id] = []
                        new_vl = {}
                        new_vl['vim_id'] = [vim_wim_id]
                        ref_i = vl['refs'][0]
                        if ':' in vl['refs'][0]:
                            ref_i = vl['refs'][0] + '_' + vl['nodes'][0]
                        ref_j = vl['refs'][1]
                        if ':' in vl['refs'][1]:
                            ref_j = vl['refs'][1] + '_' + vl['nodes'][1]
                        new_vl['refs'] = [ref_i, ref_j]
                        if 'ingress' in vl.keys():
                            new_vl['ingress'] = vl['ingress']
                        if 'egress' in vl.keys():
                            new_vl['egress'] = vl['egress']
                        vls_map[orig_id].append(new_vl)
                        break
                for wim in wims:
                    if wim['id'] == vim_wim_id:
                        orig_id = vl['id'].split('_')[0]
                        if orig_id not in vls_map.keys():                            
                            vls_map[orig_id] = []
                        new_vl = {}
                        new_vl['wim_id'] = vim_wim_id
                        ref_i = vl['refs'][0]
                        if ':' in vl['refs'][0]:
                            ref_i = vl['refs'][0] + '_' + vl['nodes'][0]
                        ref_j = vl['refs'][1]
                        if ':' in vl['refs'][1]:
                            ref_j = vl['refs'][1] + '_' + vl['nodes'][1]
                        new_vl['refs'] = [ref_i, ref_j]
                        new_vl['nodes'] = []
                        if 'ingress' in vl.keys():
                            new_vl['ingress'] = vl['ingress']
                        if 'egress' in vl.keys():
                            new_vl['egress'] = vl['egress']
                        for node in vl['nodes']:
                            for ep in eps:
                                if ep['id'] == node:
                                    new_vl['nodes'].append(node)
                                    break
                            for du in dus:
                                if du['id'] == node:
                                    vim = response['mapping']['du'][du['nf_id']]
                                    new_vl['nodes'].append(vim)
                        vls_map[orig_id].append(new_vl)
                        break

            # If VIMs and WIMs are shared within a VL, convert VIMs to WIMs
            for vl_id in vls_map.keys():
                vl = vls_map[vl_id]
                vim_used = False
                wim_used = False
                wim_id = None
                for vl_pair in vl:
                    if 'vim_id' in vl_pair.keys():
                        vim_used = True
                    if 'wim_id' in vl_pair.keys():
                        wim_used = True
                        wim_id = vl_pair['wim_id']
                if vim_used and wim_used:
                    for vl_pair in vl:
                        if 'vim_id' in vl_pair.keys():
                            vl_pair['wim_id'] = wim_id
                            vl_pair['nodes'] = [copy.deepcopy(vl_pair['vim_id'][0]), copy.deepcopy(vl_pair['vim_id'][0])]
                            del vl_pair['vim_id']

            LOG.info("vls_map initial: " + yaml.dump(vls_map))

            # Add virtual links that have no qos requirements but coincide with
            # VIMs or WIMs to the list
            for vl in nsd_vls:
                if vl['id'] not in vls_map.keys():
                    vim_or_ep = []
                    only_vim = []
                    refs = vl['connection_points_reference']
                    vl_inout = None
                    all_nodes = []
                    for ref in refs:
                        node_id, ref_res, in_out = tools.map_ref_on_id(ref, nsd, vnfds, eps)
                        all_nodes.extend([{'ref': ref_res[x], 'node': node_id[x]} for x in range(len(node_id))])
                        if in_out:
                            vl_inout = in_out
                        for node in node_id:
                            if ':' in ref:
                                vim_id = res[0]['dus'][node]
                                vim_or_ep.append(vim_id)
                                only_vim.append(vim_id)
                            else:
                                vim_or_ep.append(node)
                    for wim in wims:
                        wim_id = wim['id']
                        coll = []
                        for wim in wims:
                            if wim['id'] == wim_id:
                                coll.append(wim['vim_1'])
                                coll.append(wim['vim_2'])
                        if set(vim_or_ep) <= set(coll) and \
                           len(set(vim_or_ep)) > 1:
                            vls_map[vl['id']] = []
                            for i in range(len(all_nodes)):
                                for j in range(len(all_nodes)):
                                    if i < j:
                                        new_vl = {}
                                        new_vl['wim_id'] = wim['id']
                                        nodes = [vim_or_ep[i], vim_or_ep[j]]
                                        new_vl['nodes'] = nodes
                                        ref_i = all_nodes[i]['ref']
                                        if ':' in ref_i:
                                            ref_i = ref_i + '_' + all_nodes[i]['node']
                                        ref_j = all_nodes[j]['ref']
                                        if ':' in ref_j:
                                            ref_j = ref_j + '_' + all_nodes[j]['node']
                                        new_vl['refs'] = [ref_i, ref_j]
                                        if vl_inout:
                                            if vl_inout == 'ingress':
                                                new_vl['ingress'] = True
                                            if vl_inout == 'egress':
                                                new_vl['egress'] = True
                                        vls_map[vl['id']].append(new_vl)
                            break
                    if vl['id'] not in vls_map.keys():
                        vls_map[vl['id']] = []
                        new_vl = {}
                        new_vl['vim_id'] = list(set(only_vim))
                        new_vl['refs'] = refs
                        vls_map[vl['id']].append(new_vl)

            response['mapping']['vl'] = vls_map

        LOG.info(str(response))
        topic = 'mano.service.place'

        # print(yaml.dump(response))
        self.manoconn.notify(topic,
                             yaml.dump(response),
                             correlation_id=prop.correlation_id)

        LOG.info("Placement response sent for service: " + content['serv_id'])


    def placement(self, dus, vls, vims, wims, eps, const, wghts=[], sng=False):
        """
        This method implements the actual placement logic.

        @param dus:    list of deployment units with attributes that need
                       placement. Can be cloudnative or virtual dus.
        @param vls:    list of virtual links between vnfs that require qos
                       considerations. 
        @param vims:   list of available VIMS with attributes
        @param wims:   list of available WIMS with attributes
        @param eps:    list of endpoints defined for the service. If virtual
                       links with qos exist between VNFs and an endpoint, the
                       endpoint should be attached to at least one of the WIMS.
        @param wghts:  list of weights for operator, developer and customer
                       influence on the placement result
        @param sng:    do VNFs need to be placed on a single PoP
        @param const:  dictionary of additional constraints set by the
                       operator, customer or developer.

        TODO:
                * support for unidirectional qos information on WIMs
                * support for more than bandwidth and latency qos
                * support for more than E-Line virtual links
                * support for developer constraintsf
                * support for customer constraints
                * support for more than cpu and ram resources
        """

        # If no weights are defined, operator gets to dominate procedure
        if wghts == []:
            wghts = [1.0, 0.0, 0.0]

        # Some initial input validation
        if not isinstance(const['op_constraint'], dict):
            return "Operator policies are not a dictionary", "ERROR"
        if not isinstance(const['cu_constraint'], dict):
            return "Customer policies are not a dictionary", "ERROR"

        if len(vims) < 1:
            return "No attached VIMs", "ERROR"

        LOG.info("Placement calculation started")

        # There are three types of decision vars: eps, dus and vls. They need
        # to be aggregated in a single list of decision vars.
        LOG.info("Create decision vars")

        offset_vls = len(dus)
        offset_eps_1 = len(vls) + offset_vls
        offset_wim = len(vims)
        offset_eps_2 = len(wims) + offset_wim

        var_dus = [(x,y) for x in range(len(dus)) for y in range(len(vims))]

        a = range(len(vls))
        b = range(len(vims + wims))
        var_vls = [(x + offset_vls,y) for x in a for y in b]

        c = range(len(eps))
        var_eps = [(x + offset_eps_1, x + offset_eps_2) for x in c]
#        print(var_eps)

        dec_var = var_dus + var_vls + var_eps

        # Setting up the ILP problem. All decisions var should be integer and 
        # either 0 or 1
        LOG.info("Creating ILP problem")
        variables = pulp.LpVariable.dicts('variables',
                                          dec_var,
                                          lowBound=0,
                                          upBound=1,
                                          cat=pulp.LpInteger)

        # We solve the problem as a minimization problem.
        lpProblem = pulp.LpProblem("Placement", pulp.LpMinimize)

        # Create objective based on customer policies
        # TODO: At this point, we don't have soft customer objectives
        cu_obj = 0

        # Create objective based on operator policies
        # Only var_dus is needed from the decision vars, because all 
        # operator objectives are based on vims for now, no wims involved
        op_obj = tools.calc_op_obj(variables,
                                   dus,
                                   vims,
                                   var_dus,
                                   const['op_constraint'],
                                   LOG)

        # Create objective based on developer policies
        dev_obj = tools.calc_dev_obj(const['dev_constraint'],
                                     dus,
                                     '',
                                     '',
                                     vims,
                                     variables,
                                     var_dus,
                                     LOG)

        # Creating the object function
        lpProblem += wghts[0] * op_obj[0] + \
                     wghts[1] * dev_obj[0] + \
                     wghts[2] * cu_obj

        # Add additional constraints created by developer policy model
        # translation
        for constraint in dev_obj[1]:
            lpProblem += constraint

        # Add additional constraints created by operator policy model
        # translation
        for constraint in op_obj[1]:
            lpProblem += constraint

        # Set hard constraints
        # PoP resources can not be exceeded
        for vim in vims:
            vim_i = vims.index(vim)
            if vim['type'] == 'vm':
                cpu_sum = sum(dus[x[0]]['cpu'] * variables[x] \
                          for x in var_dus if x[1] == vim_i)
                ram_sum = sum(dus[x[0]]['ram'] * variables[x] \
                          for x in var_dus if x[1] == vim_i)
                cpu_total = vim['core_used'] + cpu_sum
                ram_total = vim['memory_used'] + ram_sum
                lpProblem +=  cpu_total <= vim['core_total']
                lpProblem +=  ram_total <= vim['memory_total']

        # Every VNF should be assigned to exactly 1 PoP
        for du in dus:
            du_i = dus.index(du)
            sum_du = sum(variables[x] for x in var_dus if x[0] == du_i)
            lpProblem += sum_du == 1
            if 'placement_needed' in du.keys():
                if not du['placement_needed']:
                    used_vim = du['vim']
                    for vim in vims:
                        vim_i = vims.index(vim)
                        if vim['id'] == used_vim:
                            lpProblem += variables[(du_i, vim_i)] == 1
                            break

        # Add blacklist from customers. If PoP is on blacklist, no VNFs can
        # be on it.
        if 'blacklist' in const['cu_constraint'].keys():
            blacklist = const['cu_constraint']['blacklist']
            LOG.info("Customer blacklist: " + str(blacklist))
        else:
            LOG.info("No customer blacklist provided.")
            blacklist = []

        for vim in vims:
            vim_i = vims.index(vim)
            if vim['id'] in blacklist:
                vim_sum = sum(variables[x] for x in var_dus if x[1] == vim_i)
                lpProblem+= vim_sum == 0

        # set constraints for single PoP VNFs
        if sng:
            for du_1 in dus:
                du_1_i = dus.index(du_1)
                for du_2 in dus:
                    du_2_i = dus.index(du_2)
                    if du_1_i < du_2_i and du_1['nf_id'] == du_2['nf_id']:
                        for vim_i in range(len(vims)):
                            vim_du_1 = variables[(du_1_i, vim_i)]
                            vim_du_2 = variables[(du_2_i, vim_i)]
                            lpProblem += vim_du_1 == vim_du_2

        # Ensure that VMs can only be deployed on VM VIMs,
        # and containers on container VIMs.
        for du in dus:
            du_i = dus.index(du)
            for vim in vims:
                vim_i = vims.index(vim)
                if du['type'] != vim['type']:
                    lpProblem += variables[(du_i, vim_i)] == 0

        # Virtual links can only be mapped on one physical link
        for vl in vls:
            vl_i = vls.index(vl) + offset_vls
            sum_vl = sum(variables[x] for x in var_vls if x[0] == vl_i)
            lpProblem += sum_vl == 1

        # Preplaced virtual links should not be placed elsewhere
        vim_wim = vims + wims
        for vl in vls:
            if 'placement_needed' in vl.keys():
                if not vl['placement_needed']:
                    vl_i = vls.index(vl) + offset_vls
                    used_vim_wim = vl['vim_wim'][0]
                    for wim in vim_wim:
                        vim_wim_i = vim_wim.index(wim)
                        if str(wim['id']) == str(used_vim_wim):
                            lpProblem += variables[(vl_i, vim_wim_i)] == 1
                            break

        # Resources of physical links can't be overconsumed
        for wim in vim_wim:
            wim_i = vim_wim.index(wim)
            # Handle latency
            for vl in vls:
                vl_i = vls.index(vl) + offset_vls
                z = variables[(vl_i, wim_i)]
                lpProblem += z * vl['latency'] >= z * wim['latency']
            # Handle bandwidth
            sum_bw = sum(variables[x] * vls[x[0] - offset_vls]['bandwidth'] \
                     for x in var_vls if x[1] == wim_i)
            lpProblem += sum_bw <= wim['bandwidth']

        # Virtual links should be mapped on WIMS that connect the VIMs that
        # are hosting the VNFs of the virtual link. Take into account that
        # vl can connect an endpoint. These are on a fixed location, so their
        # placement is not part of the problem. The only thing that needs to
        # be done for them is attach to a WIM.
        adj_mat = [[0 for y in vims] for x in vim_wim]
        for i in range(len(vims)):
            adj_mat[i][i] = 1
        for wim in wims:
            i = wims.index(wim) + len(vims)
            for vim in vims:
                vim_i = vims.index(vim)
                if vim['id'] == wim['vim_1']:
                    adj_mat[i][vim_i] = 1
                if vim['id'] == wim['vim_2']:
                    adj_mat[i][vim_i] = 1

        for vl in vls:
            vl_i = vls.index(vl) + offset_vls
            x1_i = -1
            x2_i = -1
            for du in dus:
                if du['id'] == vl['nodes'][0]:
                    x1_i = dus.index(du)
                if du['id'] == vl['nodes'][1]:
                    x2_i = dus.index(du)

            for wim in vim_wim:
                wim_i = vim_wim.index(wim)

                if x1_i == -1:
                    if 'placement_needed' in vl.keys():
                        if not vl['placement_needed']:
                            sum_1 = 1
                    else:
                        for ep in eps:
                            if ep['id'] == vl['nodes'][0]:
                                if wim['id'] in ep['wims']:
                                    sum_1 = 1
                                else:
                                    sum_1 = 0
                else:
                    sum_1 = sum(variables[x] * adj_mat[wim_i][x[1]] \
                            for x in var_dus if x[0] == x1_i)
                if x2_i == -1:
                    if 'placement_needed' in vl.keys():
                        if not vl['placement_needed']:
                            sum_2 = 1
                    else:
                        for ep in eps:
                            if ep['id'] == vl['nodes'][1]:
                                if wim['id'] in ep['wims']:
                                    sum_2 = 1
                                else:
                                    sum_2 = 0
                else:
                    sum_2 = sum(variables[x] * adj_mat[wim_i][x[1]] \
                            for x in var_dus if x[0] == x2_i)

                lpProblem += sum_1 + sum_2 >= 2 * variables[(vl_i, wim_i)]

        # Solve the problem
        lpProblem.solve()

        # for var in variables:
        #     if variables[var].varValue == 1.0:
        #         LOG.info(variables[var].cat)
        #         LOG.info(variables[var].name)

        LOG.info(lpProblem)
        LOG.info(lpProblem.status)

        # processing the result
        result = {}

        if lpProblem.status != 1:
            err = str(lpProblem.status)
            msg = "Result of placement: infeasible, return code " + err
            LOG.info(msg)
            return result, msg

        result['dus'] = {}
        for du in dus:
            du_i = dus.index(du)
            for tup in var_dus:
                if tup[0] == du_i and variables[tup].varValue == 1:
                    vim_i = tup[1]
                    break
            result['dus'][du['id']] = vims[vim_i]['id']

        result['vls'] = {}
        for vl in vls:
            vl_i = vls.index(vl) + offset_vls
            for tup in var_vls:
                if tup[0] == vl_i and variables[tup].varValue == 1:
                    wim_i = tup[1]
                    break
            result['vls'][vl['id']] = vim_wim[wim_i]['id']

        result['optimum'] = lpProblem.objective.value()
        return result, None

def main():
    """
    Entry point to start plugin.
    :return:
    """
    placement = PlacementPlugin()

if __name__ == '__main__':
    main()
