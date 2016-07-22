import unittest
import time
import logging
import json
import threading
from multiprocessing import Process
from sonmanobase.messaging import ManoBrokerRequestResponseConnection
from son_mano_specific_manger_registry.specificmangerregistry import SpecificManagerRegistry
from son_mano_specific_manger_registry.slm_nsd1 import fakeslm
from son_mano_specific_manger_registry.slm_nsd2 import fakesmlU
from son_mano_pluginmanager.pluginmanager import SonPluginManager


logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:smr_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)


class TestSpecificManagerRegistry(unittest.TestCase):

    def setUp(self):

        self.pm_proc = Process(target=SonPluginManager)
        self.pm_proc.daemon = True

        self.smr_proc = Process(target=SpecificManagerRegistry)
        self.smr_proc.daemon = True

        self.nsd1_proc = Process(target=fakeslm)
        self.nsd1_proc.daemon = True

        self.nsd2_proc = Process(target=fakesmlU)
        self.nsd2_proc.daemon = True

        #make a new connection with the broker before each test
        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')

        #Some threading events that can be used during the tests
        self.wait_for_event = threading.Event()
        self.wait_for_event.clear()

    def msg_receive_waiting(self, msg, field, timeout):
        c = 0
        while field not in msg.keys() and c < timeout:
            time.sleep(0.1)
            c += 0.1

    #Method that terminates the timer that waits for an event
    def eventFinished(self):
        self.wait_for_event.set()

    #Method that starts a timer, waiting for an event
    def waitForEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def testSMRFeatures(self):

        def on_register_receive(ch, method, properties, message):

            msg = json.loads(str(message))#,'utf-8'))

            #CHECK:The response from plugin manager
            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'], 'OK')
                self.assertGreater(len(msg.get("uuid")), 0)
                LOG.info('SMR registration into the plugin manager test: Passed')
                # Start the fake SLM(sending the first NSD)
                self.nsd1_proc.start()

        def on_onboard_receive(ch, method, properties, message):

            msg = json.loads(str(message))#, 'utf-8'))

            # CHECK: on-board response from SMR
            self.msg_receive_waiting(msg, 'on-board', 5)
            if 'on-board' in msg.keys():
                self.assertEqual(msg['on-board'], 'OK')
                LOG.info('SSM on-board test: Passed')

        def on_instantiate_receive(ch, method, properties, message):

            msg = json.loads(str(message))#, 'utf-8'))

            # CHECK: instantiation response from SMR
            self.msg_receive_waiting(msg, 'instantiation', 5)
            if 'instantiation' in msg.keys():
                self.assertEqual(msg['instantiation'],'OK')
                LOG.info('SSM instantiation test: Passed')

        def on_registration_receive(ch, method, properties, message):

            msg = json.loads(str(message))#, 'utf-8'))

            # CHECK: SSM registration response from SMR
            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'],'OK')
                LOG.info('SSM registration into the SMR test: Passed')
                if msg['name'] =='ssm1':
                    # Start the fake SLM(sending the second NSD)
                    self.nsd2_proc.start()

        def on_update_receive(ch, method, properties, message):

            msg = json.loads(str(message))#, 'utf-8'))

            # CHECK: SSM update response from SMR
            self.msg_receive_waiting(msg, 'status', 5)
            if 'on-board' in msg.keys():
                self.assertEqual(msg['on-board'],'OK')
                self.assertEqual(msg['instantiation'],'OK')
                self.assertEqual(msg['status'], 'killed')
                LOG.info('SSM update test: Passed')
                LOG.info('SSM kill test: Passed')
                # stop waiting
                self.eventFinished()


        #Listen to the required topic
        self.manoconn.subscribe(on_register_receive, 'platform.management.plugin.register')

        self.manoconn.subscribe(on_onboard_receive, 'specific.manager.registry.on-board')

        self.manoconn.subscribe(on_instantiate_receive, 'specific.manager.registry.instantiate')

        self.manoconn.subscribe(on_registration_receive, 'specific.manager.registry.ssm.registration')

        self.manoconn.subscribe(on_update_receive, 'specific.manager.registry.ssm.update')

        # Start the PM
        self.pm_proc.start()

        # Start the SMR
        self.smr_proc.start()


        #When not receiving the message, the test failed
        self.waitForEvent(timeout=500, msg="message not received.")


if __name__ == "__main__":
    unittest.main()