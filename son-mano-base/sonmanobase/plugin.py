"""
Base classed to simplify the implementation of new
MANO plugins.
"""

import logging
import json

import messaging


class ManoBasePlugin(object):

    def __init__(self, blocking=False):
        logging.info(
            "Starting MANO Plugin: %r ..." % self.__class__.__name__)
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.__class__.__name__)
        # register subscriptions
        self.declare_subscriptions()
        # register to plugin manager
        self.register()
        # jump to run()
        self.run()

    def __del__(self):
        # de-register this plugin
        self.deregister()
        p.manoconn.stop_connection()
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

    def register(self):
        """
        Send a register event to the plugin manager component to announce this plugin.
        """
        message = {"type": "REQ",
                   "plugin": self.__class__.__name__,
                   "state": "ACTIVE",
                   "version": "v0.1-dev1"}
        self.manoconn.publish(
            "platform.management.plugins.register", json.dumps(message))

    def heartbeat(self):
        """
        Send a alive notification to the plugin manager.
        """
        logging.debug("Heartbeat.")
        message = {"type": "NOTIFY",
                   "plugin": self.__class__.__name__,
                   "heartbeat": "ALIVE"}
        self.manoconn.publish(
            "platform.management.plugins.heartbeat", json.dumps(message))

    def deregister(self):
        """
        Send a deregister event to the plugin manager component.
        """
        message = {"type": "REQ",
                   "plugin": self.__class__.__name__,
                   "state": "INACTIVE"}
        self.manoconn.publish(
            "platform.management.plugins.deregister", json.dumps(message))

    def callback_print(self, ch, method, properties, body):
        """
        Helper callback that prints the received message.
        """
        logging.debug("RECEIVED from %r on %r: %r" % (
            properties.app_id, method.routing_key, json.loads(body)))

