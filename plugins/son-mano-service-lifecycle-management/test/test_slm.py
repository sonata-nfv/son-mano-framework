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

import unittest
import time
import json
import yaml
import threading
import logging
import uuid
import son_mano_slm.slm_helpers as tools

from unittest import mock
from multiprocessing import Process
from son_mano_slm.slm import ServiceLifecycleManager
from sonmanobase.messaging import ManoBrokerRequestResponseConnection
from collections import namedtuple

logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:slm_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)


class testSlmRegistrationAndHeartbeat(unittest.TestCase):
    """
    Tests the registration process of the SLM to the broker
    and the plugin manager, and the heartbeat process.
    """

    def setUp(self):
        #a new SLM in another process for each test
        self.slm_proc = Process(target=ServiceLifecycleManager)
        self.slm_proc.daemon = True
        #make a new connection with the broker before each test
        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')

        #Some threading events that can be used during the tests
        self.wait_for_event = threading.Event()
        self.wait_for_event.clear()

        #The uuid that can be assigned to the plugin
        self.uuid = '1'

    def tearDown(self):
        #Killing the slm
        if self.slm_proc is not None:
            self.slm_proc.terminate()
        del self.slm_proc

        #Killing the connection with the broker
        self.manoconn.stop_connection()
        self.manoconn.stop_threads()
        del self.manoconn

        #Clearing the threading helpers
        del self.wait_for_event

    #Method that terminates the timer that waits for an event
    def eventFinished(self):
        self.wait_for_event.set()

    #Method that starts a timer, waiting for an event
    def waitForEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def testSlmHeartbeat(self):
        """
        TEST: This test verifies whether the SLM sends out a heartbeat
        as intended, once it is registered and whether this heartbeat
        message is correctly formatted.
        """

        def on_registration_trigger(ch, method, properties, message):
            """
            When the registration request from the plugin is received,
            this method replies as if it were the plugin manager
            """
            self.eventFinished()
            return json.dumps({'status': 'OK', 'uuid': self.uuid})

        def on_heartbeat_receive(ch, method, properties, message):
            """
            When the heartbeat message is received, this
            method checks if it is formatted correctly
            """
            msg = json.loads(str(message))
            #CHECK: The message should be a dictionary.
            self.assertTrue(isinstance(msg, dict), msg="Message is not a dictionary.")
            #CHECK: The dictionary should have a key 'uuid'.
            self.assertTrue("uuid" in msg.keys(), msg="uuid is not a key.")
            #CHECK: The value of 'uuid' should be a string.
            self.assertTrue(isinstance(msg["uuid"], str), msg="uuid is not a string.")
            #CHECK: The uuid in the message should be the same as the assigned uuid.
            self.assertEqual(self.uuid, msg["uuid"], msg="uuid not correct.")
            #CHECK: The dictionary should have a key 'state'.
            self.assertTrue("state" in msg.keys(), msg="state is not a key.")
            #CHECK: The value of 'state' should be a 'READY', 'RUNNING', 'PAUSED' or 'FAILED'.
            self.assertTrue(msg["state"] in ["READY", "RUNNING", "PAUSED", "FAILED"], msg="Not a valid state.")

            #Stop the wait
            self.eventFinished()

        #STEP1: subscribe to the correct topics
        self.manoconn.register_async_endpoint(on_registration_trigger, 'platform.management.plugin.register')
        self.manoconn.subscribe(on_heartbeat_receive, 'platform.management.plugin.' + self.uuid + '.heartbeat')

        #STEP2: Start the SLM
        self.slm_proc.start()

        #STEP3: Wait until the registration request has been answered
        self.waitForEvent(msg="No registration request received")

        self.wait_for_event.clear()

        #STEP4: Wait until the heartbeat message is received.

    def testSlmRegistration(self):
        """
        TEST: This test verifies whether the SLM is sending out a message,
        and whether it contains all the needed info on the
        platform.management.plugin.register topic to register to the plugin
        manager.
        """

        #STEP3a: When receiving the message, we need to check whether all fields present. TODO: check properties
        def on_register_receive(ch, method, properties, message):

            msg = json.loads(str(message))
            #CHECK: The message should be a dictionary.
            self.assertTrue(isinstance(msg, dict), msg='message is not a dictionary')
            #CHECK: The dictionary should have a key 'name'.
            self.assertIn('name', msg.keys(), msg='No name provided in message.')
            if isinstance(msg['name'], str):
                #CHECK: The value of 'name' should not be an empty string.
                self.assertTrue(len(msg['name']) > 0, msg='empty name provided.')
            else:
                #CHECK: The value of 'name' should be a string
                self.assertEqual(True, False, msg='name is not a string')
            #CHECK: The dictionary should have a key 'version'.
            self.assertIn('version', msg.keys(), msg='No version provided in message.')
            if isinstance(msg['version'], str):
                #CHECK: The value of 'version' should not be an empty string.
                self.assertTrue(len(msg['version']) > 0, msg='empty version provided.')
            else:
                #CHECK: The value of 'version' should be a string
                self.assertEqual(True, False, msg='version is not a string')
            #CHECK: The dictionary should have a key 'description'
            self.assertIn('description', msg.keys(), msg='No description provided in message.')
            if isinstance(msg['description'], str):
                #CHECK: The value of 'description' should not be an empty string.
                self.assertTrue(len(msg['description']) > 0, msg='empty description provided.')
            else:
                #CHECK: The value of 'description' should be a string
                self.assertEqual(True, False, msg='description is not a string')

            # stop waiting
            self.eventFinished()

        #STEP1: Listen to the platform.management.plugin.register topic
        self.manoconn.subscribe(on_register_receive, 'platform.management.plugin.register')

        #STEP2: Start the SLM
        self.slm_proc.start()

        #STEP3b: When not receiving the message, the test failed 
        self.waitForEvent(timeout=5, msg="message not received.")

