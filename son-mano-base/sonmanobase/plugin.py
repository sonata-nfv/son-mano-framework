"""
Created by Manuel Peuster <manuel@peuster.de>

Base class to simplify the implementation of new MANO plugins.
"""

import logging
import json
import time
import threading

from sonmanobase import messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-base:plugin")
LOG.setLevel(logging.DEBUG)


class ManoBasePlugin(object):
    """
    Abstract class that should be inherited by other MANO plugins.
    This class provides basic mechanisms to
    - connect to the broker
    - send/receive async/sync request/response calls
    - send/receive notifications
    - register / de-register plugin to plugin manager

    It also implements a automatic heartbeat mechanism that periodically sends
    heartbeat notifications.
    """

    def __init__(self,
                 name="son-plugin",
                 version=None,
                 description=None,
                 auto_register=True,
                 wait_for_registration=True,
                 auto_heartbeat_rate=0.5):
        """
        Performs plugin initialization steps, e.g., connection setup
        :param name: Plugin name prefix
        :param version: Plugin version
        :param description: A description string
        :param auto_register: Automatically register on init
        :param wait_for_registration: Wait for registration before returning from init
        :param auto_heartbeat_rate: rate of automatic heartbeat notifications 1/n seconds. 0=deactivated
        :return:
        """
        self.name = "%s.%s" % (name, self.__class__.__name__)
        self.version = version
        self.description = description
        self.uuid = None  # uuid given by plugin manager on registration
        self.state = None  # the state of this plugin READY/RUNNING/PAUSED/FAILED

        LOG.info(
            "Starting MANO Plugin: %r ..." % self.name)
        # create and initialize broker connection
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)
        # register subscriptions
        self.declare_subscriptions()
        # register to plugin manager
        if auto_register:
            self.register()
            if wait_for_registration:
                self._wait_for_registration()
        # add additional subscriptions
        self._register_lifecycle_endpoints()
        # kick-off automatic heartbeat mechanism
        self._auto_heartbeat(auto_heartbeat_rate)
        # jump to run
        self.run()

    def __del__(self):
        """
        Actions done when plugin is destroyed.
        :return:
        """
        # de-register this plugin
        self.deregister()
        self.manoconn.stop_connection()
        del self.manoconn

    def _auto_heartbeat(self, rate):
        """
        A simple periodic heartbeat mechanism.
        (much room for improvements here)
        :param rate: rate of heartbeat notifications
        :return:
        """
        if rate <= 0:
            return

        def run():
            while True:
                if self.uuid is not None:
                    self._send_heartbeat()
                time.sleep(1/rate)

        # run heartbeats in separated thread
        t = threading.Thread(target=run)
        t.daemon = True
        t.start()

    def _send_heartbeat(self):
        self.manoconn.notify(
            "platform.management.plugin.%s.heartbeat" % str(self.uuid),
            json.dumps({"uuid": self.uuid,
            "state": str(self.state)}))

    def declare_subscriptions(self):
        """
        Can be overwritten by subclass.
        But: The this superclass method should be called in any case.
        """
        # plugin status update subscription
        self.manoconn.register_notification_endpoint(
            self.on_plugin_status_update,  # call back method
            "platform.management.plugin.status")

    def run(self):
        """
        To be overwritten by subclass
        """
        pass

    def on_lifecycle_start(self, properties, message):
        """
        To be overwritten by subclass
        """
        LOG.info("Received lifecycle.start event.")
        self.state = "RUNNING"

    def on_lifecycle_pause(self, properties, message):
        """
        To be overwritten by subclass
        """
        LOG.info("Received lifecycle.pause event.")
        self.state = "PAUSED"

    def on_lifecycle_stop(self, properties, message):
        """
        To be overwritten by subclass
        """
        LOG.info("Received lifecycle.stop event.")
        self.deregister()
        exit(0)

    def on_registration_ok(self):
        """
        To be overwritten by subclass
        """
        pass

    def on_plugin_status_update(self, properties, message):
        """
        To be overwritten by subclass.
        Called when a plugin list status update
        is received from the plugin manager.
        """
        LOG.info("Received plugin status update %r." % str(message))

    def register(self):
        """
        Send a register request to the plugin manager component to announce this plugin.
        """
        message = {"name": self.name,
                   "version": self.version,
                   "description": self.description}
        self.manoconn.call_async(self._on_register_response,
                                 "platform.management.plugin.register",
                                 json.dumps(message))

    def _on_register_response(self, props, response):
        """
        Event triggered when register response is received.
        :param props: response properties
        :param response: response body
        :return: None
        """
        response = json.loads(str(response, "utf-8"))
        if response.get("status") != "OK":
            LOG.debug("Response %r" % response)
            LOG.error("Plugin registration failed. Exit.")
            exit(1)
        self.uuid = response.get("uuid")
        # mark this plugin to be ready to be started
        self.state = "READY"
        LOG.info("Plugin registered with UUID: %r" % response.get("uuid"))
        # jump to on_registration_ok()
        self.on_registration_ok()
        self._send_heartbeat()

    def deregister(self):
        """
        Send a deregister event to the plugin manager component.
        """
        LOG.info("De-registering plugin...")
        message = {"uuid": self.uuid}
        self.manoconn.call_async(self._on_deregister_response,
                                 "platform.management.plugin.deregister",
                                 json.dumps(message))

    def _on_deregister_response(self, props, response):
        """
        Event triggered when de-register response is received.
        :param props: response properties
        :param response: response body
        :return: None
        """
        response = json.loads(str(response, "utf-8"))
        if response.get("status") != "OK":
            LOG.error("Plugin de-registration failed. Exit.")
            exit(1)
        LOG.info("Plugin de-registered.")

    def _wait_for_registration(self, timeout=5, sleep_interval=0.1):
        """
        Method to do active waiting until the registration is completed.
        (not nice, but ok for now)
        :param timeout: max wait
        :param sleep_interval: sleep interval
        :return: None
        """
        # FIXME: Use threading.Event() for this?
        c = 0
        LOG.debug("Waiting for registration (timeout=%d) ..." % timeout)
        while self.uuid is None and c < timeout:
            time.sleep(sleep_interval)
            c += sleep_interval

    def _register_lifecycle_endpoints(self):
        if self.uuid is not None:
            # lifecycle.start
            self.manoconn.register_notification_endpoint(
                self.on_lifecycle_start,  # call back method
                "platform.management.plugin.%s.lifecycle.start" % str(self.uuid))
            # lifecycle.pause
            self.manoconn.register_notification_endpoint(
                self.on_lifecycle_pause,  # call back method
                "platform.management.plugin.%s.lifecycle.pause" % str(self.uuid))
            # lifecycle.stop
            self.manoconn.register_notification_endpoint(
                self.on_lifecycle_stop,  # call back method
                "platform.management.plugin.%s.lifecycle.stop" % str(self.uuid))
