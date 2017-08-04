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
This contains helper functions for `flm.py`.
"""

import requests
import uuid
import yaml


def funcid_from_corrid(ledger, corr_id):
    """
    This method returns the function uuid based on a correlation id.
    It is used for responses from different modules that use the
    correlation id as reference instead of the function id.

    :param serv_dict: The ledger of functions
    :param corr_id: The correlation id
    """

    for func_id in ledger.keys():
        if isinstance(ledger[func_id]['act_corr_id'], list):
            if str(corr_id) in ledger[func_id]['act_corr_id']:
                break
        else:
            if ledger[func_id]['act_corr_id'] == str(corr_id):
                break

    return func_id


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


def get_fsm_from_vnfd(vnfd):

    if 'function_specific_managers' in vnfd:
        fsm_dict = {}
        for fsm in vnfd['function_specific_managers']:
            for option in fsm['options']:
                if option['key'] == 'type':
                    fsm_dict[option['value']] = {}
                    fsm_dict[option['value']]['id'] = fsm['id']
                    fsm_dict[option['value']]['image'] = fsm['image']

    else:
        return {}

    return fsm_dict


def getRestData(base, path, expected_code=200):
    """
    This method can be used to retrieve data through a rest api.
    """

    url = base + path
    try:
        get_response = requests.get(url, timeout=1.0)
        content = get_response.json()
        code = get_response.status_code

        if (code == expected_code):
            print("GET for " + str(path) + " succeeded: " + str(content))
            return {'error': None, "content": content}
        else:
            print("GET returned with status_code: " + str(code))
            return{'error': code, "content": content}
    except:
        print("GET request timed out")
        return{'error': '400', 'content': 'request timed out'}


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

    return vnfr


def get_vnfd_vdu_by_reference(vnfd, vdu_reference):
    # TODO can we do it with functional programming?
    if 'virtual_deployment_units' in vnfd:
        for vnfd_vdu in vnfd['virtual_deployment_units']:
            if vnfd_vdu['id'] in vdu_reference:
                return vnfd_vdu
    return None