class testSlmFunctionality(unittest.TestCase):
    """
    Tests the tasks that the SLM should perform in the service
    life cycle of the network services.
    """

    slm_proc    = None
    uuid        = '1'
    corr_id     = '1ba347d6-6210-4de7-9ca3-a383e50d0330'

########################
#SETUP
########################
    def setUp(self):
        def on_register_trigger(ch, method, properties, message):
            return json.dumps({'status': 'OK', 'uuid': self.uuid})

        #vnfcounter for when needed
        self.vnfcounter = 0

        #Generate a new corr_id for every test
        self.corr_id = str(uuid.uuid4())

        #a new SLM in another process for each test
        self.slm_proc = ServiceLifecycleManager(auto_register=False, start_running=False)

        #We make a spy connection to listen to the different topics on the broker
        self.manoconn_spy = ManoBrokerRequestResponseConnection('son-plugin.SonSpy')
        #we need a connection to simulate messages from the gatekeeper
        self.manoconn_gk = ManoBrokerRequestResponseConnection('son-plugin.SonGateKeeper')
        #we need a connection to simulate messages from the infrastructure adaptor
        self.manoconn_ia = ManoBrokerRequestResponseConnection('son-plugin.SonInfrastructureAdapter')

        #Some threading events that can be used during the tests
        self.wait_for_first_event = threading.Event()
        self.wait_for_first_event.clear()

        #The uuid that can be assigned to the plugin
        self.uuid = '1'

    def tearDown(self):
        #Killing the slm
        self.slm_proc.manoconn.stop_connection()
        self.slm_proc.manoconn.stop_threads()

        try:
            del self.slm_proc
        except:
            pass

        #Killing the connection with the broker
        self.manoconn_spy.stop_connection()
        self.manoconn_gk.stop_connection()
        self.manoconn_ia.stop_connection()

        self.manoconn_spy.stop_threads()
        self.manoconn_gk.stop_threads()
        self.manoconn_ia.stop_threads()

        del self.manoconn_spy
        del self.manoconn_gk
        del self.manoconn_ia

        del self.wait_for_first_event

########################
#GENERAL
########################
    def createGkNewServiceRequestMessage(self, correctlyFormatted=True):
        """
        This method helps creating messages for the service request packets.
        If it needs to be wrongly formatted, the nsd part of the request is
        removed.
        """

        path_descriptors = '/plugins/son-mano-service-lifecycle-management/test/test_descriptors/'

        nsd_descriptor   = open(path_descriptors + 'sonata-demo.yml', 'r')
        vnfd1_descriptor = open(path_descriptors + 'firewall-vnfd.yml', 'r')
        vnfd2_descriptor = open(path_descriptors + 'iperf-vnfd.yml', 'r')
        vnfd3_descriptor = open(path_descriptors + 'tcpdump-vnfd.yml', 'r')

        #import the nsd and vnfds that form the service
        if correctlyFormatted:
            service_request = {'NSD': yaml.load(nsd_descriptor), 'VNFD1': yaml.load(vnfd1_descriptor), 'VNFD2': yaml.load(vnfd2_descriptor), 'VNFD3': yaml.load(vnfd3_descriptor)}
        else:
            service_request = {'VNFD1': yaml.load(vnfd1_descriptor), 'VNFD2': yaml.load(vnfd2_descriptor), 'VNFD3': yaml.load(vnfd3_descriptor)}

        return yaml.dump(service_request)

    #Method that terminates the timer that waits for an event
    def firstEventFinished(self):
        self.wait_for_first_event.set()

    #Method that starts a timer, waiting for an event
    def waitForFirstEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_first_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def dummy(self, ch, method, properties, message):
        """
        Sometimes, we need a cbf for a async_call, without actually using it.
        """

        return

