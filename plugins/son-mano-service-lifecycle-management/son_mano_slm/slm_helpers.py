import requests
import uuid
import yaml

def build_message_for_IA(request_dictionary):
    """
    This method converts the deploy request from the gk to a messsaga for the IA
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
    This method builds a resource request message based on the needed resources.
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

    return {'vim_uuid' : vim, 'cpu':needed_cpu, 'memory':needed_memory, 'storage':needed_storage, 'memory_unit':memory_unit, 'storage_unit':storage_unit}

def replace_old_corr_id_by_new(dictionary, old_correlation_id):
    """
    This method takes a dictionary with uuid's as keys. The method replaces a certain key with a new uuid.
    """

    new_correlation_id = uuid.uuid4().hex    
    dictionary[new_correlation_id] = dictionary[old_correlation_id]
    dictionary.pop(old_correlation_id, None)

    return new_correlation_id, dictionary
    

def build_nsr(gk_request, ia_nsr):
    """
    This method builds the whole NSR from the stripped NSR returned by the Infrastructure Adaptor (IA)
    """

    nsr = {}
    ## nsr mandatory fields
    nsr['descriptor_version'] = 'nsr-schema-01'
    nsr['id'] = ia_nsr['nsr']['uuid']
    nsr['status'] = ia_nsr['nsr']['status']
    # same version as NSD for consistency, so we can relate each other
    nsr['version'] = gk_request['NSD']['version']
    nsr['descriptor_reference'] = gk_request['NSD']['id']

    ## network functions
    if 'vnfrs' in ia_nsr.keys():
        nsr['network_functions'] = []
        for network_function in ia_nsr['vnfrs']:
            function = {}
            function['vnfr_id'] = network_function['uuid']
            nsr['network_functions'].append(function)

    ## connection points
    if 'connection_points' in gk_request['NSD']:
        nsr['connection_points'] = []
        for connection_point in gk_request['NSD']['connection_points']:
            cp = {}
            cp['id'] = connection_point['id']
            cp['type'] = connection_point['type']
            nsr['connection_points'].append(cp)

    ## virtual links
    if 'virtual_links' in gk_request['NSD']:
        nsr['virtual_links'] = []
        for virtual_link in gk_request['NSD']['virtual_links']:
            vlink = {}
            vlink['id'] = virtual_link['id']
            vlink['connection_type'] = virtual_link['connectivity_type']
            vlink['connection_points_reference'] = virtual_link['connection_points_reference']
            nsr['virtual_links'].append(vlink)

    ## forwarding graphs
    if 'forwarding_graphs' in gk_request['NSD']:
        nsr['forwarding_graphs'] = []
        for forwarding_graph in gk_request['NSD']['forwarding_graphs']:
            nsr['forwarding_graphs'].append(forwarding_graph)

    ## lifecycle events
    if 'lifecycle_events' in gk_request['NSD']:
        nsr['lifecycle_events'] = []
        for lifecycle_event in gk_request['NSD']['lifecycle_events']:
            nsr['lifecycle_events'].append(lifecycle_event)

    ## vnf_dependency
    if 'vnf_dependency' in gk_request['NSD']:
        nsr['vnf_dependency'] = []
        for vd in gk_request['NSD']['vnf_dependency']:
            nsr['vnf_dependency'].append(vd)

    ## services_dependency
    if 'services_dependency' in gk_request['NSD']:
        nsr['services_dependency'] = []
        for sd in gk_request['NSD']['services_dependency']:
            nsr['services_dependency'].append(sd)

    ## monitoring_parameters
    if 'monitoring_parameters' in gk_request['NSD']:
        nsr['monitoring_parameters'] = []
        for mp in gk_request['NSD']['monitoring_parameters']:
            nsr['monitoring_parameters'].append(mp)

    ## auto_scale_policy
    if 'auto_scale_policy' in gk_request['NSD']:
        nsr['auto_scale_policy'] = []
        for asp in gk_request['NSD']['auto_scale_policy']:
            nsr['monitoring_parameters'].append(asp)

    return nsr


def build_monitoring_message(gk_request, nsr, vnfrs):

    # This method searches inside the VNFRs for the VDU that makes reference to a specific VDU of a VNFD.
    def get_matching_vdu(vnfrs, vnfd, vdu):
        for vnfr in vnfrs:
            if vnfr['descriptor_reference'] == vnfd['id']:
                for nsr_vdu in vnfr['virtual_deployment_units']:
                    if nsr_vdu['id'] == vdu['id']:
                        return nsr_vdu

        return None


    def get_associated_monitoring_rule(vnfd, monitoring_parameter_name):
        if 'monitoring_rules' in vnfd.keys():
            for mp in vnfd['monitoring_rules']:
                if monitoring_parameter_name in mp['condition']:
                    return mp
        return None

    def get_threshold(condition):
        if '>' in condition:
            return condition.split('>',1)[-1].strip()
        elif '<' in condition:
            return condition.split('<',1)[-1].strip()

        return None

    # TODO it assumes there's only one vnfc_instance per vdu, so it takes the first element nof the list
    def get_host_id(vdu):
        if vdu is not None and 'vnfc_instance' in vdu.keys():
            return vnfr_vdu['vnfc_instance'][0]['vc_id']
        return None

    message = {}
    service = {}

    nsd = gk_request['NSD']

    # add nsd fields
    service['sonata_srv_id'] = nsd['id']
    service['name'] = nsd['name']
    service['description'] = nsd['description']
    # TODO add host_id, pop_id and sonata_usr_id
    service['host_id'] = None
    service['pop_id'] = None
    service['sonata_usr_id'] = None
    message['service'] = service

    message['functions'] = []
    message['rules'] = []

    # this dictionary will store the relationshop beween the vdu['id'] and the host_id, to be later used
    # when building the metrics part of the message.
    vdu_hostid = {}

    # add vnf information
    for key in gk_request.keys():
        if key[:4] == 'VNFD':
            vnfd = gk_request[key]
            function = {}

            function['sonata_func_id'] = vnfd['id']
            function['name'] = vnfd['name']
            function['description'] = vnfd['description']
            function['pop_id'] = ""

            # we should create one function per virtual deployment unit
            for vdu in vnfd['virtual_deployment_units']:

                if ('monitoring_parameters' in vdu.keys()):
                    func = function
                    func['metrics'] = []
                    # add monitoring_parameter as metric
                    for mp in vdu['monitoring_parameters']:
                        metric = {}
                        metric['name'] = mp['name']
                        metric['unit'] = mp['unit']

                        # extract threshold from the associated monitoring rule. It's defined in the ['condition'] key.
                        # example: if monitoring_rule['condition] is "vdu01:vm_cpu_perc > 10", the threshold is 10.
                        associated_rule = get_associated_monitoring_rule(vnfd, mp['name'])
                        if (associated_rule is not None):
                            threshold = get_threshold(associated_rule['condition'])
                            if threshold is not None:
                                metric['threshold'] = threshold

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

                    ## add host_id, retrieved from vnfr['vdu']['vnfc_instance]['vc_id']
                    vnfr_vdu = get_matching_vdu(vnfrs, vnfd, vdu)
                    func['host_id'] = get_host_id(vnfr_vdu)
                    vdu_hostid[vnfr_vdu['id']] = func['host_id']
                    message['functions'].append(func)

            # look for monitoring_rules of this vnfd and add them as "rules"
            if 'monitoring_rules' in vnfd.keys():
                for mr in vnfd['monitoring_rules']:
                    rule = {}
                    rule['name'] = mr['name']
                    rule['duration'] = str(mr['duration']) + mr['duration_unit']
                    rule['summary'] = ""

                    if 'description' in mr.keys():
                        rule['description'] = mr['description']
                    else:
                        rule['description'] = ""

                    vdu_id = mr['condition'].split(":")[0]
                    host_id = vdu_hostid[vdu_id]
                    rule['condition'] = host_id + ":" + mr['condition'].split(":")[1]

                    # variable used to map the received notification_type to the integers expected by the monitoring repo
                    notification_type_mapping = {}
                    notification_type_mapping['sms'] = 1
                    notification_type_mapping['rabbitmq_message'] = 2
                    notification_type_mapping['email'] = 3

                    # we add a rule for each notification type
                    for notification in mr['notification']:
                        r = rule
                        r['notification_type'] = notification_type_mapping[notification['type']]
                        ## add rule to message
                        message['rules'].append(r)


    return message