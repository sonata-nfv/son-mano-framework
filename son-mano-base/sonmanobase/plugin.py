"""
Created by Manuel Peuster <manuel@peuster.de>

Base class to simplify the implementation of new MANO plugins.
"""

import logging
import json
import time

import messaging


class ManoBasePlugin(object):
    """
    Abstract class that should be inherited by other MANO plugins.
    This class provides basic mechanisms to
    - connect to the broker
    - send/receive async/sync request/response calls
    - send/receive notifications
    - register / de-register plugin to plugin manager
    """

    def __init__(self,
                 name="son-plugin",
                 version=None,
                 description=None,
                 auto_register=True,
                 wait_for_registration=True):
        """
        Performs plugin initialization steps, e.g., connection setup
        :param name: Plugin name prefix
        :param version: Plugin version
        :param description: A description string
        :param auto_register: Automatically register on init
        :param wait_for_registration: Wait for registration before returning from init
        :return:
        """
        self.name = "%s.%s" % (name, self.__class__.__name__)
        self.version = version
        self.description = description
        self.uuid = None # uuid given by plugin manager on registration

        logging.info(
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

    def declare_subscriptions(self):
        """
        To be overwritten by subclass
        """
        pass

    def run(self):
        """
        To be overwritten by subclass
        """
        pass

    def on_registration_ok(self):
        """
        To be overwritten by subclass
        """
        pass

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
        response = json.loads(response)
        if response.get("status") != "OK":
            logging.error("Plugin registration failed. Exit.")
            exit(1)
        self.uuid = response.get("uuid")
        logging.info("Plugin registered with UUID: %r" % response.get("uuid"))
        # jump to on_registration_ok()
        self.on_registration_ok()

    def deregister(self):
        """
        Send a deregister event to the plugin manager component.
        """
        logging.info("De-registering plugin...")
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
        response = json.loads(response)
        if response.get("status") != "OK":
            logging.error("Plugin de-registration failed. Exit.")
            exit(1)
        logging.info("Plugin de-registered.")

    def _wait_for_registration(self, timeout=5, sleep_interval=0.1):
        """
        Method to do active waiting until the registration is completed.
        (not nice, but ok for now)
        :param timeout: max wait
        :param sleep_interval: sleep interval
        :return: None
        """
        c = 0
        logging.debug("Waiting for registration (timeout=%d) ..." % timeout)
        while self.uuid is None and c < timeout:
            time.sleep(sleep_interval)
            c += sleep_interval
