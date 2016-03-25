import unittest
import time
import json
import threading
from multiprocessing import Process
from son_mano_slm.slm import ServiceLifecycleManager
from sonmanobase.messaging import ManoBrokerRequestResponseConnection


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

        #STEP4: Wait until the heartbeat message is received. TODO: What is the time window?
        self.waitForEvent(timeout=30, msg="No heartbeat received")

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
            #CHECK: The dictionary should have a key 'description'.
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


if __name__ == '__main__':
    unittest.main()
        

        
                

