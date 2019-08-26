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

import requests
import uuid
import yaml
import json
import base64


def convert_corr_id(corr_id):
    """
    This method converts the correlation id into an integer that is
    small enough to be used with a modulo operation.

    :param corr_id: The correlation id as a String
    """

    # Select the final 4 digits of the string
    reduced_string = corr_id[-4:]
    reduced_int = int(reduced_string, 16)
    return reduced_int


def servid_from_corrid(ledger, corr_id):
    """
    This method returns the service uuid based on a correlation id.
    It is used for responses from different modules that use the
    correlation id as reference instead of the service id.

    :param serv_dict: The ledger of services
    :param corr_id: The correlation id
    """

    for serv_id in ledger.keys():
        if 'act_corr_id' in ledger[serv_id].keys():
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


def replace_old_corr_id_by_new(dictionary, old_correlation_id):
    """
    This method takes a dictionary with uuid's as keys. The method replaces a
    certain key with a new uuid.
    """

    new_correlation_id = uuid.uuid4().hex
    dictionary[new_correlation_id] = dictionary[old_correlation_id]
    dictionary.pop(old_correlation_id, None)

    return new_correlation_id, dictionary


def build_nsr(request_status, nsd, vnfr_ids, serv_id, vls, flavour=None, sid=None, pid=None):
    """
    This method builds the whole NSR from the payload (stripped nsr and vnfrs)
    returned by the Infrastructure Adaptor (IA).
    """

    nsr = {}
    # nsr mandatory fields
    nsr['descriptor_version'] = 'nsr-schema-01'
    nsr['id'] = serv_id
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
            vlink['descriptor_reference'] = virtual_link['id']
            vlink['connectivity_type'] = virtual_link['connectivity_type']
            cpr = virtual_link['connection_points_reference']
            vlink['connection_points_reference'] = cpr
            if virtual_link['id'] in vls.keys():
                vl_map = vls[virtual_link['id']]
                vlink['id'] = vl_map['id']
                if 'vim_id' in vl_map.keys():
                    vlink['vim_id'] = vl_map['vim_id']
                if 'wim_id' in vl_map.keys():
                    vlink['wim_id'] = vl_map['wim_id']
                    for pair in vl_map['pairs']:
                        if 'paths' not in vlink.keys():
                            vlink['paths'] = []
                        node1 = {'ref': pair['refs'][0],
                                 'location': pair['nodes'][0],
                                 'nap': pair['naps'][0]}
                        node2 = {'ref': pair['refs'][1], 
                                 'location': pair['nodes'][1],
                                 'nap': pair['naps'][1]}
                        vlink['paths'].append({'nodes': [node1, node2]})

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

    # sla and policy
    if sid:
        nsr['sla_id'] = sid
    if pid:
        nsr['policy_id'] = pid

    if flavour:
        nsr['flavour'] = flavour

    return nsr


def client_register(url, module_id, password):
    """
    This method registers the SLM as a micro-service with the GK
    """

    reg_form = {}
    reg_form["clientId"] = module_id
    reg_form["secret"] = password
    reg_form["redirectUris"] = ["/auth/catalogue"]

    response = requests.post(url, data=json.dumps(reg_form), verify=False)
    return response.text


def client_login(url, module_id, password):
    """
    This method gets a token for a registered user
    """
    login_string = module_id + ':' + password
    cred = bytes(login_string, 'utf-8')
    encoded_cred = base64.b64encode(cred).decode("utf-8")
    header = {"Authorization": "Basic %s" % encoded_cred}

    response = requests.get(url,
                            headers=header,
                            verify=False)

    resp_dict = json.loads(response.text)

    if 'access_token' in resp_dict.keys():
        return resp_dict['access_token']
    else:
        return None


def get_sm_from_descriptor(descr):
    """
    This method returns a list of specific managers based on
    a received desriptor
    """

    sm_dict = {}

    if 'service_specific_managers' in descr:
        sm_dict = {}
        for ssm in descr['service_specific_managers']:
            for option in ssm['options']:
                if option['key'] == 'type':
                    sm_dict[option['value']] = {}
                    sm_dict[option['value']]['id'] = ssm['id']
                    sm_dict[option['value']]['image'] = ssm['image']

    if 'function_specific_managers' in descr:
        sm_dict = {}
        for fsm in descr['function_specific_managers']:
            for option in fsm['options']:
                if option['key'] == 'type':
                    sm_dict[option['value']] = {}
                    sm_dict[option['value']]['id'] = fsm['id']
                    sm_dict[option['value']]['image'] = fsm['image']

    return sm_dict


