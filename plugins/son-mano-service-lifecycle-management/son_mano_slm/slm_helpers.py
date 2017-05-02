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
partner consortium (www.sonata-nfv.eu).
"""
"""
This contains helper functions for `slm.py`.
"""

import requests
import uuid
import yaml

def convert_corr_id(corr_id):
    """
    This method converts the correlation id into an integer that is 
    small enough to be used with a modulo operation.

    :param corr_id: The correlation id as a String
    """ 

    #Select the final 4 digits of the string
    reduced_string = corr_id[-4:]
    reduced_int = int(reduced_string, 16)
    return reduced_int


def serv_id_from_corr_id(ledger, corr_id):
    """
    This method returns the service uuid based on a correlation id.
    It is used for responses from different modules that use the
    correlation id as reference instead of the service id.

    :param serv_dict: The ledger of services
    :param corr_id: The correlation id
    """

    for serv_id in ledger.keys():
        if isinstance(ledger[serv_id]['act_corr_id'], list):
            if str(corr_id) in ledger[serv_id]['act_corr_id']:
                break
        else:
            if ledger[serv_id]['act_corr_id'] == str(corr_id):
                break

    return serv_id

def generate_image_uuid(vdu, vnfd):
    """
    This method creates the image_uuid based on the vdu info in the
    vnfd
    """

    new_string = vnfd['vendor'] + '_' + vnfd['name'] + '_' + vnfd['version']
    new_string = new_string + '_' + vdu['id']

    return new_string


def placement(NSD, functions, topology):
    """
    This is the default placement algorithm that is used if the SLM
    is responsible to perform the placement
    """

    mapping = {}

    for function in functions:
        vnfd = function['vnfd']
        needed_cpu = vnfd['virtual_deployment_units'][0]['resource_requirements']['cpu']['vcpus']
        needed_mem = vnfd['virtual_deployment_units'][0]['resource_requirements']['memory']['size']
        needed_sto = vnfd['virtual_deployment_units'][0]['resource_requirements']['storage']['size']

#        print('vnfd considered ' + vnfd['name'] + ' ' + vnfd['instance_uuid'])

        for vim in topology:
            cpu_req = needed_cpu <= (vim['core_total'] - vim['core_used'])
            mem_req = needed_mem <= (vim['memory_total'] - vim['memory_used'])

#            print(str(needed_cpu) + ' ' + str(needed_mem))
#            print(str(vim['core_total']) + ' ' + str(vim['core_used']))
#            print(str(vim['memory_total']) + ' ' + str(vim['memory_used']))

            if cpu_req and mem_req:
                print('VNF ' + function['id'] + ' mapped on VIM ' + vim['vim_uuid'])
                mapping[function['id']] = {}
                mapping[function['id']]['vim'] = vim['vim_uuid']
                vim['core_used'] = vim['core_used'] + needed_cpu
                vim['memory_used'] = vim['memory_used'] + needed_mem
                break
    
    # Check if all VNFs have been mapped
    if len(mapping.keys()) == len(functions):
        return mapping
    else:
        return None

def build_resource_request(descriptors, vim):
    """
    This method builds a resource request message based on the needed resourcs.
    The needed resources for a service are described in the descriptors.
    """

    needed_cpu     = 0
    needed_memory  = 0
    needed_storage = 0

    memory_unit  = 'GB'
    storage_unit = 'GB'

    for key in descriptors.keys():
        if key[:4] == 'VNFD':
            needed_cpu = needed_cpu + descriptors[key]['virtual_deployment_units'][0]['resource_requirements']['cpu']['vcpus']
            needed_memory = needed_memory + descriptors[key]['virtual_deployment_units'][0]['resource_requirements']['memory']['size']
            needed_storage = needed_storage + descriptors[key]['virtual_deployment_units'][0]['resource_requirements']['storage']['size']

    return {'vim_uuid': vim, 'cpu': needed_cpu, 'memory': needed_memory, 'storage': needed_storage, 'memory_unit': memory_unit, 'storage_unit': storage_unit}


def replace_old_corr_id_by_new(dictionary, old_correlation_id):
    """
    This method takes a dictionary with uuid's as keys. The method replaces a
    certain key with a new uuid.
    """

    new_correlation_id = uuid.uuid4().hex
    dictionary[new_correlation_id] = dictionary[old_correlation_id]
    dictionary.pop(old_correlation_id, None)

    return new_correlation_id, dictionary


def build_nsr(request_status, nsd, vnfr_ids, service_instance_id):
    """
    This method builds the whole NSR from the payload (stripped nsr and vnfrs)
    returned by the Infrastructure Adaptor (IA).
    """

    nsr = {}
    # nsr mandatory fields
    nsr['descriptor_version'] = 'nsr-schema-01'
    nsr['id'] = service_instance_id
    nsr['status'] = request_status
    # Building the nsr makes it the first version of this nsr
    nsr['version'] = '1'
    nsr['descriptor_reference'] = nsd['uuid']

    # Future functionality
#    if 'instanceVimUuid' in ia_payload:
#        nsr['instanceVimUuid'] = ia_payload['instanceVimUuid']

    # network functions
    nsr['network_functions'] = []
    for vnfr_id in vnfr_ids:
        function = {}
        function['vnfr_id'] = vnfr_id
        nsr['network_functions'].append(function)

    # # connection points
    # if 'connection_points' in nsd:
    #     nsr['connection_points'] = []
    #     for connection_point in nsd['connection_points']:
    #         cp = {}
    #         cp['id'] = connection_point['id']
    #         cp['type'] = connection_point['type']
    #         nsr['connection_points'].append(cp)

    # virtual links
    if 'virtual_links' in nsd:
        nsr['virtual_links'] = []
        for virtual_link in nsd['virtual_links']:
            vlink = {}
            vlink['id'] = virtual_link['id']
            vlink['connectivity_type'] = virtual_link['connectivity_type']
            vlink['connection_points_reference'] = virtual_link['connection_points_reference']
            nsr['virtual_links'].append(vlink)

    # forwarding graphs
    if 'forwarding_graphs' in nsd:
        nsr['forwarding_graphs'] = []
        for forwarding_graph in nsd['forwarding_graphs']:
            nsr['forwarding_graphs'].append(forwarding_graph)

    # lifecycle events
    if 'lifecycle_events' in nsd:
        nsr['lifecycle_events'] = []
        for lifecycle_event in nsd['lifecycle_events']:
            nsr['lifecycle_events'].append(lifecycle_event)

    # vnf_dependency
    if 'vnf_dependency' in nsd:
        nsr['vnf_dependency'] = []
        for vd in nsd['vnf_dependency']:
            nsr['vnf_dependency'].append(vd)

    # services_dependency
    if 'services_dependency' in nsd:
        nsr['services_dependency'] = []
        for sd in nsd['services_dependency']:
            nsr['services_dependency'].append(sd)

    # monitoring_parameters
    if 'monitoring_parameters' in nsd:
        nsr['monitoring_parameters'] = []
        for mp in nsd['monitoring_parameters']:
            nsr['monitoring_parameters'].append(mp)

    # auto_scale_policy
    if 'auto_scale_policy' in nsd:
        nsr['auto_scale_policy'] = []
        for asp in nsd['auto_scale_policy']:
            nsr['monitoring_parameters'].append(asp)

    return nsr


def build_vnfr(ia_vnfr, vnfd):
    """
    This method builds the VNFR. VNFRS are built from the stripped VNFRs
    returned by the Infrastructure Adaptor (IA), combining it with the 
    provided VNFD.
    """

    vnfr = {}
    # vnfd base fields
    vnfr['descriptor_version'] = ia_vnfr['descriptor_version']
    vnfr['id'] = ia_vnfr['id']
    #Building the vnfr makes it the first version of this vnfr.
    vnfr['version'] = '1'
    vnfr['status'] = ia_vnfr['status']
    vnfr['descriptor_reference'] = ia_vnfr['descriptor_reference']

    # deployment flavour
    if 'deployment_flavour' in ia_vnfr:
        vnfr['deployment_flavour'] = ia_vnfr['deployment_flavour']

    # virtual_deployment_units
    vnfr['virtual_deployment_units'] = []
    for ia_vdu in ia_vnfr['virtual_deployment_units']:
        vnfd_vdu = get_vnfd_vdu_by_reference(vnfd, ia_vdu['vdu_reference'])

        vdu = {}
        # vdu info returned by IA
        # mandatofy info
        vdu['id'] = ia_vdu['id']
        vdu['resource_requirements'] = vnfd_vdu['resource_requirements']

        # vdu optional info
        if 'vm_image' in ia_vdu:
            vdu['vm_image'] = ia_vdu['vm_image']
        if 'vdu_reference' in ia_vdu:
            vdu['vdu_reference'] = ia_vdu['vdu_reference']
        if 'number_of_instances' in ia_vdu:
            vdu['number_of_instances'] = ia_vdu['number_of_instances']
        # vdu vnfc-instances (optional)
        vdu['vnfc_instance'] = []
        if 'vnfc_instance' in ia_vdu:
            for ia_vnfc in ia_vdu['vnfc_instance']:
                vnfc = {}
                vnfc['id'] = ia_vnfc['id']
                vnfc['vim_id'] = ia_vnfc['vim_id']
                vnfc['vc_id'] = ia_vnfc['vc_id']
#                vnfc['connection_points'] = ia_vnfc['connection_points']
                vnfc['connection_points'] = []
                for cp_ia in ia_vnfc['connection_points']:
                    new_cp = {}
                    new_cp['id'] = cp_ia['id']
                    cp_vnfd = get_vdu_cp_by_ref(vnfd, vdu['id'], new_cp['id'])
                    new_cp['type'] = cp_vnfd['type']
                    new_cp['interface'] = {}

                    new_cp['interface']['address'] = cp_ia['type']['address']
                    if 'netmask' in cp_ia['type'].keys():
                        new_cp['interface']['netmask'] = cp_ia['type']['netmask']
                    else:
                        new_cp['interface']['netmask'] = '255.255.255.248'

                    if 'hardware_address' in cp_ia['type'].keys():
                        new_cp['interface']['hardware_address'] = cp_ia['type']['hardware_address']

                    vnfc['connection_points'].append(new_cp)

                vdu['vnfc_instance'].append(vnfc)



        # vdu monitoring-parameters (optional)

        if vnfd_vdu is not None and 'monitoring_parameters' in vnfd_vdu:
            vdu['monitoring_parameters'] = vnfd_vdu['monitoring_parameters']

        vnfr['virtual_deployment_units'].append(vdu)

    # connection points && virtual links (optional)
    if 'connection_points' in ia_vnfr:
        vnfr['connection_points'] = ia_vnfr['connection_points']
    if 'virtual_links' in vnfd:
        vnfr['virtual_links'] = vnfd['virtual_links']

    # TODO vnf_address ???

    # lifecycle_events (optional)
    if 'lifecycle_events' in vnfd:
        vnfr['lifecycle_events'] = vnfd['lifecycle_events']

    return vnfr


def get_vnfd_vdu_by_reference(vnfd, vdu_reference):
    # TODO can we do it with functional programming?
    if 'virtual_deployment_units' in vnfd:
        for vnfd_vdu in vnfd['virtual_deployment_units']:
            if vnfd_vdu['id'] in vdu_reference:
                return vnfd_vdu
    return None

def get_vdu_cp_by_ref(vnfd, vdu_id, cp_id):

    if 'virtual_deployment_units' in vnfd:
        for vdu in vnfd['virtual_deployment_units']:
            if vdu['id'] == vdu_id:
                for cp in vdu['connection_points']:
                    if cp['id'] == cp_id:
                        return cp

    return None

def get_vnfd_by_reference(gk_request, vnfd_reference):

    for key in gk_request.keys():
        if key[:4] == 'VNFD':
            vnfd = gk_request[key]
            if vnfd['uuid'] == vnfd_reference:
                return vnfd

    return None


def build_monitoring_message(service, functions):
    """
    This method builds the message for the Monitoring Manager.
    """

    nsd = service['nsd']
    nsr = service['nsr']
    instance_vim_uuid = service['vim_uuid']

#    def get_matching_vdu(vnfrs, vnfd, vdu):
#        """
#        This method searches inside the VNFRs for the VDU that makes reference
#        to a specific VDU of a VNFD.
#        """
#        for vnfr in vnfrs:
#            if vnfr['descriptor_reference'] == vnfd['uuid']:
#                for nsr_vdu in vnfr['virtual_deployment_units']:
#                    if vdu['id'] in nsr_vdu['vdu_reference']:
#                        return nsr_vdu
#
#        return None

    def get_associated_monitoring_rule(vnfd, monitoring_parameter_name):
        """
        This method searches with monitoring rule of the VNFD is assocated to a
        monitoring parameter, identified by the provided monitoring_parameter
        name.
        """
        if 'monitoring_rules' in vnfd.keys():
            for mp in vnfd['monitoring_rules']:
                if monitoring_parameter_name in mp['condition']:
                    return mp
        return None

    def get_threshold(condition):
        """
        This method retrieves a threshold from a condition message.
        """
        if '>' in condition:
            return condition.split('>', 1)[-1].strip()
        elif '<' in condition:
            return condition.split('<', 1)[-1].strip()

        return None

    message = {}
    service = {}

    # add nsd fields
    service['sonata_srv_id'] = nsr['id']
    service['name'] = nsd['name']
    service['description'] = nsd['description']
    service['host_id'] = instance_vim_uuid
    # TODO add pop_id and sonata_usr_id
    service['pop_id'] = None
    service['sonata_usr_id'] = None
    message['service'] = service

    message['functions'] = []
    message['rules'] = []

    # This dictionary will store the relationship beween the vdu['id'] and the
    # host_id, to be later used when building the metrics part of the message.
    vdu_hostid = {}

    # add vnf information
    for vnf in functions:

        print(vnf.keys())
        function = {}
        vnfr = vnf['vnfr']
        vnfd = vnf['vnfd']

        function['sonata_func_id'] = vnfr['id']
        function['name'] = vnfd['name']
        function['description'] = vnfd['description']
        function['pop_id'] = ""

        # message['functions'].append(function)

        vdu_hostid = {}

        # we should create one function per virtual deployment unit
        for vdu in vnfr['virtual_deployment_units']:


            # FIXME for the first version, relationshop between VNFC and VDU is 1-1. Change it in the future.
            vdu_name = vdu['vdu_reference'].split(':')[1]
            vnfc = vdu['vnfc_instance'][0]
            vdu_hostid[vdu_name] = vnfc['vc_id']

            function['host_id'] = vdu_hostid[vdu_name]

            if 'monitoring_parameters' in vdu:
                func = function.copy()
                func['metrics'] = []
                for mp in vdu['monitoring_parameters']:
                    metric = {}
                    metric['name'] = mp['name']
                    metric['unit'] = mp['unit']

                    associated_rule = get_associated_monitoring_rule(vnfd, mp['name'])
                    if (associated_rule is not None):
                        if 'threshold' in mp.keys():
                            metric['threshold'] = mp['threshold']
                        else:
                            metric['threshold'] = None
                        if 'frequency' in mp.keys():
                            metric['interval'] = mp['frequency']
                        else:
                            metric['interval'] = None
                        if 'command' in mp.keys():
                            metric['cmd'] = mp['command']
                        else:
                            metric['cmd'] = None
                        if 'description' in mp.keys():
                            metric['description'] = mp['description']
                        else:
                            metric['description'] = ""

                        func['metrics'].append(metric)

                message['functions'].append(func)

            else:
                function['metrics'] = []
                message['functions'].append(function)

        if 'monitoring_rules' in vnfd.keys():

            # variable used to map the received notification_type to the
            # integers expected by the monitoring repo
            notification_type_mapping = {}
            notification_type_mapping['sms'] = 1
            notification_type_mapping['rabbitmq_message'] = 2
            notification_type_mapping['email'] = 3

            for mr in vnfd['monitoring_rules']:
                rule = {}
                rule['name'] = mr['name']
                rule['summary'] = ''
                rule['duration'] = str(mr['duration']) + mr['duration_unit']

                if 'description' in mr.keys():
                    rule['description'] = mr['description']
                else:
                    rule['description'] = ""

                # TODO add condition
                vdu_id = mr['condition'].split(":")[0]
                host_id = vdu_hostid[vdu_name]
                rule['condition'] = host_id + ":" + mr['condition'].split(":")[1]

                # we add a rule for each notification type
                for notification in mr['notification']:
                    r = rule
                    r['notification_type'] = notification_type_mapping[notification['type']]
                    # add rule to message
                    message['rules'].append(r)

    return message
