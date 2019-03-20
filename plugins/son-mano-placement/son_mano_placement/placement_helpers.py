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

import pulp


def abs_load_diff(ilp_vars, x, y, vnfs, vims, dec_vars, types=['cpu', 'ram']):
    """
    Calculating the actual load difference between two vims x and y.
    """

    load_x = 0.0
    load_y = 0.0

    for res_type in types:
        if res_type == 'cpu':
            type_used = 'core_used'
            type_tot = 'core_total'
        if res_type == 'ram':
            type_used = 'memory_used'
            type_tot = 'memory_total'

        used_x = sum(vnfs[k[0]][res_type] * ilp_vars[k] for k in dec_vars if k[1] == x)
        load_x = load_x + (vims[x][type_used] + used_x) / vims[x][type_tot]

        used_y = sum(vnfs[k[0]][res_type] * ilp_vars[k] for k in dec_vars if k[1] == y)
        load_y = load_y + (vims[y][type_used] + used_y) / vims[y][type_tot]

    return load_x / len(types) - load_y / len(types)


def number_of_vnfs_mapped_to_pop(ilp_vars, x, dec_vars):

    number_of_vnf = 0
    for combo in dec_vars:
        if combo[1] == x:
            number_of_vnf = number_of_vnf + ilp_vars[combo]
    return number_of_vnf


def calc_op_obj(ilp_vars, vnfs, vims, dec_vars, op_pol, LOG):

    LOG.info("Active operator Policy: " + str(op_pol))
    op_obj = 0
    add_constr = []

    # Setting up the operator_factor. When the load is balanced, the difference
    # in load between vims needs to be minimized, hence factor 1. When vims
    # need to be used in a fill first capacity, the difference in load between
    # vims should be maximised, or the inverse minimised, hence factor -1
    op_factor = 0
    if op_pol['policy'] == 'load balanced':
        op_factor = 1
    if op_pol['policy'] == 'fill first':
        op_factor = -1

    if op_factor != 0:
        # Creating expressions for fill first or load balanced objectives, we
        # have to deal with absolute values, which require the introduction of
        # new variables to be described as an ilp constraint, as well as new
        # constraints
        constr_to_add = {}
        new_floats1 = []
        new_floats2 = []
        new_bins = []
        for x in range(len(vims)):
            for y in range(len(vims)):
                if x < y:
                    # expression of which absolute value should be minimized
                    expr = abs_load_diff(ilp_vars, y, x, vnfs, vims, dec_vars)
                    # new dec vars to problem to bypass absolute value issue
                    nameFloat1 = "extraFloat1_" + str(x) + "_" + str(y)
                    nameFloat2 = "extraFloat2_" + str(x) + "_" + str(y)
                    nameBin = "extraBin_" + str(x) + "_" + str(y)
                    new_floats1.append(nameFloat1)
                    new_floats2.append(nameFloat2)
                    new_bins.append(nameBin)
                    # we need to store the new constraints to be added after
                    # object function is defined
                    constr_to_add[nameFloat1] = expr

        flts1 = pulp.LpVariable.dicts('extra_Float1',
                                      new_floats1,
                                      lowBound=0,
                                      upBound=1)
        flts2 = pulp.LpVariable.dicts('extra_Float2',
                                      new_floats2,
                                      lowBound=0,
                                      upBound=1)
        bins = pulp.LpVariable.dicts('extra_bin',
                                     new_bins,
                                     lowBound=0,
                                     upBound=1,
                                     cat=pulp.LpInteger)

        # Combine all objectives in object function
        rn = range(len(new_floats1))
        op_obj = sum(flts1[new_floats1[x]] + flts2[new_floats2[x]] for x in rn)
        op_obj = op_factor * op_obj 

        # Add the constraints related to the new variables
        for index in range(len(new_floats1)):
            bn = bins[new_bins[index]]
            ft1 = flts1[new_floats1[index]]
            ft2 = flts2[new_floats2[index]]
            add_constr.append(ft1 - ft2 == constr_to_add[new_floats1[index]])
            add_constr.append(ft1 <= bn)
            add_constr.append(ft2 <= 1 - bn)

    elif op_pol['policy'] == 'priority':
        number_of_vnfs = []
        priority_log = []
        priorityList = op_policy['policy_list']
        LOG.info("Priority list: " + str(priorityList))

        for index in range(len(vims)):
            vim_name = vims[index]['id']

            if vim_name in priorityList:
                priority = len(vims) - priorityList.index(vim_name)
            else:
                LOG.info("PoP not in priority list: " + str(vim_name))
                priority = 1

            x = number_of_vnfs_mapped_to_pop(ilp_vars, index, dec_vars)
            number_of_vnfs.append(x)
            priority_log.append(priority)

        rn = range(len(priority_log))
        op_obj = (-1) * sum(number_of_vnfs[x] * priority_log[x] for x in rn)

    else:
        LOG.info("No supported operator policy set.")

    return op_obj, add_constr


