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
#!/usr/bin/env python -W ignore::ResourceWarning

import unittest
import time
import logging
import threading
import yaml
from multiprocessing import Process
from sonmanobase.messaging import ManoBrokerRequestResponseConnection
from son_mano_specific_manager_registry.specificmanagerregistry import SpecificManagerRegistry
from test.fake_slm1 import fakeslm
from test.fake_slm2 import fakeslmu
from son_mano_specific_manager_registry.smr_engine import SMREngine

logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:smr_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)

class test1SpecificManagerRegistry(unittest.TestCase):
    def setUp(self):

        self.srm_proc = Process(target=SpecificManagerRegistry)
        self.srm_proc.daemon = True

        self.nsd1_proc = Process(target=fakeslm)
        self.nsd1_proc.daemon = True

        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')

        self.wait_for_event = threading.Event()
        self.wait_for_event.clear()

    def tearDown(self):
        if self.srm_proc is not None:
            self.srm_proc.terminate()
        del self.srm_proc

        try:
            self.manoconn.stop_connection()
        except Exception as e:
            LOG.exception("Stop connection exception.")

        del self.wait_for_event

    def eventFinished(self):
        self.wait_for_event.set()

    def waitForEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def msg_receive_waiting(self, msg, field, timeout):
        c = 0
        while field not in msg.keys() and c < timeout:
            time.sleep(0.1)
            c += 0.1

    def test_smr_registration_in_pm(self):

        def on_register_receive(ch, method, properties, message):
            msg = yaml.load(str(message))  # ,'utf-8'))

            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'], 'OK')
                self.assertGreater(len(msg.get("uuid")), 0)
                LOG.info('SMR registration in the plugin manager test: Passed')
                self.eventFinished()

        self.manoconn.subscribe(on_register_receive, 'platform.management.plugin.register')

        self.srm_proc.start()

        self.waitForEvent(timeout=10, msg="message not received.")

        self.wait_for_event.clear()


