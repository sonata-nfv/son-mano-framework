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
import threading
import requests
from multiprocessing import Process
from son_mano_pluginmanager.pluginmanager import SonPluginManager
from sonmanobase.messaging import ManoBrokerRequestResponseConnection


class TestPluginManagerBase(unittest.TestCase):
    """
    Commen functionalities used my many test cases
    """
    pm_proc = None

    @classmethod
    def setUpClass(cls):
        # start the plugin manger in another process so that we can connect to it using its broker interface
        cls.pm_proc = Process(target=SonPluginManager)
        cls.pm_proc.daemon = True
        cls.pm_proc.start()
        time.sleep(1)  # give the plugin manager some time to start

    @classmethod
    def tearDownClass(cls):
        if cls.pm_proc is not None:
            cls.pm_proc.terminate()
            del cls.pm_proc

    def setUp(self):
        # initialize messaging subsystem
        self.m = ManoBrokerRequestResponseConnection("pm-client" + self.id())
        self.wait_for_reply = threading.Event()
        self.plugin_uuid = None

    def tearDown(self):
        self.m.stop_connection()
        self.m.stop_threads()
        del self.m

    def waitForMessage(self, timeout=5):
        self.wait_for_reply.clear()
        if not self.wait_for_reply.wait(timeout):
            raise Exception("Timeout in wait for reply message.")

    def messageReceived(self):
        self.wait_for_reply.set()

    def register(self):
        """
        Helper: We need this in many tests.
        :return:
        """
        def on_register_reply(ch, method, properties, message):
            msg = json.loads(str(message))
            assert(msg.get("status") == "OK")
            assert(len(msg.get("uuid")) > 0)
            assert(msg.get("error") is None)
            # set internal state variables
            self.plugin_uuid = msg.get("uuid")
            # stop waiting
            self.messageReceived()

        # create register request message
        msg = dict(name="test-plugin",
                   version="v0.01",
                   description="description")

        # do the registration call
        self.m.call_async(on_register_reply,
                          "platform.management.plugin.register",
                          json.dumps(msg))

        # make our test synchronous: wait
        self.waitForMessage()

    def deregister(self):
        """
        Helper: We need this in many tests.
        :return:
        """
        assert(self.plugin_uuid is not None)

        def on_deregister_reply(ch, method, properties, message):
            msg = json.loads(str(message))
            assert(msg.get("status") == "OK")
            # stop waiting
            self.messageReceived()

        # create register request message
        msg = dict(uuid=self.plugin_uuid)

        # do the registration call
        self.m.call_async(on_deregister_reply,
                          "platform.management.plugin.deregister",
                          json.dumps(msg))

        # make our test synchronous: wait
        self.waitForMessage()


class TestPluginManagerMessageInterface(TestPluginManagerBase):
    """
    Tests the rabbit mq interface of the the plugin manager by interacting
    with it like a plugin.
    """
    # TODO Add more test cases to cover all functionailites of the interface

    @unittest.skip("skip")
    def testInitialLifecycleStartMessage(self):
        """
        Do registration and check that a lifecycle.start message is sent afterwards.
        :return:
        """
        self.register()

        # callback for status updates
        def on_start_receive(ch, method, properties, message):
            msg = json.loads(str(message))
            assert(len(msg) == 0)
            # stop waiting
            self.messageReceived()

        # create heartbeat message
        msg = dict(uuid=self.plugin_uuid,
                   state="READY")

        # subscribe to status updates
        self.m.subscribe(on_start_receive,
                         "platform.management.plugin.%s.lifecycle.start" % self.plugin_uuid)
        time.sleep(0.5)  # wait to establish subscription

        # send heartbeat with status update to trigger autostart
        self.m.notify("platform.management.plugin.%s.heartbeat" % self.plugin_uuid, json.dumps(msg))

        # make our test synchronous: wait
        self.waitForMessage()

        # de-register
        self.deregister()

    #@unittest.skip("skip")
    def testHeartbeatStatusUpdate(self):
        """
        Do registration and confirm the global status update message that has to be send by the PM.
        :return:
        """

        self.register()

        # callback for status updates
        def on_status_update(ch, method, properties, message):
            msg = json.loads(str(message))
            self.assertTrue(len(msg.get("timestamp")) > 0)
            self.assertTrue(len(msg.get("plugin_dict")) > 0)
            # stop waiting
            self.messageReceived()

        # create heartbeat message
        msg = dict(uuid=self.plugin_uuid,
                   state="READY")

        # subscribe to status updates
        self.m.subscribe(on_status_update,
                         "platform.management.plugin.status")
        time.sleep(0.5)  # wait to establish subscription

        # send heartbeat with status update
        self.m.notify("platform.management.plugin.%s.heartbeat" % self.plugin_uuid, json.dumps(msg))

        # make our test synchronous: wait
        self.waitForMessage()


class TestPluginManagerManagementInterface(TestPluginManagerBase):
    """
    Test the REST management interface of the plugin manager.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.URL = "http://127.0.0.1:8001"

    def testInterfaceConnectivity(self):
        """
        Test if we can access the interface.
        :return:
        """
        r = requests.get("%s/api/plugins" % self.URL)
        self.assertEqual(r.status_code, 200)

    def testGetPluginList(self):
        """
        Test if we can receive a list with plugin uuids.
        :return:
        """
        self.register()
        r = requests.get("%s/api/plugins" % self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()), 1)

    def testGetPluginInfo(self):
        """
        Test if we can receive information about a specific plugin.
        :return:
        """
        self.register()
        r = requests.get("%s/api/plugins/%s" % (self.URL, self.plugin_uuid))
        self.assertEqual(r.status_code, 200)
        p_state = r.json()
        self.assertIn("version", p_state)
        self.assertIn("name", p_state)
        self.assertIn("uuid", p_state)
        self.assertIn("description", p_state)
        self.assertIn("state", p_state)
        self.assertIn("registered_at", p_state)
        self.assertIn("last_heartbeat_at", p_state)

#    def testDeletePlugin(self):
#        """
#        Test if we can request the deletion of a plugin.
#        :return:
#        """
#        self.register()
#        r = requests.delete("%s/api/plugins/%s" % (self.URL, self.plugin_uuid))
#        self.assertEqual(r.status_code, 200)
#        # TODO check that plugin was really removed

    def testPutPluginLifecycle(self):
        """
        Test if we can modify the lifecycle state of a plugin.
        :return:
        """
        self.register()
        req = {"target_state": "pause"}
        r = requests.put("%s/api/plugins/%s/lifecycle" % (self.URL, self.plugin_uuid), json=json.dumps(req))
        self.assertEqual(r.status_code, 200)

    def testPutPluginLifecycleMalformed(self):
        """
        Test if the lifecycle endpoint can handle malformed input data.
        :return:
        """
        self.register()
        req = {"target_state123": "pause"}
        r = requests.put("%s/api/plugins/%s/lifecycle" % (self.URL, self.plugin_uuid), json=json.dumps(req))
        self.assertEqual(r.status_code, 500)


if __name__ == "__main__":
    unittest.main()