def calc_dev_obj(constr, dus, src, dest, vims, ilp_vars, dec_vars, LOG):

    # If no soft constraints have been defined, there is no objective
    if not constr:
        return 0, {}, {}, {}

    # TODO: code needs revision
    return 0, {}, {}, {}

    # dev_obj = 0
    # add_constr = []

    # # Account for the distance factor
    # dist_constr = []
    # for constraint in constr:
    #     if constraint['objective'] in ['proximity', 'affinity']:
    #         dist_constr.append(constraint['involved_actors'])
    # LOG.info("Distance constr: " + str(dist_constr))

    # # Check if IPs are provided for source and destination if they are used
    # # in the soft constraints
    # act_constr = []
    # for constraint in dist_constr:
    #     constr_complete = True
    #     if 'source' in constraint:
    #         if not src:
    #             constraint_complete = False
    #             LOG.info("constraint useless due missing src IP.")
    #     if 'destination' in constraint:
    #         if not dest:
    #             constraint_complete = False 
    #             LOG.info("constraint useless due missing dest IP.")
    #     if constraint_complete:
    #         act_constr.append(constraint)

    # dist_matrix = calc_dist(src, dest, vims, LOG)
    # LOG.info("Distance matrix: " + str(dist_matrix))

    # for constraint in act_constr:
    #     indexes_first_vnf = find_images_vnf_indexes(nsd, vnfs, images_to_map, constr[0])
    #     indexes_second_vnf = find_images_vnf_indexes(nsd, vnfs, images_to_map, constr[1])

    #     if indexes_first_vnf != [] and indexes_second_vnf != []:
    #         new_bins = []
    #         matrix_equivalent = []
    #         old_var_1 = []
    #         old_var_2 = []
    #         for index_1 in indexes_first_vnf:
    #             for index_2 in indexes_second_vnf:
    #                 for pop_1 in range(len(top)):
    #                     for pop_2 in range(len(top)):
    #                         new_name = "extraDeveloperBin_" + str(index_1) + "_" + str(index_2) + "_" + str(pop_1) + "_" + str(pop_2)
    #                         new_bins.append(new_name)
    #                         matrix_equivalent.append(distance_matrix[pop_1][pop_2])
    #                         old_var_1.append(variables[(index_1, pop_1)])
    #                         old_var_2.append(variables[(index_2, pop_2)])

    #         new_bins_lp = pulp.LpVariable.dicts('extra_bins', new_bins, lowBound=0, upBound=1, cat=pulp.LpInteger)

    #         # Combine all objectives in object function
    #         LOG.info(str(matrix_equivalent))
    #         developer_objective += sum((-1) * new_bins_lp[new_bins[x]] * matrix_equivalent[x] / 4 for x in range(len(new_bins)))

    #         for new_constraint in range(len(new_bins)):
    #             additional_constraints.append(new_bins_lp[new_bins[new_constraint]] <= (old_var_1[new_constraint] + old_var_2[new_constraint])/2.0)

    #     else:
    #         if constr[0] in ['source', 'destination']:
    #             indexes_vnf = indexes_second_vnf
    #             if constr[0] == 'source':
    #                 index_endpoint = len(top)
    #             if constr[0] == 'destination':
    #                 index_endpoint = len(top) + 1
    #         else:
    #             indexes_vnf = indexes_first_vnf
    #             if constr[1] == 'source':
    #                 index_endpoint = len(top)
    #             if constr[1] == 'destination':
    #                 index_endpoint = len(top) + 1

    #         for index in indexes_vnf:
    #             for pop in range(len(top)):
    #                 developer_objective += (-1) * variables[(index, pop)] * distance_matrix[pop][index_endpoint]
    #         LOG.info(developer_objective)

    # return developer_objective, additional_constraints