def get_ordered_vim_list(payload, which_graph=0):
    """
    This method returns a list of vims. The list is ordered in such
    a way that any VIM is never addressed after the next one in the list
    """

    def find_vim_based_on_vnf_id(vnf_id):
        for vnf in payload['nsd']['network_functions']:
            if vnf['vnf_id'] == vnf_id:
                for func in payload['function']:
                    if vnf['vnf_version'] == func['vnfd']['version']:
                        if vnf['vnf_vendor'] == func['vnfd']['vendor']:
                            if vnf['vnf_name'] == func['vnfd']['name']:
                                return func['vim_uuid']

        return None

    nodes = {}

    nsd = payload['nsd']
    vim_list = []

    if 'forwarding_graphs' in nsd.keys():
        forw_graph = nsd['forwarding_graphs'][which_graph]
        paths = forw_graph['network_forwarding_paths']

        for path in paths:
            cps = path["connection_points"]
            incoming = None
            for cp in cps:
                cp_ref = cp['connection_point_ref']
                if ':' not in cp_ref:
                    pass
                else:
                    vnf_id = cp_ref.split(':')[0]
                    vim_uuid = find_vim_based_on_vnf_id(vnf_id)
                    if vim_uuid not in nodes.keys():
                        nodes[vim_uuid] = {"incoming": [],
                                           "outgoing": []}

                    if incoming is not None:
                        if vim_uuid != incoming:
                            nodes[vim_uuid]["incoming"].append(incoming)
                            nodes[incoming]["outgoing"].append(vim_uuid)

                    incoming = vim_uuid

        number_of_vnfs = len(payload['function'])
        while_counter = 0

        while (len(nodes.keys()) > 0):
            # Exit if loop is infinite
            if while_counter > number_of_vnfs:
                vim_list = None
                break
            for vim_uuid in nodes.keys():
                if len(nodes[vim_uuid]['incoming']) == 0:
                    vim_list.append(vim_uuid)
                    outgoing_list = nodes[vim_uuid]['outgoing']
                    for outg_vim in outgoing_list:
                        nodes[outg_vim]["incoming"].remove(vim_uuid)
            # remove vims with no incoming links
            for vim in vim_list:
                if vim in nodes.keys():
                    del nodes[vim]

            while_counter = while_counter + 1

    else:
        # If no forwarding grapgh is present, the order is irrelevant
        for func in payload['function']:
            if func['vim_uuid'] not in vim_list:
                vim_list.append(func['vim_uuid'])

    return vim_list


def getRestData(base, path, expected_code=200, header=None, token=None):
    """
    This method can be used to retrieve data through a rest api.
    """

    url = base + path
    header = header
    if token is not None:
        header["Authorization"] = "Bearer %s" % token

    counter = 0
    while True:
        try:
            get_response = requests.get(url,
                                        headers=header,
                                        timeout=20.0)

            content = yaml.load(get_response.content)
            code = get_response.status_code

            if (code == expected_code):
                response = {'error': None, "content": content}
                break
            else:
                response = {'error': code, "content": content}
                break
        except:
            counter = counter + 1
            print("GET request timed out")
            if counter == 3:
                response = {'error': '400', 'content': 'request timed out'}
                break
              
    return response


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
    # Building the vnfr makes it the first version of this vnfr.
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
        vdu['id'] = ia_vdu['id'].split("-")[0]
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


def build_monitoring_message(service, functions, userdata):
    """
    This method builds the message for the Monitoring Manager.
    """

    nsd = service['nsd']
    nsr = service['nsr']

    def get_associated_rule(vnfd, monitoring_parameter_name):
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
    service['host_id'] = None
    service['pop_id'] = None

    customer_data = {}
    customer_data['email'] = userdata['customer'].get('email')
    customer_data['phone'] = userdata['customer'].get('phone')

    developer_data = {}
    developer_data['email'] = userdata['developer'].get('email')
    developer_data['phone'] = userdata['developer'].get('phone')

    service['sonata_usr'] = customer_data

    # TODO: data on the developer should be added if customer allows developer
    # to receive monitoring data
