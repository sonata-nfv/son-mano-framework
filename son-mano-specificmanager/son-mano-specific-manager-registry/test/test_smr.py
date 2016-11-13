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
        e.pull(ssm_uri="hadik3r/ssmexample", ssm_name='ssmexample')
        img = e.dc.get_image('hadik3r/ssmexample')
        self.assertIsNotNone(img)
        e.dc.close()

    def test_container_instantiation(self):
        e = engine_connection(self)
        e.pull(ssm_uri="hadik3r/ssmexample", ssm_name='ssmexample')
        e.start(image_name="hadik3r/ssmexample", ssm_name='ssmexample', host_ip= None)
        con = e.dc.containers(filters={'name': 'ssmexample'})
        self.assertIsNotNone(con)
        e.dc.close()

if __name__ == "__main__":
    unittest.main()







# """
# Copyright (c) 2015 SONATA-NFV
# ALL RIGHTS RESERVED.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).
# """
# #!/usr/bin/env python -W ignore::ResourceWarning
#
# import unittest
# import time
# import logging
# import threading
# import yaml
# from multiprocessing import Process
# from sonmanobase.messaging import ManoBrokerRequestResponseConnection
# from son_mano_specific_manager_registry.specificmanagerregistry import SpecificManagerRegistry
# #from test.fake_slm1 import fakeslm
# #from test.fake_slm2 import fakeslmu
# from son_mano_specific_manager_registry.smr_engine import SMREngine
#
# logging.basicConfig(level=logging.INFO)
# logging.getLogger('amqp-storm').setLevel(logging.INFO)
# LOG = logging.getLogger("son-mano-plugins:smr_test")
# logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
# logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
# LOG.setLevel(logging.INFO)
#
# class testSMRRegistration(unittest.TestCase):
#     """
#     Tests the registration process of SMR to the broker
#     and the plugin manager, and the heartbeat process.
#     """
#
#     def setUp(self):
#         #a new SMR in another process for each test
#         self.smr_proc = Process(target=SpecificManagerRegistry)
#         #self.smr_registration = Process(target=self.testSMRRegistration)
#         #self.smr_connection = Process(target=self.test_docker_service_connection)
#         #self.smr_onboard = Process(target=self.test_ssm_onboard)
#         #self.smr_instantiate = Process(target=self.test_ssm_instantiate)
#         #self.smr_kill = Process(target=self.test_ssm_kill)
#         #self.smr_proc.daemon = True
#         #self.tLock = threading.Lock()
#
#         #make a new connection with the broker before each test
#         #self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')
#
#         #Some threading events that can be used during the tests
#         #self.wait_for_event = threading.Event()
#         #self.wait_for_event.clear()
#
#         #self.smr_registration.start()
#         #self.tLock.acquire()
#
#         #self.smr_connection.start()
#         self.test_docker_service_connection()
#         #self.tLock.acquire()
#
#         #self.smr_onboard.start()
#         #self.tLock.acquire()
#
#         #self.smr_instantiate.start()
#         #self.tLock.acquire()
#
#
#     # def tearDown(self):
#     #     #Killing SMR
#     #     if self.smr_proc is not None:
#     #         self.smr_proc.terminate()
#     #     del self.smr_proc
#     #
#     #     #Killing the connection with the broker
#     #     try:
#     #         self.manoconn.stop_connection()
#     #     except Exception as e:
#     #         LOG.exception("Stop connection exception.")
#     #
#     #     #Clearing the threading helpers
#     #     del self.wait_for_event
#     #
#     # #Method that terminates the timer that waits for an event
#     # def eventFinished(self):
#     #     self.wait_for_event.set()
#     #
#     # #Method that starts a timer, waiting for an event
#     # def waitForEvent(self, timeout=5, msg="Event timed out."):
#     #     if not self.wait_for_event.wait(timeout):
#     #         self.assertEqual(True, False, msg=msg)
#
#
#     # def testSMRRegistration(self):
#     #     """
#     #     TEST: This test verifies whether SMR is sending out a message,
#     #     and whether it contains all the needed info on the
#     #     platform.management.plugin.register topic to register to the plugin
#     #     manager.
#     #     """
#     #     self.tLock.acquire()
#     #
#     #     #STEP3a: When receiving the message, we need to check whether all fields present.
#     #     def on_register_receive(ch, method, properties, message):
#     #
#     #         msg = yaml.load(message)
#     #         #CHECK: The message should be a dictionary.
#     #         self.assertTrue(isinstance(msg, dict), msg='message is not a dictionary')
#     #         #CHECK: The dictionary should have a key 'name'.
#     #         self.assertIn('name', msg.keys(), msg='No name provided in message.')
#     #         if isinstance(msg['name'], str):
#     #             #CHECK: The value of 'name' should not be an empty string.
#     #             self.assertTrue(len(msg['name']) > 0, msg='empty name provided.')
#     #         else:
#     #             #CHECK: The value of 'name' should be a string
#     #             self.assertEqual(True, False, msg='name is not a string')
#     #         #CHECK: The dictionary should have a key 'version'.
#     #         self.assertIn('version', msg.keys(), msg='No version provided in message.')
#     #         if isinstance(msg['version'], str):
#     #             #CHECK: The value of 'version' should not be an empty string.
#     #             self.assertTrue(len(msg['version']) > 0, msg='empty version provided.')
#     #         else:
#     #             #CHECK: The value of 'version' should be a string
#     #             self.assertEqual(True, False, msg='version is not a string')
#     #         #CHECK: The dictionary should have a key 'description'
#     #         self.assertIn('description', msg.keys(), msg='No description provided in message.')
#     #         if isinstance(msg['description'], str):
#     #             #CHECK: The value of 'description' should not be an empty string.
#     #             self.assertTrue(len(msg['description']) > 0, msg='empty description provided.')
#     #         else:
#     #             #CHECK: The value of 'description' should be a string
#     #             self.assertEqual(True, False, msg='description is not a string')
#     #
#     #         # stop waiting
#     #         self.eventFinished()
#     #         self.tLock.release()
#     #
#     #     #STEP1: Listen to the platform.management.plugin.register topic
#     #     self.manoconn.subscribe(on_register_receive, 'platform.management.plugin.register')
#     #
#     #     #STEP2: Start SMR
#     #     self.smr_proc.start()
#     #
#     #     #STEP3b: When not receiving the message, the test failed
#     #     self.waitForEvent(timeout=5, msg="message not received.")
#
#     def test_docker_service_connection(self):
#         #self.tLock.acquire()
#         e = SMREngine()
#         #self.assertIsNotNone(e.dc.info().get("ServerVersion"))
#         #self.tLock.release()
#
#     # def test_ssm_onboard(self):
#     #     # ensure that existing test images and containers are removed
#     #     #image_container_cleaner(ssmdumb=True,ssmsmart=False)
#     #     self.tLock.acquire()
#     #     e = SMREngine()
#     #     e.pull(ssm_uri="sonatanfv/dumb", ssm_name='dumb')
#     #     img = e.dc.get_image('sonatanfv/dumb')
#     #     self.assertIsNotNone(img)
#     #     self.tLock.release()
#     #
#     # def test_ssm_instantiate(self):
#     #     # ensure that existing test images and containers are removed
#     #     #image_container_cleaner(ssmdumb=True,ssmsmart=False)
#     #     self.tLock.acquire()
#     #     e = SMREngine()
#     #     e.pull(ssm_uri="sonatanfv/dumb", ssm_name='dumb')
#     #     e.start(image_name="sonatanfv/dumb", ssm_name='dumb', host_ip= None)
#     #     con = e.dc.containers(filters={'name': 'dumb'})
#     #     self.assertIsNotNone(con)
#     #     self.tLock.release()
#
#     # def test_ssm_kill(self):
#     #     # ensure that existing test images and containers are removed
#     #     #image_container_cleaner(ssmdumb=True,ssmsmart=True)
#     #     e = SMREngine()
#     #     e.pull(ssm_uri="sonatanfv/dumb", ssm_name='dumb')
#     #     e.start(image_name="sonatanfv/dumb", ssm_name='dumb', host_ip= None)
#     #     e.stop('dumb')
#     #     con = e.dc.containers(filters={'name': 'dumb'})
#     #     self.assertEqual(con, [])
#
#
# # class test2SpecificManagerRegistry(unittest.TestCase):
# #     def setUp(self):
# #
# #         # ensure that existing test images and containers are removed
# #
# #         image_container_cleaner(ssmdumb=True,ssmsmart=True)
# #
# #         self.srm_proc = Process(target=SpecificManagerRegistry)
# #         self.srm_proc.daemon = True
# #
# #         self.nsd1_proc = Process(target=fakeslm)
# #         self.nsd1_proc.daemon = True
# #
# #         self.nsd2_proc = Process(target=fakeslmu)
# #         self.nsd2_proc.daemon = True
# #
# #         self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')
# #         self.wait_for_event1 = threading.Event()
# #         self.wait_for_event1.clear()
# #
# #         self.wait_for_event2 = threading.Event()
# #         self.wait_for_event2.clear()
# #
# #     def tearDown(self):
# #         if self.srm_proc is not None:
# #             self.srm_proc.terminate()
# #         del self.srm_proc
# #
# #         if self.nsd1_proc is not None:
# #             self.nsd1_proc.terminate()
# #         del self.nsd1_proc
# #
# #         if self.nsd2_proc is not None:
# #             self.nsd2_proc.terminate()
# #         del self.nsd2_proc
# #
# #         try:
# #             self.manoconn.stop_connection()
# #         except Exception as e:
# #             LOG.exception("Stop connection exception.")
# #
# #         del self.wait_for_event1
# #
# #     def eventFinished1(self):
# #         self.wait_for_event1.set()
# #
# #     def waitForEvent1(self, timeout=5, msg="Event timed out."):
# #         if not self.wait_for_event1.wait(timeout):
# #             self.assertEqual(True, False, msg=msg)
# #
# #     def eventFinished2(self):
# #         self.wait_for_event2.set()
# #
# #     def waitForEvent2(self, timeout=5, msg="Event timed out."):
# #         if not self.wait_for_event2.wait(timeout):
# #             self.assertEqual(True, False, msg=msg)
# #
# #     def msg_receive_waiting(self, msg, field, timeout):
# #         c = 0
# #         while field not in msg.keys() and c < timeout:
# #             time.sleep(0.1)
# #             c += 0.1
# #
# #     def test_smr_features(self):
# #
# #         def test_on_onboard_receive(ch, method, properties, message):
# #             msg = yaml.load(str(message))  # , 'utf-8'))
# #             self.msg_receive_waiting(msg, 'status', 5)
# #             if 'status' in msg.keys():
# #                 self.assertEqual(msg['status'], 'On-boarded')
# #                 LOG.info('SSM on-board test: Passed')
# #
# #         def test_on_instantiate_receive(ch, method, properties, message):
# #             msg = yaml.load(str(message))  # , 'utf-8'))
# #             self.msg_receive_waiting(msg, 'status', 5)
# #             if 'status' in msg.keys():
# #                 self.assertEqual(msg['status'], 'Instantiated')
# #                 LOG.info('SSM instantiation test: Passed')
# #
# #         def test_on_registration_receive(ch, method, properties, message):
# #             msg = yaml.load(str(message))  # , 'utf-8'))
# #             self.msg_receive_waiting(msg, 'status', 5)
# #             if 'status' in msg.keys():
# #                 self.assertEqual(msg['status'], 'running')
# #                 LOG.info('SSM registration into the SMR test: Passed')
# #                 self.nsd1_proc.terminate()
# #                 time.sleep(3)
# #                 self.nsd2_proc.start()
# #                 self.waitForEvent2(timeout=170, msg="message not received.")
# #                 self.eventFinished1()
# #
# #         def test_on_update_receive(ch, method, properties, message):
# #             msg = yaml.load(str(message))  # , 'utf-8'))
# #             self.msg_receive_waiting(msg, 'status', 5)
# #             if 'status' in msg.keys():
# #                 self.assertEqual(msg['status'],'Updated')
# #                 #self.assertEqual(msg['on-board'], 'OK')
# #                 #self.assertEqual(msg['instantiation'], 'OK')
# #                 #self.assertEqual(msg['status'], 'killed')
# #                 LOG.info('SSM update test: Passed')
# #                 LOG.info('SSM kill test: Passed')
# #                 # stop waiting
# #                 self.eventFinished2()
# #
# #         self.manoconn.subscribe(test_on_onboard_receive, 'specific.manager.registry.ssm.on-board')
# #         self.manoconn.subscribe(test_on_instantiate_receive, 'specific.manager.registry.ssm.instantiate')
# #         self.manoconn.subscribe(test_on_registration_receive, 'specific.manager.registry.ssm.registration')
# #         self.manoconn.subscribe(test_on_update_receive, 'specific.manager.registry.ssm.update')
# #
# #         time.sleep(5)
# #         self.srm_proc.start()
# #
# #
# #         time.sleep(3)
# #         self.nsd1_proc.start()
# #
# #         self.waitForEvent1(timeout=270, msg="message not received.")
#
#
# # class testSMREngine(unittest.TestCase):
# #     def test_docker_service_connection(self):
# #         e = SMREngine()
# #         self.assertIsNotNone(e.dc.info().get("ServerVersion"))
# #
# #     def test_ssm_onboard(self):
# #         # ensure that existing test images and containers are removed
# #         #image_container_cleaner(ssmdumb=True,ssmsmart=False)
# #         e = SMREngine()
# #         e.pull(ssm_uri="sonatanfv/dumb", ssm_name='dumb')
# #         img = e.dc.get_image('sonatanfv/dumb')
# #         self.assertIsNotNone(img)
# #
# #     def test_ssm_instantiate(self):
# #         # ensure that existing test images and containers are removed
# #         #image_container_cleaner(ssmdumb=True,ssmsmart=False)
# #         e = SMREngine()
# #         e.pull(ssm_uri="sonatanfv/dumb", ssm_name='dumb')
# #         e.start(image_name="sonatanfv/dumb", ssm_name='dumb', host_ip= None)
# #         con = e.dc.containers(filters={'name': 'dumb'})
# #         self.assertIsNotNone(con)
# #
# #     def test_ssm_kill(self):
# #         # ensure that existing test images and containers are removed
# #         #image_container_cleaner(ssmdumb=True,ssmsmart=True)
# #         e = SMREngine()
# #         e.pull(ssm_uri="sonatanfv/dumb", ssm_name='dumb')
# #         e.start(image_name="sonatanfv/dumb", ssm_name='dumb', host_ip= None)
# #         e.stop('dumb')
# #         con = e.dc.containers(filters={'name': 'dumb'})
# #         self.assertEqual(con, [])
# #
# #
# # def image_container_cleaner(ssmdumb, ssmsmart):
# #     e = SMREngine()
# #     if ssmdumb:
# #         try:
# #             e.dc.stop('dumb')
# #             e.dc.remove_container('dumb')
# #         except BaseException as ex:
# #             pass
# #         try:
# #             e.dc.remove_image(force=True, image='sonatanfv/dumb')
# #         except BaseException as ex:
# #             pass
# #
# #     if ssmsmart:
# #         try:
# #             e.dc.stop('ssmsmart')
# #             e.dc.remove_container('ssmsmart')
# #         except BaseException as ex:
# #             pass
# #
# #         try:
# #             e.dc.remove_image(force=True, image='sonatanfv/ssmsmart')
# #         except BaseException as ex:
# #             pass
#
#
# if __name__ == "__main__":
#     unittest.main()
