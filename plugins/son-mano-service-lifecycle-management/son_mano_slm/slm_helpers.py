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
        if 'monitoring_parameters' in vnfd.keys():
            for mp in vnfd['monitoring_parameters']:
                if monitoring_parameter_name in mp['name']:
                    return mp
        return None

    def get_threshold(condition):
        if '>' in condition:
            return condition.split('>',1)[-1].strip()
        elif '<' in condition:
            return condition.split('<',1)[-1].strip()

        return None


    message = {}
    service = {}

    nsd = gk_request['NSD']

    # add nsd fields
    service['sonata_srv_id'] = nsd['id']
    service['name'] = nsd['name']
    service['description'] = nsd['description']
    # TODO add host_id, pop_id and sonata_usr_id
    service['host_id'] = ""
    service['pop_id'] = ""
    service['sonata_usr_id'] = ""
    message['service'] = service
    message['functions'] = []
    message['rules'] = []

    # add vnf information
    for key in gk_request.keys():
        if key[:4] == 'VNFD':
            vnfd = key
            function = {}
            function['sonata_func_id'] = vnfd['id']
            function['name'] = vnfd['name']
            function['description'] = vnfd['description']

            # we should create one function per virtual deployment unit
            for vdu in vnfd['virtual_deployment_units']:

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

                    metric['threshold'] = 1.0 # TODO real threshold
                    if 'frequency' in mp.keys():
                        metric['interval'] = mp['frequency']
                    if 'command' in mp.keys():
                        metric['cmd'] = mp['command']

                    func['metrics'].append(metric)

                ## add host_id, retrieved from vnfr['vdu']['vnfc_instance]['host_id']
                vnfr_vdu = get_matching_vdu(vnfrs, vnfd, vdu)
                if vnfr_vdu is not None:
                    func['host_id'] = []
                    for vnfc in vnfr_vdu['vnfc_instance']:
                       func['host_id'].append(vnfc['vim_id'])

                message['functions'].append(func)

            # look for monitoring_rules of this vnfd and add them as "rules"
            for mr in vnfd['monitoring_rules']:
                rule = {}
                rule['name'] = mr['name']
                rule['duration'] = str(mr['duration']) + mr['duration_unit']
                rule['description'] = mr['description']

                rule['condition'] = mr['condition'] # TODO modify uuid

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