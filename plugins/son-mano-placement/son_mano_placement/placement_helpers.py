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


def absolute_load_difference(variables, x, y, vnfs, pop, possible_combinations, resource_types=['cpu', 'ram']):

    load_x = 0.0
    load_y = 0.0

    for resource_type in resource_types:
        if resource_type == 'cpu':
            type_used = 'core_used'
            type_tot = 'core_total'
        if resource_type == 'ram':
            type_used = 'memory_used'
            type_tot = 'memory_total'

        used_x = pop[x][type_used] + sum(vnfs[k[0]][resource_type] * variables[k] for k in possible_combinations if k[1] == x)
        load_x = load_x + used_x / pop[x][type_tot]

        used_y = pop[y][type_used] + sum(vnfs[k[0]][resource_type] * variables[k] for k in possible_combinations if k[1] == y)
        load_y = load_y + used_y / pop[y][type_tot]

    return load_x / len(resource_types) - load_y / len(resource_types)


def number_of_vnfs_mapped_to_pop(variables, x, possible_combinations, log):

    number_of_vnf = 0
    for combo in possible_combinations:
        if combo[1] == x:
#            log.info(str(combo))
            number_of_vnf = number_of_vnf + variables[combo]
    return number_of_vnf


def get_image_list(vnfs):

    images_to_map = []
    for vnf in vnfs:
        vnfd = vnf['vnfd']
        for vdu in vnfd['virtual_deployment_units']:
            new_dict = {}
            req = vdu['resource_requirements']
            new_dict['cpu'] = req['cpu']['vcpus']
            new_dict['ram'] = req['memory']['size']
            if req['memory']['size_unit'] == 'MB':
                new_dict['ram'] = new_dict['ram'] / 1024.0
            new_dict['storage'] = req['storage']['size']
            if req['storage']['size_unit'] == 'MB':
                new_dict['storage'] = new_dict['storage'] / 1024.0
            new_dict['function_id'] = vnf['id']
            new_dict['id'] = str(vnf['id']) + '_' + vdu['id']
            new_dict['needs_placement'] = True
            if 'deployed' in vnf.keys():
                new_dict['needs_placement'] = False
                new_dict['vim'] = vnf['vim_uuid']
                new_dict['cpu'] = 0
                new_dict['ram'] = 0
                new_dict['storage'] = 0
            images_to_map.append(new_dict)

    return images_to_map


def calculate_operator_objective(variables, images_to_map, top, decision_vars, op_policy, LOG, serv_id):

    LOG.info(str(serv_id) + ": Operator Policy: " + str(op_policy))
    operator_objective = 0
    additional_constraints = []

    operator_factor = 0
    if op_policy['policy'] == 'load balanced':
        operator_factor = 1
    if op_policy['policy'] == 'fill first':
        operator_factor = -1

    if operator_factor != 0:
        soft_constraints_to_add = {}
        list_of_new_floats1 = []
        list_of_new_floats2 = []
        list_of_new_bins = []
        for x in range(len(top)):
            for y in range(len(top)):
                if x < y:
                    # create expression of which absolute value should be minimized
                    expression = absolute_load_difference(variables, y, x, images_to_map, top, decision_vars)
                    # add new decision variables to problem to bypass absolute value issue
                    nameFloat1 = "extraFloat1_" + str(x) + "_" + str(y)
                    nameFloat2 = "extraFloat2_" + str(x) + "_" + str(y)
                    nameBin = "extraBin_" + str(x) + "_" + str(y)
                    list_of_new_floats1.append(nameFloat1)
                    list_of_new_floats2.append(nameFloat2)
                    list_of_new_bins.append(nameBin)
                    # we need to store the new constraints to be added after object
                    # object function is defined
                    soft_constraints_to_add[nameFloat1] = expression

        new_floats1 = pulp.LpVariable.dicts('extra_Float1', list_of_new_floats1, lowBound=0, upBound=1)
        new_floats2 = pulp.LpVariable.dicts('extra_Float2', list_of_new_floats2, lowBound=0, upBound=1)
        new_bins = pulp.LpVariable.dicts('extra_bin', list_of_new_bins, lowBound=0, upBound=1, cat=pulp.LpInteger)

        # Combine all objectives in object function
        operator_objective += operator_factor * sum(new_floats1[x] + new_floats2[y] for x in list_of_new_floats1 for y in list_of_new_floats2)

        # Add the constraints related to the new variables
        additional_constraints
        for index in range(len(list_of_new_floats1)):
            bn = new_bins[list_of_new_bins[index]]
            ft1 = new_floats1[list_of_new_floats1[index]]
            ft2 = new_floats2[list_of_new_floats2[index]]
            additional_constraints.append(ft1 - ft2 == soft_constraints_to_add[list_of_new_floats1[index]])
            additional_constraints.append(ft1 <= bn)
            additional_constraints.append(ft2 <= 1 - bn)

    elif op_policy['policy'] == 'priority':
        number_of_vnfs = []
        priority_log = []
        priorityList = op_policy['policy_list']
        LOG.info(str(serv_id) + ": Priority list: " + str(priorityList))

        for index in range(len(top)):
            vim_name = top[index]['vim_name']

            if vim_name in priorityList:
                priority = len(top) - priorityList.index(vim_name)
            else:
                LOG.info(str(serv_id) + ": PoP not in priority list: " + str(vim_name))
                priority = 1

            number_of_vnfs.append(number_of_vnfs_mapped_to_pop(variables, index, decision_vars, LOG))
            priority_log.append(priority)

        operator_objective += (-1) * sum(number_of_vnfs[x] * priority_log[x] for x in range(len(priority_log)))

    else:
        LOG.info(str(serv_id) + ": No supported operator policy set.")

    return operator_objective, additional_constraints