#############################################################
#TEST1: test validate_deploy_request
#############################################################
    def test_validate_deploy_request(self):
        """
        The method validate_deploy_request is used to check whether the
        received message that requests the deployment of a new service is
        correctly formatted.
        """

        #Setup
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'original_corr_id':corr_id}

        #SUBTEST1: Check a correctly formatted message
        message = self.createGkNewServiceRequestMessage()
        service_dict[service_id]['payload'] =  yaml.load(message)

        self.slm_proc.set_services(service_dict)
        self.slm_proc.validate_deploy_request(service_id)
        result = self.slm_proc.get_services()

        self.assertEqual({'status': result[service_id]['status'],
                          'error': result[service_id]['error']},
                         {'status': 'INSTANTIATING', 'error': None},
                         msg="outcome and expected result not equal SUBTEST1.")

        #SUBTEST2: Check a message that is not a dictionary
        message = "test message"
        service_dict[service_id]['payload'] = message

        self.slm_proc.set_services(service_dict)
        self.slm_proc.validate_deploy_request(service_id)
        result = self.slm_proc.get_services()

        expected_message = "Request " + corr_id + ": payload is not a dict."
        expected_response = {'status': 'ERROR', 'error': expected_message}

        self.assertEqual({'status': result[service_id]['status'],
                          'error': result[service_id]['error']},
                         expected_response,
                         msg="outcome and expected result not equal SUBTEST2.")


        #SUBTEST3: Check a message that contains no NSD
        message = self.createGkNewServiceRequestMessage()
        loaded_message = yaml.load(message)
        del loaded_message['NSD']
        service_dict[service_id]['payload'] = loaded_message

        self.slm_proc.set_services(service_dict)
        self.slm_proc.validate_deploy_request(service_id)
        result = self.slm_proc.get_services()

        expected_message = "Request " + corr_id + ": NSD is not a dict."
        expected_response = {'status': 'ERROR', 'error': expected_message}

        self.assertEqual({'status': result[service_id]['status'],
                          'error': result[service_id]['error']},
                         expected_response,
                         msg="outcome and expected result not equal SUBTEST3.")

        #SUBTEST4: The number of VNFDs must be the same as listed in the NSD
        message = self.createGkNewServiceRequestMessage()
        loaded_message = yaml.load(message)
        loaded_message['NSD']['network_functions'].append({})
        service_dict[service_id]['payload'] = loaded_message

        self.slm_proc.set_services(service_dict)
        self.slm_proc.validate_deploy_request(service_id)
        result = self.slm_proc.get_services()

        expected_message = "Request " + corr_id + ": # of VNFDs doesn't match NSD."
        expected_response = {'status': 'ERROR', 'error': expected_message}

        self.assertEqual({'status': result[service_id]['status'],
                          'error': result[service_id]['error']},
                         expected_response,
                         msg="outcome and expected result not equal SUBTEST4.")

        #SUBTEST5: VNFDs can not be empty
        message = self.createGkNewServiceRequestMessage()
        loaded_message = yaml.load(message)
        loaded_message['VNFD1'] = None
        service_dict[service_id]['payload'] = loaded_message

        self.slm_proc.set_services(service_dict)
        self.slm_proc.validate_deploy_request(service_id)
        result = self.slm_proc.get_services()

        expected_message = "Request " + corr_id + ": empty VNFD."
        expected_response = {'status': 'ERROR', 'error': expected_message}

        self.assertEqual({'status': result[service_id]['status'],
                          'error': result[service_id]['error']},
                         expected_response,
                         msg="outcome and expected result not equal SUBTEST5.")

###########################################################
#TEST2: Test start_next_task
###########################################################
    def test_start_next_task(self):
        """
        This method tests the start_next_task method
        """

        #Setup
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        orig_corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'corr_id':corr_id,
                                    'original_corr_id': orig_corr_id,
                                    'pause_chain': True,
                                    'kill_chain': False}

        #SUBTEST1: Check if next task is correctly called
        message = self.createGkNewServiceRequestMessage()

        #Add a task to the list
        task_list = ['validate_deploy_request']

        #Create the ledger
        service_dict[service_id]['schedule'] = task_list
        service_dict[service_id]['payload'] = yaml.load(message)

        #Run the method
        self.slm_proc.set_services(service_dict)
        self.slm_proc.start_next_task(service_id)

        #wait for the task to finish
        time.sleep(0.1)
        result = self.slm_proc.get_services()

        #Check result
        generated_response = {'status': result[service_id]['status'],
                              'error': result[service_id]['error']}
        expected_response = {'status': 'INSTANTIATING', 'error': None}

        self.assertEqual(generated_response,
                         expected_response,
                         msg="outcome and expected result not equal SUBTEST1.")

        #Setup
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        orig_corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'corr_id':corr_id,
                                    'original_corr_id': orig_corr_id,
                                    'pause_chain': False,
                                    'kill_chain': False}

        #SUBTEST2: Check behavior if there is no next task
        message = self.createGkNewServiceRequestMessage()

        #Add a task to the list
        task_list = []

        #Create the ledger
        service_dict[service_id]['schedule'] = task_list
        service_dict[service_id]['payload'] = yaml.load(message)

        #Run the method
        self.slm_proc.set_services(service_dict)
        self.slm_proc.start_next_task(service_id)

        #wait for the task to finish
        time.sleep(0.1)
        result = self.slm_proc.get_services()

        #Check result: if successful, service_id will not be a key in result

        self.assertFalse(service_id in result.keys(),
                         msg="key is part of ledger in SUBTEST2.")

