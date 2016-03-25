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

    manoconn = None    

    @classmethod
    def setUpClass(cls):
        # we test the interaction between the SLM and the plugin manager. Therefore, we need to simulate the presence of such a plugin manager. We open a connection to the broker in name of the plugin manager
        cls.manoconn = ManoBrokerRequestResponseConnection('Son-plugin.SonPluginManager')

    @classmethod
    def tearDownClass(cls):
        if cls.manoconn is not None:
            del cls.manoconn

    def setUp(self):
        #a new SLM in another process for each test
        self.slm_proc = Process(target=ServiceLifecycleManager)
        self.slm_proc.daemon = True
    
        #Some threading events that can be used during the tests
        self.wait_for_reply = threading.Event()
        self.wait_for_reply.clear()
        self.wait_for_analysis = threading.Event()
        self.wait_for_analysis.clear()

    def tearDown(self):
        if self.slm_proc is not None:
            self.slm_proc.terminate()
        del self.slm_proc
        del self.wait_for_reply    
        del self.wait_for_analysis    

    #Trigger the treading event when a message we were waiting for is received.
    def messageReceived(self):
        self.wait_for_reply.set()

    #Give the unit under review some time to come up with a message
    def waitForMessage(self, timeout=5):
        if not self.wait_for_reply.wait(timeout):
            self.assertEqual(True, False, msg='No message received')   

    #Trigger the wait for the analysis when it is done
    def analysisFinished(self):
        self.wait_for_analysis.set()

    #Wait for the data to be analysed
    def waitForAnalysis(self, timeout=5):
        if not self.wait_for_analysis.wait(timeout):
            raise Exception("Timeout in wait for analysis.")
        
    def testSlmRegistration(self):
        """
        TEST: This test verifies whether the SLM is sending out a message, and whether it contains all the needed info on the platform.management.plugin.register topic to register to the plugin manager. 
        """

        #STEP3a: When receiving the message, we need to check whether all fields present. TODO: check properties
        def on_register_receive(ch, method, properties, message):
            #Once the message is received, the wait for the message assert can be disabled.
            self.messageReceived()
                        
            msg = json.loads(str(message, "utf-8"))
            self.assertTrue(isinstance(msg, dict), msg='message is not a dictionary')

            self.assertIn('name', msg.keys(), msg='No name provided in message.')
            if isinstance(msg['name'], str):
                self.assertTrue(len(msg['name']) > 0, msg='empty name provided.')
            else:
                self.assertEqual(True, False, msg='name is not a string')

            self.assertIn('version', msg.keys(), msg='No version provided in message.')
            if isinstance(msg['version'], str):
                self.assertTrue(len(msg['version']) > 0, msg='empty version provided.')
            else:
                self.assertEqual(True, False, msg='version is not a string')

            self.assertIn('description', msg.keys(), msg='No description provided in message.')
            if isinstance(msg['description'], str):
                self.assertTrue(len(msg['description']) > 0, msg='empty description provided.')
            else:
                self.assertEqual(True, False, msg='description is not a string')


            # analysis done
            self.analysisFinished()

        #STEP1: Listen to the platform.management.plugin.register topic
        self.manoconn.subscribe(on_register_receive,'platform.management.plugin.register')

        #STEP2: Start the SLM
        self.slm_proc.start()

        #STEP3b: When not receiving the message, the test failed 
        self.waitForMessage(timeout=10)

        #When the message is received, on_register_receive needs some time to evaluate it
        self.waitForAnalysis()

    def testSlmHeartbeat(self):
        """
        TEST: This test verifies whether the SLM sends out a heartbeat as intended, once it is registered.
        """

        self.slm_proc = None

if __name__ == '__main__':
    unittest.main()
        

        
                

