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


def build_message_for_IA(request_dictionary):
    """
    This method converts the deploy request from the gk to a messsaga for the
    IA.
    """
    resulting_message = {}
    resulting_message['vim_uuid'] = request_dictionary['vim']
    resulting_message['nsd'] = request_dictionary['NSD']
    resulting_message['vnfds'] = []

    for key in request_dictionary.keys():
        if key[:4] == 'VNFD':
            resulting_message['vnfds'].append(request_dictionary[key])

    newFile = open('service_request.yml', 'w')
    newFile.write(yaml.dump(resulting_message))
    return resulting_message


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


def build_nsr(gk_request, ia_payload):
    """
    This method builds the whole NSR from the payload (stripped nsr and vnfrs)
    returned by the Infrastructure Adaptor (IA).
    """

    nsr = {}
    # nsr mandatory fields
    nsr['descriptor_version'] = 'nsr-schema-01'
    nsr['id'] = ia_payload['nsr']['id']
    nsr['status'] = ia_payload['nsr']['status']
    # Building the nsr makes it the first version of this nsr
    nsr['version'] = '1'
    nsr['descriptor_reference'] = gk_request['NSD']['uuid']

    # Future functionality
#    if 'instanceVimUuid' in ia_payload:
#        nsr['instanceVimUuid'] = ia_payload['instanceVimUuid']

    # network functions
    if 'vnfrs' in ia_payload.keys():
        nsr['network_functions'] = []
        for network_function in ia_payload['vnfrs']:
            function = {}
            function['vnfr_id'] = network_function['id']
            nsr['network_functions'].append(function)

    # connection points
    if 'connection_points' in gk_request['NSD']:
        nsr['connection_points'] = []
        for connection_point in gk_request['NSD']['connection_points']:
            cp = {}
            cp['id'] = connection_point['id']
            cp['type'] = connection_point['type']
            nsr['connection_points'].append(cp)

    # virtual links
    if 'virtual_links' in gk_request['NSD']:
        nsr['virtual_links'] = []
        for virtual_link in gk_request['NSD']['virtual_links']:
            vlink = {}
            vlink['id'] = virtual_link['id']
            vlink['connectivity_type'] = virtual_link['connectivity_type']
            vlink['connection_points_reference'] = virtual_link['connection_points_reference']
            nsr['virtual_links'].append(vlink)

    # forwarding graphs
    if 'forwarding_graphs' in gk_request['NSD']:
        nsr['forwarding_graphs'] = []
        for forwarding_graph in gk_request['NSD']['forwarding_graphs']:
            nsr['forwarding_graphs'].append(forwarding_graph)

    # lifecycle events
    if 'lifecycle_events' in gk_request['NSD']:
        nsr['lifecycle_events'] = []
        for lifecycle_event in gk_request['NSD']['lifecycle_events']:
            nsr['lifecycle_events'].append(lifecycle_event)

    # vnf_dependency
    if 'vnf_dependency' in gk_request['NSD']:
        nsr['vnf_dependency'] = []
        for vd in gk_request['NSD']['vnf_dependency']:
            nsr['vnf_dependency'].append(vd)

    # services_dependency
    if 'services_dependency' in gk_request['NSD']:
        nsr['services_dependency'] = []
        for sd in gk_request['NSD']['services_dependency']:
            nsr['services_dependency'].append(sd)

    # monitoring_parameters
    if 'monitoring_parameters' in gk_request['NSD']:
        nsr['monitoring_parameters'] = []
        for mp in gk_request['NSD']['monitoring_parameters']:
            nsr['monitoring_parameters'].append(mp)

    # auto_scale_policy
    if 'auto_scale_policy' in gk_request['NSD']:
        nsr['auto_scale_policy'] = []
        for asp in gk_request['NSD']['auto_scale_policy']:
            nsr['monitoring_parameters'].append(asp)

    return nsr


def build_vnfrs(gk_request, ia_vnfrs):
    """
    This method builds the different VNFRS a NSR consists of. VNFRS are built
    from the stripped VNFRs returned by the Infrastructure Adaptor (IA),
    combining it with the provided VNFD.
    """
    vnfrs = []
    for ia_vnfr in ia_vnfrs:
        vnfd = get_vnfd_by_reference(gk_request, ia_vnfr['descriptor_reference'])

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
                    vnfc['connection_points'] = ia_vnfc['connection_points']
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

        vnfrs.append(vnfr)

    return vnfrs


def get_vnfd_vdu_by_reference(vnfd, vdu_reference):
    # TODO can we do it with functional programming?
    if 'virtual_deployment_units' in vnfd:
        for vnfd_vdu in vnfd['virtual_deployment_units']:
            if vnfd_vdu['id'] in vdu_reference:
                return vnfd_vdu
    return None


def get_vnfd_by_reference(gk_request, vnfd_reference):

    for key in gk_request.keys():
        if key[:4] == 'VNFD':
            vnfd = gk_request[key]
            if vnfd['uuid'] == vnfd_reference:
                return vnfd

    return None


def build_monitoring_message(gk_request, message_from_ia, nsr, vnfrs):
    """
    This method builds the message for the Monitoring Manager.
    """

    def get_matching_vdu(vnfrs, vnfd, vdu):
        """
        This method searches inside the VNFRs for the VDU that makes reference
        to a specific VDU of a VNFD.
        """
        for vnfr in vnfrs:
            if vnfr['descriptor_reference'] == vnfd['uuid']:
                for nsr_vdu in vnfr['virtual_deployment_units']:
                    if vdu['id'] in nsr_vdu['vdu_reference']:
                        return nsr_vdu

        return None

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

    def get_vnfd_by_id(gk_request, vnfd_reference):
        for key in gk_request.keys():
            if key[:4] == 'VNFD':
                if gk_request[key]['uuid'] == vnfd_reference:
                    return gk_request[key]

        return None

    message = {}
    service = {}

    nsd = gk_request['NSD']

    # add nsd fields
    service['sonata_srv_id'] = nsr['id']
    service['name'] = nsd['name']
    service['description'] = nsd['description']
    service['host_id'] = message_from_ia['instanceVimUuid']
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
    for vnfr in vnfrs:

        function = {}

        vnfd = get_vnfd_by_id(gk_request, vnfr['descriptor_reference'])

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