# ###############################################################
# #TEST3: Test service_instance_create
# ###############################################################
#     def test_service_instance_create(self):
#         """
#         This method tests the service_instance_create method of the SLM
#         """

#         #Setup
#         message = self.createGkNewServiceRequestMessage()
#         corr_id = str(uuid.uuid4())
#         topic = "service.instances.create"
#         prop_dict = {'reply_to': topic, 
#                      'correlation_id': corr_id,
#                      'app_id': "Gatekeeper"}

#         properties = namedtuple('properties', prop_dict.keys())(*prop_dict.values())

#         schedule = self.slm_proc.service_instance_create('foo',
#                                                          'bar',
#                                                          properties,
#                                                          message)

#         #Check result: since we don't know how many of the tasks
#         #were completed by the time we got the result, we only check
#         #the final elements in the tasklist

#         #The last 7 elements from the generated result
#         generated_result = schedule[-7:]

#         #The expected last 7 elements in the list
#         expected_result = ['SLM_mapping', 'ia_prepare', 'vnf_deploy',
#                            'vnf_chain', 'wan_configure',
#                            'instruct_monitoring', 'inform_gk']

#         self.assertEqual(generated_result,
#                          expected_result,
#                          msg='lists are not equal')

###############################################################
#TEST4: Test resp_topo
###############################################################
    def test_resp_topo(self):
        """
        This method tests the resp_topo method.
        """

        #Setup
        #Create topology message
        first = {'vim_uuid':str(uuid.uuid4()), 'memory_used':5, 'memory_total':12, 'core_used':4, 'core_total':6}
        second = {'vim_uuid':str(uuid.uuid4()), 'memory_used':3, 'memory_total':5, 'core_used':4, 'core_total':5}
        third = {'vim_uuid':str(uuid.uuid4()), 'memory_used':6, 'memory_total':7, 'core_used':2, 'core_total':12}
        topology_message = [first, second, third]
        payload = yaml.dump(topology_message)

        #Create ledger
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'act_corr_id':corr_id,
                                    'infrastructure': {'topology':None},
                                    'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'kill_chain': False}

        self.slm_proc.set_services(service_dict)

        #Create properties
        topic = "infrastructure.management.compute.list"
        prop_dict = {'reply_to': topic, 
                     'correlation_id': corr_id,
                     'app_id': 'InfrastructureAdaptor'}

        properties = namedtuple('properties', prop_dict.keys())(*prop_dict.values())

        #Run method
        self.slm_proc.resp_topo('foo', 'bar', properties, payload)

        #Check result
        result = self.slm_proc.get_services()

        self.assertEqual(topology_message,
                         result[service_id]['infrastructure']['topology'],
                         msg="Dictionaries are not equal")

###############################################################
#TEST5: Test resp_vnf_depl
###############################################################
    def test_resp_vnf_depl(self):
        """
        This method tests the resp_vnf_depl method.
        """

        #SUBTEST1: Only one VNFD in the service
        #Setup
        #Create the message
        vnfr = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/expected_vnfr_iperf.yml', 'r'))
        message = {'status': 'DEPLOYED',
                   'error': None,
                   'vnfr': vnfr}

        payload = yaml.dump(message)

        #Create ledger
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'act_corr_id':corr_id,
                                    'function': [{'id': vnfr['id']}],
                                    'vnfs_to_resp': 1,
                                    'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'kill_chain': False}

        self.slm_proc.set_services(service_dict)

        #Create properties
        topic = "mano.function.deploy"
        prop_dict = {'reply_to': topic, 
                     'correlation_id': corr_id,
                     'app_id': 'FunctionLifecycleManager'}

        properties = namedtuple('props', prop_dict.keys())(*prop_dict.values())

        #Run method
        self.slm_proc.resp_vnf_depl('foo', 'bar', properties, payload)

        #Check result
        result = self.slm_proc.get_services()

        self.assertEqual(vnfr,
                         result[service_id]['function'][0]['vnfr'],
                         msg="Dictionaries are not equal SUBTEST 1")

        self.assertEqual(result[service_id]['vnfs_to_resp'],
                         0,
                         msg="Values not equal SUBTEST 1")


        #SUBTEST2: Two VNFDs in the service
        #Setup
        #Create the message
        vnfr = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/expected_vnfr_iperf.yml', 'r'))
        message = {'status': 'DEPLOYED',
                   'error': None,
                   'vnfr': vnfr}

        payload = yaml.dump(message)

        #Create ledger
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'act_corr_id':corr_id,
                                    'function': [{'id': vnfr['id']}],
                                    'vnfs_to_resp': 2,
                                    'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'kill_chain': False}

        self.slm_proc.set_services(service_dict)

        #Create properties
        topic = "mano.function.deploy"
        prop_dict = {'reply_to': topic, 
                     'correlation_id': corr_id,
                     'app_id': 'FunctionLifecycleManager'}

        properties = namedtuple('props', prop_dict.keys())(*prop_dict.values())

        #Run method
        self.slm_proc.resp_vnf_depl('foo', 'bar', properties, payload)

        #Check result
        result = self.slm_proc.get_services()

        self.assertEqual(vnfr,
                         result[service_id]['function'][0]['vnfr'],
                         msg="Dictionaries are not equal SUBTEST 2")

        self.assertEqual(result[service_id]['vnfs_to_resp'],
                         1,
                         msg="Values not equal SUBTEST 2")

        self.assertEqual(result[service_id]['schedule'],
                         ['get_ledger'],
                         msg="Lists not equal SUBTEST 2")