class test2SpecificManagerRegistry(unittest.TestCase):
    def setUp(self):

        # ensure that existing test images and containers are removed

        image_container_cleaner(ssm1=True,ssm1_new=True)

        self.srm_proc = Process(target=SpecificManagerRegistry)
        self.srm_proc.daemon = True

        self.nsd1_proc = Process(target=fakeslm)
        self.nsd1_proc.daemon = True

        self.nsd2_proc = Process(target=fakeslmu)
        self.nsd2_proc.daemon = True

        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')
        self.wait_for_event1 = threading.Event()
        self.wait_for_event1.clear()

        self.wait_for_event2 = threading.Event()
        self.wait_for_event2.clear()

    def tearDown(self):
        if self.srm_proc is not None:
            self.srm_proc.terminate()
        del self.srm_proc

        if self.nsd1_proc is not None:
            self.nsd1_proc.terminate()
        del self.nsd1_proc

        if self.nsd2_proc is not None:
            self.nsd2_proc.terminate()
        del self.nsd2_proc

        try:
            self.manoconn.stop_connection()
        except Exception as e:
            LOG.exception("Stop connection exception.")

        del self.wait_for_event1

    def eventFinished1(self):
        self.wait_for_event1.set()

    def waitForEvent1(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event1.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def eventFinished2(self):
        self.wait_for_event2.set()

    def waitForEvent2(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_event2.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def msg_receive_waiting(self, msg, field, timeout):
        c = 0
        while field not in msg.keys() and c < timeout:
            time.sleep(0.1)
            c += 0.1

    def test_smr_features(self):

        def test_on_onboard_receive(ch, method, properties, message):
            msg = yaml.load(str(message))  # , 'utf-8'))
            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'], 'On-boarded')
                LOG.info('SSM on-board test: Passed')

        def test_on_instantiate_receive(ch, method, properties, message):
            msg = yaml.load(str(message))  # , 'utf-8'))
            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'], 'Instantiated')
                LOG.info('SSM instantiation test: Passed')

        def test_on_registration_receive(ch, method, properties, message):
            msg = yaml.load(str(message))  # , 'utf-8'))
            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'], 'running')
                LOG.info('SSM registration into the SMR test: Passed')
                self.nsd1_proc.terminate()
                time.sleep(3)
                self.nsd2_proc.start()
                self.waitForEvent2(timeout=170, msg="message not received.")
                self.eventFinished1()

        def test_on_update_receive(ch, method, properties, message):
            msg = yaml.load(str(message))  # , 'utf-8'))
            self.msg_receive_waiting(msg, 'status', 5)
            if 'status' in msg.keys():
                self.assertEqual(msg['status'],'Updated')
                #self.assertEqual(msg['on-board'], 'OK')
                #self.assertEqual(msg['instantiation'], 'OK')
                #self.assertEqual(msg['status'], 'killed')
                LOG.info('SSM update test: Passed')
                LOG.info('SSM kill test: Passed')
                # stop waiting
                self.eventFinished2()

        self.manoconn.subscribe(test_on_onboard_receive, 'specific.manager.registry.ssm.on-board')
        self.manoconn.subscribe(test_on_instantiate_receive, 'specific.manager.registry.ssm.instantiate')
        self.manoconn.subscribe(test_on_registration_receive, 'specific.manager.registry.ssm.registration')
        self.manoconn.subscribe(test_on_update_receive, 'specific.manager.registry.ssm.update')

        time.sleep(5)
        self.srm_proc.start()


        time.sleep(3)
        self.nsd1_proc.start()

        self.waitForEvent1(timeout=270, msg="message not received.")




class testSMREngine(unittest.TestCase):
    def test_docker_service_connection(self):
        e = SMREngine()
        self.assertIsNotNone(e.dc.info().get("ServerVersion"))

    def test_ssm_onboard(self):
        # ensure that existing test images and containers are removed
        image_container_cleaner(ssm1=True,ssm1_new=False)
        e = SMREngine()
        e.pull(ssm_uri="hadik3r/ssm1", ssm_name='ssm1')
        img = e.dc.get_image('hadik3r/ssm1')
        self.assertIsNotNone(img)

    def test_ssm_instantiate(self):
        # ensure that existing test images and containers are removed
        image_container_cleaner(ssm1=True,ssm1_new=False)
        e = SMREngine()
        e.pull(ssm_uri="hadik3r/ssm1", ssm_name='ssm1')
        e.start(image_name="hadik3r/ssm1", ssm_name='ssm1', host_ip= None)
        con = e.dc.containers(filters={'name': 'ssm1'})
        self.assertIsNotNone(con)

    def test_ssm_kill(self):
        # ensure that existing test images and containers are removed
        image_container_cleaner(ssm1=True,ssm1_new=True)
        e = SMREngine()
        e.pull(ssm_uri="hadik3r/ssm1", ssm_name='ssm1')
        e.start(image_name="hadik3r/ssm1", ssm_name='ssm1', host_ip= None)
        e.stop('ssm1')
        con = e.dc.containers(filters={'name': 'ssm1'})
        self.assertEqual(con, [])


def image_container_cleaner(ssm1, ssm1_new):
    e = SMREngine()
    if ssm1:
        try:
            e.dc.stop('ssm1')
            e.dc.remove_container('ssm1')
        except BaseException as ex:
            pass
        try:
            e.dc.remove_image(force=True, image='hadik3r/ssm1')
        except BaseException as ex:
            pass

    if ssm1_new:
        try:
            e.dc.stop('ssm1_new')
            e.dc.remove_container('ssm1_new')
        except BaseException as ex:
            pass

        try:
            e.dc.remove_image(force=True, image='hadik3r/ssm1_new')
        except BaseException as ex:
            pass


if __name__ == "__main__":
    unittest.main()