#    service['sonata_dev'] = developer_data

    message['service'] = service
    message['functions'] = []
    message['rules'] = []

    # add vnf information
    for vnf in functions:

        vnfr = vnf['vnfr']
        vnfd = vnf['vnfd']

        dus = []
        if 'cloudnative_deployment_units' in vnfr:
            dus = vnfr['cloudnative_deployment_units']
        if 'virtual_deployment_units' in vnfr:
            dus = vnfr['virtual_deployment_units']

        for du in dus:
            du_d = {}
            if 'cloudnative_deployment_units' in vnfr:
                for cdu_d in vnfd['cloudnative_deployment_units']:
                    if du['id'].split(':')[0] == cdu_d['id'][:-37]:
                        du_d = cdu_d
                        break
            if 'virtual_deployment_units' in vnfr:
                for vdu_d in vnfd['virtual_deployment_units']:
                    if du['id'].split(':')[0] == vdu_d['id'][:-37]:
                        du_d = vdu_d
                        break

            function = {}
            function['sonata_func_id'] = vnfr['id']
            function['name'] = vnfd['name']
            function['description'] = vnfd['description']
            function['pop_id'] = vnf['vim_uuid']

            if 'cloudnative_deployment_units' in vnfr:
                function['cnt_name'] = [du['id'] + '-' + vnfr['id']]

            if 'virtual_deployment_units' in vnfr:
                function['host_id'] = du['vnfc_instance'][0]['vc_id']

            function['metrics'] = []

            if 'monitoring_parameters' in du_d:

                for mp in du_d['monitoring_parameters']:
                    metric = {}
                    metric['name'] = mp['name']
                    metric['unit'] = mp['unit']

                    associated_rule = get_associated_rule(vnfd, mp['name'])
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

                        function['metrics'].append(metric)

            if 'snmp_parameters' in du_d:
                function['snmp'] = {}
                function['snmp'] = du_d['snmp_parameters']
                function['snmp']['password'] = "supercalifrajilistico"
                function['snmp']['entity_id'] = du['vnfc_instance'][0]['vc_id']

                mgmt_ip = ''
                for cp in du['vnfc_instance'][0]['connection_points']:
                    if cp['id'] == 'mgmt':
                        mgmt_ip = cp['interface']['address']
                function['snmp']['ip'] = mgmt_ip

            message['functions'].append(function)

        if 'monitoring_rules' in vnfd.keys():

            # variable used to map the received notification_type to the
            # integers expected by the monitoring repo
            notification_type = {}
            notification_type['sms'] = 1
            notification_type['rabbitmq_message'] = 2
            notification_type['email'] = 3

            for mr in vnfd['monitoring_rules']:
                vdu_id = mr['condition'].split(":")[0]
                for vnfc in vdu_hostid:
                    if vnfc[vdu_id] is not None:
                        host_id = vnfc[vdu_id]

                        rule = {}
                        rule['name'] = mr['name']
                        rule['summary'] = ''
                        duration = str(mr['duration']) + mr['duration_unit']
                        rule['duration'] = duration

                        if 'description' in mr.keys():
                            rule['description'] = mr['description']
                        else:
                            rule['description'] = ""

                        condition = mr['condition'].split(":")[1]
                        rule['condition'] = host_id + ":" + condition

                        # we add a rule for each notification type
                        for notification in mr['notification']:
                            r = rule
                            nt = notification_type[notification['type']]
                            r['notification_type'] = nt
                            # add rule to message
                            message['rules'].append(r)

    return message

def append_networkid_to_cp(vnfd, vls):
    """
    This method adds network ids to the connection points in the vnfd
    """

    dus = []
    if 'virtual_deployment_units' in vnfd.keys():
        dus = vnfd['virtual_deployment_units']
    if 'cloudnative_deployment_units' in vnfd.keys():
        dus = vnfd['cloudnative_deployment_units']

    for du in dus:
        if 'connection_points' not in du.keys():
            continue
        for cp in du['connection_points']:
            for vl in vnfd['virtual_links']:
                refs = vl['connection_points_reference']
                if du['id'][:-37] + ':' + cp['id'] in refs:
                    vl_id = vl['id']
                    break
            cp['network_id'] = vls[vl_id]['id']
            cp['fip'] = vls[vl_id]['fip']

    return vnfd

def vnfd_vl_maps_on_nsd_vl(nsd, vnfd, vl):
    """
    This method returns whether a vnfd vl maps on an nsd vl
    """

    name = vnfd['name']
    version = vnfd['version']
    vendor = vnfd['vendor']

    res_cp = None

    for cp in vl['connection_points_reference']:
        if ':' not in cp:
            res_cp = cp
            break

    if res_cp is None:
        return False, None

    vnf_id = None
    for vnf in nsd['network_functions']:
        if vnf['vnf_name'] == name and vnf['vnf_vendor'] == vendor and \
           vnf['vnf_version'] == version:
           vnf_id = vnf['vnf_id']

    if vnf_id is None:
        return False, None

    for nsd_vl in nsd['virtual_links']:
        if vnf_id + ':' + res_cp in nsd_vl['connection_points_reference']:
            return True, nsd_vl['id']

    return False, None