###############################################################
#TEST6: Test resp_prepare
###############################################################
    def test_resp_prepare(self):
        """
        This method tests the resp_prepare method.
        """

        #SUBTEST 1: Successful response message
        #Setup
        #Create the message
        message = {'request_status': 'COMPLETED',
                   'error': None,
                   }

        payload = yaml.dump(message)

        #Create ledger
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'act_corr_id':corr_id,
                                    'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'current_workflow': 'instantiation',
                                    'kill_chain': False}

        self.slm_proc.set_services(service_dict)

        #Create properties
        topic = "infrastructure.service.prepare"
        prop_dict = {'reply_to': topic, 
                     'correlation_id': corr_id,
                     'app_id': 'InfrastructureAdaptor'}

        properties = namedtuple('props', prop_dict.keys())(*prop_dict.values())

        #Run method
        self.slm_proc.resp_prepare('foo', 'bar', properties, payload)

        #Check result
        result = self.slm_proc.get_services()

        self.assertFalse('status' in result[service_id].keys(),
                         msg="Key in dictionary SUBTEST 1")

        self.assertFalse('error' in result[service_id].keys(),
                         msg="Key in dictionary SUBTEST 1")

        # #SUBTEST 2: Failed response message

        # def on_test_resp_prepare_subtest2(ch, mthd, prop, payload):

        #     message = yaml.load(payload)

        #     self.assertEqual(message['status'],
        #                      'ERROR',
        #                      msg="Status not correct in SUBTEST 1")

        #     self.assertEqual(message['error'],
        #                      'BAR',
        #                      msg="Error not correct in SUBTEST 1")

        #     self.assertTrue('timestamp' in message.keys(),
        #                      msg="Timestamp missing in SUBTEST 1")

        #     self.assertEqual(len(message.keys()),
        #                      3,
        #                     msg="Number of keys not correct in SUBTEST1")
        #     self.firstEventFinished()

        # #Setup
        # #Create the message

        # message = {'request_status': 'FOO',
        #            'message': 'BAR',
        #            }

        # payload = yaml.dump(message)

        # #Listen on feedback topic
        # self.manoconn_gk.subscribe(on_test_resp_prepare_subtest2,'service.instances.create')

        # #Create ledger
        # service_dict = {}
        # service_id = str(uuid.uuid4())
        # corr_id = str(uuid.uuid4())
        # service_dict[service_id] = {'act_corr_id':corr_id,
        #                             'schedule': ['get_ledger'],
        #                             'original_corr_id':corr_id,
        #                             'pause_chain': True,
        #                             'current_workflow': 'instantiation',
        #                             'kill_chain': False}

        # self.slm_proc.set_services(service_dict)

        # #Create properties
        # topic = "infrastructure.service.prepare"
        # prop_dict = {'reply_to': topic, 
        #              'correlation_id': corr_id,
        #              'app_id': 'InfrastructureAdaptor'}

        # properties = namedtuple('props', prop_dict.keys())(*prop_dict.values())

        # #Run method
        # self.slm_proc.resp_prepare('foo', 'bar', properties, payload)

        # #Wait for the test to finish
        # self.waitForFirstEvent(timeout=5)


