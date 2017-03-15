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
import yaml
import threading
import logging

from multiprocessing import Process
from son_mano_placement_executive.placementexc import PlacementExecutive
from sonmanobase.messaging import ManoBrokerRequestResponseConnection

logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:plex_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)


class testPLEXRegistration(unittest.TestCase):
    """
    Tests the registration process of the Placement Executive to the broker
    and the plugin manager, and the heartbeat process.
    """

    def setUp(self):
        #a new Placement Executive in another process for each test
        self.plex_proc = Process(target=PlacementExecutive)
        self.plex_proc.daemon = True
        #make a new connection with the broker before each test
        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SonPluginManager')

        #Some threading events that can be used during the tests
        self.wait_for_event = threading.Event()
        self.wait_for_event.clear()

        #The uuid that can be assigned to the plugin
        self.uuid = '1'

    def tearDown(self):
        #Killing the Placement Executive
        if self.plex_proc is not None:
            self.plex_proc.terminate()
        del self.plex_proc

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


    def testPLEXRegistration(self):
        """
        TEST: This test verifies whether the Placement Executive is sending out a message,
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

        #STEP2: Start the Placement Executive
        self.plex_proc.start()

        #STEP3b: When not receiving the message, the test failed 
        self.waitForEvent(timeout=5, msg="message not received.")


if __name__ == '__main__':
    unittest.main()