def find_images_vnf_indexes(nsd, vnfs, images_to_map, vnf_id):

    if vnf_id in ['source', 'destination']:
        return []

    for vnf_desc in nsd['network_functions']:
        if vnf_desc['vnf_id'] == vnf_id:
            name = vnf_desc["vnf_name"]
            version = vnf_desc["vnf_version"]
            vendor = vnf_desc["vnf_vendor"]

    for vnf in vnfs:
        vnfd = vnf['vnfd']
        if vnfd['vendor'] == vendor:
            if vnfd['name'] == name:
                if vnfd['version'] == version:
                    function_id = vnf['id']

    indexes = []
    for index in range(len(images_to_map)):
        if images_to_map[index]['function_id'] == function_id:
            indexes.append(index)

    return indexes


def calculate_distances(source, destination, pop, LOG, weightfactor=1):

    matrix = []

    for index_x in range(len(pop) + 2):
        matrix.append([])
        for index_y in range(len(pop) + 2):
            if index_x == len(pop):
                ip_x = source
            elif index_x == len(pop) + 1:
                ip_x = destination
            else:
                ip_x = pop[index_x]['vim_endpoint']

            if index_y == len(pop):
                ip_y = source
            elif index_y == len(pop) + 1:
                ip_y = destination
            else:
                ip_y = pop[index_y]['vim_endpoint']
            matrix[index_x].append((find_number_of_common_segments(ip_x, ip_y, LOG)) ** weightfactor)

    return matrix


def find_number_of_common_segments(first_ip, second_ip, LOG):

    if not first_ip:
        return 0

    if not second_ip:
        return 0

    first_segments = first_ip.split('.')
    second_segments = second_ip.split('.')

    if first_segments == second_segments:
        return 4

    elif first_segments[:3] == second_segments[:3]:
        return 3

    elif first_segments[:2] == second_segments[:2]:
        return 2

    elif first_segments[0] == second_segments[0]:
        return 1
    else:
        return 0


def convert_name_to_index(name, vnfs):

    for index in range(len(vnfs)):
        if vnfs[index]['name'] == name:
            return index

def map_ref_on_id(ref, nsd, vnfds, eps):
    """
    This method is used to map a reference in a virtual link descriptor on
    a deployment unit.
    """
    if ':' in ref:
        # reference is towards a vnf
        for vnf in nsd['network_functions']:
            if vnf['vnf_id'] == ref.split(':')[0]:
                vnf_name = vnf['vnf_name']
                vnf_version = vnf['vnf_version']
                vnf_vendor = vnf['vnf_vendor']
                break
        for vnfd in vnfds:
            if vnfd['name'] == vnf_name and vnfd['version'] == vnf_version and \
               vnfd['vendor'] == vnf_vendor:
               break

        for vl in vnfd['virtual_links']:
            cpr = vl['connection_points_reference']
            if ref.split(':')[1] in cpr:
                ref_i = cpr.index(ref.split(':')[1])
                du_int_ref = cpr[len(cpr) - 1 - ref_i]
                du_ref = du_int_ref.split(':')[0]
                break

        if 'cloudnative_deployment_units' in vnfd.keys():
            for cdu in vnfd['cloudnative_deployment_units']:
                if cdu['id'].startswith(du_ref):
                    return cdu['id']

        if 'virtual_deployment_units' in vnfd.keys():
            for vdu in vnfd['virtual_deployment_units']:
                if vdu['id'].startswith(du_ref):
                    return vdu['id']

    else:
        # reference is towards an endpoint
        # TODO: find a solid way to differentiate between ingress and egress,
        # currently, we assume that ingress comes before egress in the nsd cp
        # list. If there is only one, we assume that it is ingress
        cps = nsd['connection_points']
        for cp in cps:
            if cp['id'] == ref:
                cp_i = cps.index(cp)
        if len(cps) == 1:
            for ep in eps:
                if ep['type'] == 'ingress':
                    return ep['id']
        if len(eps) == 3 and cp_i == 1:
            for ep in eps:
                if ep['type'] == 'ingress':
                    return ep['id']
        if len(eps) == 3 and cp_i == 2:
            for ep in eps:
                if ep['type'] == 'egress':
                    return ep['id']
        if len(eps) == 2 and cp_i == 0:
            for ep in eps:
                if ep['type'] == 'ingress':
                    return ep['id']
        if len(eps) == 2 and cp_i == 1:
            for ep in eps:
                if ep['type'] == 'egress':
                    return ep['id']
            return eps[0]['id']

    return None