###############################################################
#TEST7: test contact_gk
###############################################################
    def test_contact_gk(self):
        """
        This method tests the contact_gk method.
        """

        #Check result SUBTEST 1
        def on_contact_gk_subtest1(ch, mthd, prop, payload):
            message = yaml.load(payload)

            self.assertEqual(message['status'],
                             'FOO',
                             msg="Status not correct in SUBTEST 1")

            self.assertEqual(message['error'],
                             'BAR',
                             msg="Error not correct in SUBTEST 1")

            self.assertTrue('timestamp' in message.keys(),
                             msg="Timestamp missing in SUBTEST 1")

            self.assertEqual(len(message.keys()),
                             3,
                            msg="Number of keys not correct in SUBTEST1")
            self.firstEventFinished()

        #Check result SUBTEST2
        def on_contact_gk_subtest2(ch, mthd, prop, payload):
            self.firstEventFinished()

            message = yaml.load(payload)

            self.assertEqual(message['status'],
                             'FOO',
                             msg="Status not correct in SUBTEST 2")

            self.assertEqual(message['error'],
                             'BAR',
                             msg="Error not correct in SUBTEST 2")

            self.assertEqual(message['FOO'],
                             'BAR',
                             msg="Error not correct in SUBTEST 2")

            self.assertTrue('timestamp' in message.keys(),
                             msg="Timestamp missing in SUBTEST 2")

            self.assertEqual(len(message.keys()),
                             4,
                            msg="Number of keys not correct in SUBTEST2")

        #SUBTEST1: Without additional content
        #Setup
        #Create the ledger
        self.wait_for_first_event.clear()
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'status': 'FOO',
                                    'error': 'BAR',
                                    'kill_chain': False,
                                    'topic': 'service.instances.create'}

        #Set the ledger
        self.slm_proc.set_services(service_dict)

        #Spy the message bus
        self.manoconn_spy.subscribe(on_contact_gk_subtest1, 'service.instances.create')

        #Wait until subscription is completed
        time.sleep(0.1)

        #Run the method
        self.slm_proc.contact_gk(service_id)

        #Wait for the test to finish
        self.waitForFirstEvent(timeout=5)

        #SUBTEST2: With additional content
        #Setup
        self.wait_for_first_event.clear()
        #Create the ledger
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        add_content = {'FOO': 'BAR'}
        service_dict[service_id] = {'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'status': 'FOO',
                                    'error': 'BAR',
                                    'add_content': add_content,
                                    'topic': 'service.instances.create'}

        self.slm_proc.set_services(service_dict)

        #Spy the message bus
        self.manoconn_gk.subscribe(on_contact_gk_subtest2, 'service.instances.create')

        #Wait until subscription is completed
        time.sleep(0.1)

        #Run the method
        self.slm_proc.contact_gk(service_id)

        #Wait for the test to finish
        self.waitForFirstEvent(timeout=5)

###############################################################
#TEST8: test request_topology
###############################################################
    def test_request_topology(self):
        """
        This method tests the request_topology method.
        """

        #Check result SUBTEST 1
        def on_request_topology_subtest1(ch, mthd, prop, payload):

            self.assertEqual(payload,
                             "{}",
                             msg="Payload is not empty")

            self.firstEventFinished()

        #SUBTEST1: Trigger request_topology
        #Setup
        #Create the ledger
        self.wait_for_first_event.clear()
        service_dict = {}
        service_id = str(uuid.uuid4())
        corr_id = str(uuid.uuid4())
        service_dict[service_id] = {'schedule': ['get_ledger'],
                                    'original_corr_id':corr_id,
                                    'pause_chain': True,
                                    'kill_chain': False,
                                    'status': 'FOO',
                                    'error': 'BAR',
                                    'infrastructure':{}}

        #Set the ledger
        self.slm_proc.set_services(service_dict)

        #Spy the message bus
        self.manoconn_spy.subscribe(on_request_topology_subtest1, 
                                    'infrastructure.management.compute.list')

        #Wait until subscription is completed
        time.sleep(0.1)

        #Run the method
        self.slm_proc.request_topology(service_id)

        #Wait for the test to finish
        self.waitForFirstEvent(timeout=5)