def calculate_developer_objective(nsd, vnfs, source_ip, dest_ip, images_to_map, top, variables, decision_vars, LOG, serv_id):

    # If no soft constraints have been defined, there is no objective
    if 'soft_constraints' not in nsd.keys():
        return 0, {}, {}, {}

    developer_objective = 0
    additional_constraints = []

    # Account for the distance factor
    distance_constraints = []
    for constraint in nsd['soft_constraints']:
        if constraint['objective'] in ['proximity', 'affinity']:
            distance_constraints.append(constraint['involved_actors'])
    LOG.info(str(serv_id) + ": Distance constr: " + str(distance_constraints))

    # Check if IPs are provided for source and destination if they are used
    # in the soft constraints
    complete_constraints = []
    for constraint in distance_constraints:
        constraint_complete = True
        if 'source' in constraint:
            if not source_ip:
                constraint_complete = False
                LOG.info(str(serv_id) + ": constraint useless due missing IP.")
        if 'destination' in constraint:
            if not dest_ip:
                constraint_complete = False 
                LOG.info(str(serv_id) + ": constraint useless due missing IP.")
        if constraint_complete:
            complete_constraints.append(constraint)

    distance_matrix = calculate_distances(source_ip, dest_ip, top, LOG)
    LOG.info(str(serv_id) + ": Distance matrix: " + str(distance_matrix))

    for constr in complete_constraints:
        indexes_first_vnf = find_images_vnf_indexes(nsd, vnfs, images_to_map, constr[0])
        indexes_second_vnf = find_images_vnf_indexes(nsd, vnfs, images_to_map, constr[1])

        if indexes_first_vnf != [] and indexes_second_vnf != []:
            new_bins = []
            matrix_equivalent = []
            old_var_1 = []
            old_var_2 = []
            for index_1 in indexes_first_vnf:
                for index_2 in indexes_second_vnf:
                    for pop_1 in range(len(top)):
                        for pop_2 in range(len(top)):
                            new_name = "extraDeveloperBin_" + str(index_1) + "_" + str(index_2) + "_" + str(pop_1) + "_" + str(pop_2)
                            new_bins.append(new_name)
                            matrix_equivalent.append(distance_matrix[pop_1][pop_2])
                            old_var_1.append(variables[(index_1, pop_1)])
                            old_var_2.append(variables[(index_2, pop_2)])

            new_bins_lp = pulp.LpVariable.dicts('extra_bins', new_bins, lowBound=0, upBound=1, cat=pulp.LpInteger)

            # Combine all objectives in object function
            LOG.info(str(matrix_equivalent))
            developer_objective += sum((-1) * new_bins_lp[new_bins[x]] * matrix_equivalent[x] / 4 for x in range(len(new_bins)))

            for new_constraint in range(len(new_bins)):
                additional_constraints.append(new_bins_lp[new_bins[new_constraint]] <= (old_var_1[new_constraint] + old_var_2[new_constraint])/2.0)

        else:
            if constr[0] in ['source', 'destination']:
                indexes_vnf = indexes_second_vnf
                if constr[0] == 'source':
                    index_endpoint = len(top)
                if constr[0] == 'destination':
                    index_endpoint = len(top) + 1
            else:
                indexes_vnf = indexes_first_vnf
                if constr[1] == 'source':
                    index_endpoint = len(top)
                if constr[1] == 'destination':
                    index_endpoint = len(top) + 1

            for index in indexes_vnf:
                for pop in range(len(top)):
                    developer_objective += (-1) * variables[(index, pop)] * distance_matrix[pop][index_endpoint]
            LOG.info(developer_objective)

    return developer_objective, additional_constraints

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
