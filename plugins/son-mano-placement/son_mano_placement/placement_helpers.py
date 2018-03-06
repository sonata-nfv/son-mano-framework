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

def absolute_load_difference(variables, x, y, vnfs, pop, possible_combinations, resource_type='cpu'):

    if resource_type == 'cpu':
        type_used =  'core_used'
        type_tot = 'core_total'
    if resource_type == 'ram':
        type_used =  'memory_used'
        type_tot = 'memory_total'

    used_x = pop[x][type_used] + sum(vnfs[k[0]][resource_type] * variables[k] for k in possible_combinations if k[1] == x)
    load_x = 1.0 * used_x / pop[x][type_tot]

    used_y = pop[y][type_used] + sum(vnfs[k[0]][resource_type] * variables[k] for k in possible_combinations if k[1] == y)
    load_y = 1.0 * used_y / pop[y][type_tot]

    return load_x - load_y

def number_of_vnfs_mapped_to_pop(variables, x, possible_combinations, log):

    number_of_vnf = 0
    for combo in possible_combinations:
        if combo[1] == x:
#            log.info(str(combo))
            number_of_vnf = number_of_vnf + variables[combo]
    return number_of_vnf


def calculate_distances(metric, source, destination, pop, weightfactor=1):

    if metric == 'IP':
        result = {}
        result['source'] = []
        result['destination'] = []

        for unit in pop:
            common_source_segments = find_number_of_common_segments(source, unit['ip'])
            common_dest_segments = find_number_of_common_segments(destination, unit['ip'])

            result['source'].append((4 - common_source_segments) ** weightfactor)
            result['destination'].append((4 - common_dest_segments) ** weightfactor)

    return result


def find_number_of_common_segments(first_ip, second_ip):

    first_segments = first_ip.split('.')
    second_segments = second_ip.split('.')

    if first_segments == second_segments:
        return 4

    if first_segments[:3] == second_segments[:3]:
        return 3

    if first_segments[:2] == second_segments[:2]:
        return 2

    if first_segments[0] == second_segments[0]:
        return 1


def convert_name_to_index(name, vnfs):

    for index in range(len(vnfs)):
        if vnfs[index]['name'] == name:
            return index