###############################################################
#TEST9: test ia_prepare
###############################################################
    # def test_ia_prepare(self):
    #     """
    #     This method tests the request_topology method.
    #     """

    #     #Check result SUBTEST 1
    #     def on_ia_prepare_subtest1(ch, mthd, prop, payload):

    #         message = yaml.load(payload)

    #         for func in service_dict[service_id]['function']:
    #             self.assertIn(func['vim_uuid'], 
    #                           message.keys(), 
    #                           msg="VIM uuid missing from keys")

    #             image = func['vnfd']['virtual_deployment_units'][0]['vm_image']

    #             self.assertIn(image,
    #                           message[func['vim_uuid']]['vm_images'],
    #                           msg="image not on correct Vim")

    #         self.firstEventFinished()

    #     #SUBTEST1: Check ia_prepare message if functions are mapped on
    #     # different VIMs.
    #     #Setup
    #     #Create the ledger
    #     self.wait_for_first_event.clear()
    #     service_dict = {}
    #     service_id = str(uuid.uuid4())
    #     corr_id = str(uuid.uuid4())
    #     service_dict[service_id] = {'schedule': ['get_ledger'],
    #                                 'original_corr_id':corr_id,
    #                                 'pause_chain': True,
    #                                 'kill_chain': False,
    #                                 'function': []}


    #     path = '/plugins/son-mano-service-lifecycle-management/test/'

    #     message = {}
    #     message['instance_id'] = service_id
    #     vnfd1 = open(path + 'test_descriptors/firewall-vnfd.yml', 'r')
    #     vnfd2 = open(path + 'test_descriptors/iperf-vnfd.yml', 'r')
    #     vnfd3 = open(path + 'test_descriptors/tcpdump-vnfd.yml', 'r')

    #     service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd1)})
    #     service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd2)})
    #     service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd3)})

    #     for vnfd in service_dict[service_id]['function']:
    #         vim_uuid = str(uuid.uuid4())
    #         vnfd['vim_uuid'] = vim_uuid

    #     #Set the ledger
    #     self.slm_proc.set_services(service_dict)

    #     #Spy the message bus
    #     self.manoconn_spy.subscribe(on_ia_prepare_subtest1, 
    #                                 'infrastructure.service.prepare')

    #     #Wait until subscription is completed
    #     time.sleep(0.1)

    #     #Run the method
    #     self.slm_proc.ia_prepare(service_id)

    #     #Wait for the test to finish
    #     self.waitForFirstEvent(timeout=5)

    #     #SUBTEST2: Check ia_prepare message if functions are mapped on
    #     # same VIMs.
    #     #Setup
    #     #Create the ledger
    #     self.wait_for_first_event.clear()
    #     service_dict = {}
    #     service_id = str(uuid.uuid4())
    #     corr_id = str(uuid.uuid4())
    #     service_dict[service_id] = {'schedule': ['get_ledger'],
    #                                 'original_corr_id':corr_id,
    #                                 'pause_chain': True,
    #                                 'kill_chain': False,
    #                                 'function': []}


    #     path = '/plugins/son-mano-service-lifecycle-management/test/'

    #     vnfd1 = open(path + 'test_descriptors/firewall-vnfd.yml', 'r')
    #     vnfd2 = open(path + 'test_descriptors/iperf-vnfd.yml', 'r')
    #     vnfd3 = open(path + 'test_descriptors/tcpdump-vnfd.yml', 'r')

    #     service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd1)})
    #     service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd2)})
    #     service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd3)})

    #     vim_uuid = str(uuid.uuid4())
    #     for vnfd in service_dict[service_id]['function']:
    #         vnfd['vim_uuid'] = vim_uuid

    #     #Set the ledger
    #     self.slm_proc.set_services(service_dict)

    #     #Run the method
    #     self.slm_proc.ia_prepare(service_id)

    #     #Wait for the test to finish
    #     self.waitForFirstEvent(timeout=5)

# ###############################################################
# #TEST10: test vnf_deploy
# ###############################################################
#     def test_vnf_deploy(self):
#         """
#         This method tests the request_topology method.
#         """

#         #Check result SUBTEST 1
#         def on_vnf_deploy_subtest1(ch, mthd, prop, payload):
#             message = yaml.load(payload)

#             self.assertIn(message,
#                           service_dict[service_id]['function'],
#                              msg="Payload is not correct")

#             self.vnfcounter = self.vnfcounter + 1

#             if self.vnfcounter == len(service_dict[service_id]['function']):
#                 self.firstEventFinished()

#         #SUBTEST1: Run test
#         #Setup
#         #Create the ledger
#         self.wait_for_first_event.clear()
#         service_dict = {}
#         self.vnfcounter = 0
#         service_id = str(uuid.uuid4())
#         corr_id = str(uuid.uuid4())
#         service_dict[service_id] = {'schedule': ['get_ledger'],
#                                     'original_corr_id':corr_id,
#                                     'pause_chain': True,
#                                     'kill_chain': False,
#                                     'function': []}


#         path = '/plugins/son-mano-service-lifecycle-management/test/'

#         vnfd1 = open(path + 'test_descriptors/firewall-vnfd.yml', 'r')
#         vnfd2 = open(path + 'test_descriptors/iperf-vnfd.yml', 'r')
#         vnfd3 = open(path + 'test_descriptors/tcpdump-vnfd.yml', 'r')

#         service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd1),
#                                                 'id': str(uuid.uuid4()),
#                                                 'vim_uuid': str(uuid.uuid4())})
#         service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd2),
#                                                 'id': str(uuid.uuid4()),
#                                                 'vim_uuid': str(uuid.uuid4())})
#         service_dict[service_id]['function'].append({'vnfd': yaml.load(vnfd3),
#                                                 'id': str(uuid.uuid4()),
#                                                 'vim_uuid': str(uuid.uuid4())})

