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
    