def map_refs_on_du_cps(refs, nsd, vnfs, mapping, vnf_id=None):
    """
    This method returns a list of du cps, that map on the cp references in the
    refs input.
    """
    cps = []
    for ref in refs:
        if ':' in ref:
            vnf_ref, cp_ref = ref.split(':')
            for vnf_nsd in nsd['network_functions']:
                if vnf_nsd['vnf_id'] == vnf_ref:
                    for vnf in vnfs:
                        if not vnf_id or vnf['id'] == vnf_id: 
                            vnfd = vnf['vnfd']
                            if vnf_nsd['vnf_name'] == vnfd['name'] and \
                               vnf_nsd['vnf_version'] == vnfd['version'] and \
                               vnf_nsd['vnf_vendor'] == vnfd['vendor']:
                                du_cp_list = map_vnf_cp_on_du_cps(cp_ref, vnfd)
                                for du_cp in du_cp_list:
                                    du_cp['vnf_id'] = vnf['id']
                                    du_cp['vim_id'] = mapping[vnf['id']]['vim_id']
                                cps.extend(du_cp_list)
                    break
    return cps

def find_du_based_on_ip(ip, functions):
    """
    This method finds a du id associated to an ip
    """

    for vnf in functions:
        if 'vnfr' not in vnf.keys():
            continue
        vnfr = vnf['vnfr']
        dus = []
        if 'virtual_deployment_units' in vnfr.keys():
            dus = vnfr['virtual_deployment_units']
        if 'couldnative_deployment_units' in vnfr.keys():
            dus = vnfr['cloudnative_deployment_units']
        for du in dus:
            du_string = str(du)
            if ip in du_string:
                return du['id'], vnf['id']

    return None, None


def find_ip_from_ref(ref, nsd, vnfs, mapping, vnf_id=None):
    """
    find ip associated to a ref
    """
    cp = map_refs_on_du_cps([ref], nsd, vnfs, mapping, vnf_id)[0]

    for vnf in vnfs:
        if vnf['id'] == cp['vnf_id']:
            if 'virtual_deployment_units' in vnf['vnfr'].keys():
                vdus = vnf['vnfr']['virtual_deployment_units']
                for vdu in vdus:
                    if vdu['id'] == cp['du_id']:
                        vnfc = vdu['vnfc_instance'][0]
                        for cp_loc in vnfc['connection_points']:
                            if cp_loc['id'] == cp['cp_id']:
                                return cp_loc['interface']['address']
            if 'cloudnative_deployment_units' in vnf['vnfr'].keys():
                vdus = vnf['vnfr']['cloudnative_deployment_units']
                for vdu in vdus:
                    if vdu['id'] == cp['du_id']:
                        return cp_loc['load_balancer_ip']['floating_ip']

    return None

def map_vnf_cp_on_du_cps(cp_ref, vnfd):
    """
    This method returns a map from a vnf cp onto the du connection points.
    The return content is a list of dictionaries. Each entry has three keys:
    the id of the du, the id of the cp and a pointer towards the cp section.
    """
    du_cps = []
    for vl in vnfd['virtual_links']:
        if cp_ref in vl['connection_points_reference']:
            for du_cp_ref in vl['connection_points_reference']:
                if du_cp_ref != cp_ref:
                    du_cps.extend(get_du_cp_from_ref(du_cp_ref, vnfd))
            break
    return du_cps

def get_du_cp_from_ref(du_cp_ref, vnfd):
    du_cps = []
    du_id, cp_id = du_cp_ref.split(':')
    du_cps.append({'du_id': du_id, 'cp_id': cp_id})
    if 'virtual_deployment_units' in vnfd.keys():
        for du in vnfd['virtual_deployment_units']:
            if du['id'].split('-')[0] == du_id:
                for cp in du['connection_points']:
                    if cp['id'] == cp_id:
                        du_cps[-1]['ptr'] = cp
    if 'cloudnative_deployment_units' in vnfd.keys():
        for du in vnfd['cloudnative_deployment_units']:
            if du['id'].split('-')[0] == du_id:
                for cp in du['connection_points']:
                    if cp['id'] == cp_id:
                        du_cps[-1]['ptr'] = cp
    return du_cps


def add_network_to_cp(net_id, cp_interfaces, fip=False):
    """
    This method adds the network id to the du cps in the vnfds, and potentially
    also the neccesity for a floating ip.
    """
    for cp in cp_interfaces:
        cp['ptr']['network_id'] = net_id
        if fip:
            cp['ptr']['fip'] = true