#         #Set the ledger
#         self.slm_proc.set_services(service_dict)

#         #Spy the message bus
#         self.manoconn_spy.subscribe(on_vnf_deploy_subtest1, 
#                                     'mano.function.deploy')

#         #Wait until subscription is completed
#         time.sleep(0.1)

#         #Run the method
#         self.slm_proc.vnf_deploy(service_id)

#         #Wait for the test to finish
#         self.waitForFirstEvent(timeout=5)

#         #SUBTEST2: TODO: test that only one message is sent per vnf

# ###############################################################################
# #TEST11: Test build_monitoring_message
# ###############################################################################
#     def test_build_monitoring_message(self):
#         """
#         This method tests the build_monitoring_message method
#         """

#         #Setup
#         gk_request = yaml.load(self.createGkNewServiceRequestMessage())

#         #add ids to NSD and VNFDs (those used in the expected message)
#         gk_request['NSD']['uuid'] = '005606ed-be7d-4ce3-983c-847039e3a5a2'
#         gk_request['VNFD1']['uuid'] = '6a15313f-cb0a-4540-baa2-77cc6b3f5b68'
#         gk_request['VNFD2']['uuid'] = '645db4fa-a714-4cba-9617-4001477d1281'
#         gk_request['VNFD3']['uuid'] = '8a0aa837-ec1c-44e5-9907-898f6401c3ae'

#         #load nsr_file, containing both NSR and the list of VNFRs
#         message_from_ia = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/ia-nsr.yml', 'r'))
#         nsr_file = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/sonata-demo-nsr.yml', 'r'))
#         vnfrs_file = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/sonata-demo-vnfrs.yml', 'r'))

#         vnfd_firewall = gk_request['VNFD1']
#         vnfd_iperf = gk_request['VNFD2']
#         vnfd_tcpdump = gk_request['VNFD3']

#         vnfr_firewall = vnfrs_file[1]
#         vnfr_iperf = vnfrs_file[0]
#         vnfr_tcpdump = vnfrs_file[2]

#         service = {'nsd': gk_request['NSD'], 'nsr': nsr_file, 'vim_uuid': message_from_ia['instanceVimUuid']}
#         functions = []
#         functions.append({'vnfr': vnfr_iperf, 'vnfd': vnfd_iperf, 'id': vnfr_iperf['id']})
#         functions.append({'vnfr': vnfr_firewall, 'vnfd': vnfd_firewall, 'id': vnfr_firewall['id']})
#         functions.append({'vnfr': vnfr_tcpdump, 'vnfd': vnfd_tcpdump, 'id': vnfr_tcpdump['id']})

#         #Call the method
#         message = tools.build_monitoring_message(service, functions)

#         #Load expected results
#         expected_message = json.load(open('/plugins/son-mano-service-lifecycle-management/test/test_descriptors/monitoring-message.json', 'r'))

#         #Check result
#         self.assertEqual(message, expected_message, "messages are not equals")

# ###############################################################################
# #TEST12: Test build_nsr
# ###############################################################################
#     def test_build_nsr(self):
#         """
#         This method tests the build_nsr method
#         """

#         #Setup
#         gk_request = yaml.load(self.createGkNewServiceRequestMessage())
#         nsd = gk_request['NSD']

#         ia_message = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/ia-nsr.yml', 'r'))
#         expected_nsr = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/sonata-demo-nsr.yml', 'r'))

#         vnfr_ids = ['645db4fa-a714-4cba-9617-4001477d0000','6a15313f-cb0a-4540-baa2-77cc6b3f0000', '8a0aa837-ec1c-44e5-9907-898f64010000']

#         #Call method
#         message = tools.build_nsr(ia_message, nsd, vnfr_ids, ia_message['nsr']['id'])

#         #Check result
#         self.assertEqual(message, expected_nsr, "Built NSR is not equal to the expected one")

# ###############################################################################
# #TEST13: Test build_vnfr
# ###############################################################################
#     def test_build_vnfr(self):
#         """
#         This method tests the build_vnfr method
#         """

#         #Setup
#         gk_request = yaml.load(self.createGkNewServiceRequestMessage())
#         vnfd_iperf = gk_request['VNFD2']

#         ia_vnfr_iperf = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/ia-vnfr-iperf.yml', 'r'))
#         expected_vnfr_iperf = yaml.load(open('/plugins/son-mano-service-lifecycle-management/test/test_records/expected_vnfr_iperf.yml', 'r'))

#         #Call method
#         message = tools.build_vnfr(ia_vnfr_iperf['vnfr'], vnfd_iperf)

#         #Check result
#         self.assertEqual(message, expected_vnfr_iperf, "Built VNFRs are not equals to the expected ones")


if __name__ == '__main__':
    unittest.main()
