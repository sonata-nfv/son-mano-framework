import unittest
import threading
import yaml
import logging
from multiprocessing import Process
from son_mano_specific_manager_registry.smr_engine import SMREngine
from sonmanobase.messaging import ManoBrokerRequestResponseConnection
from son_mano_specific_manager_registry.specificmanagerregistry import SpecificManagerRegistry


logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:smr_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)

def engine_connection(self):
    e = SMREngine()
    return e

class testSMRRegistration(unittest.TestCase):

    def setUp(self):
        #a new SMR in another process for each test
        self.smr_proc = Process(target=SpecificManagerRegistry)
        self.smr_proc.daemon = True
        #make a new connection with the broker before each test
        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')

        #Some threading events that can be used during the tests
        self.wait_for_event = threading.Event()
        self.wait_for_event.clear()

        #The uuid that can be assigned to the plugin
        self.uuid = '1'

    def tearDown(self):
        #Killing SMR
        if self.smr_proc is not None:
            self.smr_proc.terminate()
        del self.smr_proc

        #Killing the connection with the broker
        try:
            self.manoconn.stop_connection()
        except Exception as e:
            LOG.exception("Stop connection exception.")

        #Clearing the threading helpers
        del self.wait_for_event

    #Method that terminates the timer that waits for an event
    def eventFinished(self):
        self.wait_for_event.set()

    #Method that starts a timer, waiting for an event
    def waitForEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)


    def testSMRRegistration(self):
        """
        TEST: This test verifies whether SMR is sending out a message,
        and whether it contains all the needed info on the
        platform.management.plugin.register topic to register to the plugin
        manager.
        """

        #STEP3a: When receiving the message, we need to check whether all fields present.
        def on_register_receive(ch, method, properties, message):

            msg = yaml.load(message)
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

        #STEP2: Start the Scaling Executive
        self.smr_proc.start()

        #STEP3b: When not receiving the message, the test failed
        self.waitForEvent(timeout=5, msg="message not received.")

class testSMREngine(unittest.TestCase):

    def test_docker_service_connection(self):
        e = engine_connection(self)
        self.assertIsNotNone(e.dc.info().get("ServerVersion"))
        e.dc.close()
        

    def test_container_onboarding(self):
        e = engine_connection(self)
        e.pull(image="hadik3r/ssmexample")
        img = e.dc.get_image('hadik3r/ssmexample')
        self.assertIsNotNone(img)
        e.dc.close()

    def test_container_instantiation(self):
        e = engine_connection(self)
        e.pull( image ="hadik3r/ssmexample")
        e.start(id='ssmexample', image="hadik3r/ssmexample", uuid= None)
        con = e.dc.containers(filters={'name': 'ssmexample'})
        self.assertIsNotNone(con)
        e.dc.close()

if __name__ == "__main__":
    unittest.main()