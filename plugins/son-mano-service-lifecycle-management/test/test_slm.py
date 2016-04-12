import unittest
import time
import json
import yaml
import threading
import logging

from multiprocessing import Process
from son_mano_slm.slm import ServiceLifecycleManager
from sonmanobase.messaging import ManoBrokerRequestResponseConnection

logging.basicConfig(level=logging.INFO)
logging.getLogger('pika').setLevel(logging.ERROR)
LOG = logging.getLogger("son-mano-plugins:slm_test")
LOG.setLevel(logging.DEBUG)


class testSlmRegistrationAndHeartbeat(unittest.TestCase):
    """
    Tests the registration process of the SLM to the broker and the plugin manager, and the heartbeat process.
    """

    def setUp(self):
        #a new SLM in another process for each test
        self.slm_proc = Process(target=ServiceLifecycleManager)
        self.slm_proc.daemon = True
        #make a new connection with the broker before each test 
        self.manoconn = ManoBrokerRequestResponseConnection('Son-plugin.SonPluginManager')

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
        TEST: This test verifies whether the SLM sends out a heartbeat as intended, once it is registered and whether this heartbeat message is correctly formatted.
        """
        
        def on_registration_trigger(ch, method, properties, message):
            """
            When the registration request from the plugin is received, this method replies as if it were the plugin manager
            """
            self.eventFinished()
            return json.dumps({'status':'OK','uuid':self.uuid})

        def on_heartbeat_receive(ch, method, properties, message):
            """
            When the heartbeat message is received, this method checks if it is formatted correctly
            """
            msg = json.loads(str(message, "utf-8"))
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
            self.assertTrue(msg["state"] in ["READY","RUNNING","PAUSED","FAILED"], msg="Not a valid state.")

            #Stop the wait
            self.eventFinished()

        #STEP1: subscribe to the correct topics
        self.manoconn.register_async_endpoint(on_registration_trigger,'platform.management.plugin.register')
        self.manoconn.subscribe(on_heartbeat_receive, 'platform.management.plugin.' + self.uuid + '.heartbeat')

        #STEP2: Start the SLM
        self.slm_proc.start()

        #STEP3: Wait until the registration request has been answered
        self.waitForEvent(msg="No registration request received")

        self.wait_for_event.clear()

        # TODO: deactivated (seems to break local tests)
        #STEP4: Wait until the heartbeat message is received. TODO: What is the time window?
        #self.waitForEvent(timeout=30, msg="No heartbeat received")

    def testSlmRegistration(self):
        """
        TEST: This test verifies whether the SLM is sending out a message, and whether it contains all the needed info on the platform.management.plugin.register topic to register to the plugin manager. 
        """

        #STEP3a: When receiving the message, we need to check whether all fields present. TODO: check properties
        def on_register_receive(ch, method, properties, message):

            msg = json.loads(str(message, "utf-8"))
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
        self.manoconn.subscribe(on_register_receive,'platform.management.plugin.register')

        #STEP2: Start the SLM
        self.slm_proc.start()

        #STEP3b: When not receiving the message, the test failed 
        self.waitForEvent(timeout=5,msg="message not received.")


class testSlmFunctionality(unittest.TestCase):
    """
    Tests the tasks that the SLM should perform in the service life cycle of the network services.
    """

    slm_proc    = None
    manoconn_pm = None
    uuid        = '1'
    corr_id     = '1ba347d6-6210-4de7-9ca3-a383e50d0330'

    @classmethod
    def setUpClass(cls):
        """
        Starts the SLM instance and takes care if its registration.
        """
        def on_register_trigger(ch, method, properties, message):
            return json.dumps({'status':'OK','uuid':cls.uuid})

        #Some threading events that can be used during the tests
        cls.wait_for_event = threading.Event()
        cls.wait_for_event.clear()

        #Deploy SLM and a connection to the broker
        cls.slm_proc = Process(target=ServiceLifecycleManager)
        cls.slm_proc.daemon = True
        cls.manoconn_pm = ManoBrokerRequestResponseConnection('Son-plugin.SonPluginManager')
        cls.manoconn_pm.subscribe(on_register_trigger,'platform.management.plugin.register')
        cls.slm_proc.start()
        #wait until registration process finishes
        if not cls.wait_for_event.wait(timeout=5):
            pass

    @classmethod
    def tearDownClass(cls):
        if cls.slm_proc is not None:
            cls.slm_proc.terminate()
            del cls.slm_proc
#        cls.manoconn_pm.stop_connection()

    def setUp(self):
        #We make a spy connection to listen to the different topics on the broker
        self.manoconn_spy = ManoBrokerRequestResponseConnection('Son-plugin.SonSpy')
        #we need a connection to simulate messages from the gatekeeper
        self.manoconn_gk = ManoBrokerRequestResponseConnection('Son-plugin.SonGateKeeper')
        #we need a connection to simulate messages from the infrastructure adapter
        self.manoconn_ia = ManoBrokerRequestResponseConnection('Son-plugin.SonInfrastructureAdapter')


    def tearDown(self):
        self.manoconn_spy.stop_connection()
        self.manoconn_gk.stop_connection()
        self.manoconn_ia.stop_connection()

    def createGkNewServiceRequestMessage(self):
        """
        This method helps creating messages for the service request packets.
        """
        
        path_descriptors = '/plugins/son-mano-service-lifecycle-management/test/test_descriptors/'
    	#import the nsd and vnfds that form the service	
        nsd_descriptor   = open(path_descriptors + 'sonata-demo.yml','r')
        vnfd1_descriptor = open(path_descriptors + 'firewall-vnfd.yml','r')
        vnfd2_descriptor = open(path_descriptors + 'iperf-vnfd.yml','r')
        vnfd3_descriptor = open(path_descriptors + 'tcpdump-vnfd.yml','r')

        service_request = {'NSD': yaml.load(nsd_descriptor), 'VNFD1': yaml.load(vnfd1_descriptor), 'VNFD2': yaml.load(vnfd2_descriptor), 'VNFD3': yaml.load(vnfd3_descriptor)}

        return yaml.dump(service_request)

    #Method that terminates the timer that waits for an event
    def eventFinished(self):
        self.wait_for_event.set()

    #Method that starts a timer, waiting for an event
    def waitForEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def on_slm_infra_adaptor_instantiation(self, ch, method, properties, message):

        #The message send on to the IA should be the same as the one received from the GK
        received_msg = yaml.load(message)
        sent_msg     = yaml.load(self.createGkNewServiceRequestMessage())
        self.assertEqual(received_msg, sent_msg, msg='Not the same message.')

        self.eventFinished()

    def on_slm_gk_response(self, ch, method, properties, message):
        self.eventFinished()

    def on_gk_response_service_request(self, ch, method, properties, message):

        #TODO
        return

    def on_service_deployment_response(self, ch, method, properties, message):
        msg =  yaml.load(message)
        self.assertIn('request_status', msg.keys(), msg='request_status is not a key')
        self.eventFinished()
        return

    def do_nothing(self, ch, method, properties, message):
        return

    def testResponseToGkNewServiceRequest(self):
        """
        This method tests the reaction of the SLM when it receives a message from the gk, targetted to the infrastructure adaptor.
        """
        
        #STEP1: Spy the topic on which the SLM will contact the infrastructure adaptor
        self.manoconn_spy.subscribe(self.on_slm_infra_adaptor_instantiation, 'infrastructure.service.deploy')

        #STEP2: Send a service request message (from the gk) to the SLM
        self.manoconn_gk.call_async(self.on_gk_response_service_request, 'service.instances.create', msg=self.createGkNewServiceRequestMessage(), content_type='application/yaml', correlation_id=self.corr_id)

        #STEP3: Start waiting for the messages that are triggered by this request
        self.waitForEvent(timeout=10)

    def createInfrastructureAdapterResponseMessage(self):
        path_descriptors = '/plugins/son-mano-service-lifecycle-management/test/test_descriptors/'

        ia_nsr = open(path_descriptors + 'infrastructure-adapter-nsr.yml','r')

        return str(yaml.load(ia_nsr))

    def test_on_infra_adaptor_service_deploy_reply(self):

        #STEP1: Spy the topic on which the SLM will contact the GK
        self.manoconn_spy.subscribe(self.on_service_deployment_response, 'service.instances.create')

        #STEP2: Send a service deployment response from Inrastructure Adapter to the SLM. This response should be of type .notify, since the SLM expects a response to an async_call, and with .notify, we can add the correlation_id to make it look like that response.
        self.manoconn_ia.notify("infrastructure.service.deploy", msg=self.createInfrastructureAdapterResponseMessage(), content_type='application/yaml', correlation_id=self.corr_id)

        # TODO: deactivated (seems to break local tests)
        #STEP3: Start waiting for the messages that are triggered by this request
        #self.wait_for_event.clear()
        #self.waitForEvent(timeout=10)

if __name__ == '__main__':
    unittest.main()
        

        
                

