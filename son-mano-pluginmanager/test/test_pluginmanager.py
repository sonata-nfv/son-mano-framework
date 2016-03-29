import unittest
import time
import json
import threading
from multiprocessing import Process
from son_mano_pluginmanager.pluginmanager import SonPluginManager
from sonmanobase.messaging import ManoBrokerRequestResponseConnection


class TestPluginManagerMessageInterface(unittest.TestCase):
    """
    Tests the rabbit mq interface of the the plugin manager by interacting
    with it like a plugin.
    """
    # TODO Add more test cases to cover all functionailites of the interface
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
            msg = json.loads(str(message, "utf-8"))
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
            msg = json.loads(str(message, "utf-8"))
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

    #@unittest.skip("skip")
    def testInitialLifecycleStartMessage(self):
        """
        Do registration and check that a lifecycle.start message is sent afterwards.
        :return:
        """
        self.register()

        # callback for status updates
        def on_start_receive(ch, method, properties, message):
            msg = json.loads(str(message, "utf-8"))
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
            msg = json.loads(str(message, "utf-8"))
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


if __name__ == "__main__":
    unittest.main()
