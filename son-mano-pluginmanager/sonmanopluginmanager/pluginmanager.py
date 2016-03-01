"""
Created by Manuel Peuster <manuel@peuster.de>

This is the main module of the plugin manager component.
"""

import logging
import json
import time
import datetime
import uuid
import sys

sys.path.append("../../son-mano-base")
from sonmanobase.plugin import ManoBasePlugin


class SonPluginManager(ManoBasePlugin):
    """
    This is the core of SONATA's plugin manager component.
    All plugins that want to interact with the system have to register
    themselves to it by doing a registration call.
    """

    def __init__(self):
        # plugin management: simple dict for bookkeeping
        self.plugins = {}
        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__(auto_register=False,
                                             auto_heartbeat_rate=0)

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.register_async_endpoint(self._on_register, "platform.management.plugin.register")
        self.manoconn.register_async_endpoint(self._on_deregister, "platform.management.plugin.deregister")
        self.manoconn.register_async_endpoint(self._on_list, "platform.management.plugin.list")
        self.manoconn.register_notification_endpoint(self._on_heartbeat, "platform.management.plugin.*.heartbeat")

    def run(self):
        """
        Just go into an endless loop and wait for new plugins.
        """
        while True:
            time.sleep(1)  # lets block for now

    def _on_register(self, properties, message):
        """
        Event method that is called when a registration request is received.
        Registers the new plugin in the internal data model and returns
        a fresh UUID that is used to identify it.
        :param properties: request properties
        :param message: request body
        :return: response message
        """
        message = json.loads(message)
        pid = str(uuid.uuid4())
        # simplified example for plugin bookkeeping (replace this with real functionality)
        self.plugins[pid] = message
        # add some fields to record
        self.plugins[pid]["state"] = "REGISTERED"
        self.plugins[pid]["resgister_time"] = str(datetime.datetime.now())
        self.plugins[pid]["last_heartbeat"] = None
        logging.info("REGISTERED: %r with UUID %r" % (message.get("name"), pid))
        # return result
        response = {
            "status": "OK",
            "uuid": pid,
            "error": None
        }
        return json.dumps(response)

    def _on_deregister(self, properties, message):
        """
        Event method that is called when a de-registration request is received.
        Removes the given plugin from the internal data model.
        :param properties: request properties
        :param message: request body (contains UUID to identify plugin)
        :return: response message
        """
        message = json.loads(message)
        # simplified example for plugin bookkeeping
        if message.get("uuid") in self.plugins:
            del self.plugins[message.get("uuid")]
        logging.info("DE-REGISTERED: %r" % properties.app_id)
        # return result
        response = {
            "status" : "OK"
        }
        return json.dumps(response)

    def _on_list(self, properties, message):
        """
        Event method that is called when a plugin wants to request a
        list of all plugins that are currently registered to the system.
        :param properties: request properties
        :param message: request body
        :return: response message
        """
        # generate result
        response = {"status": "OK",
                    "list": self.plugins,
                    "error": None}
        logging.info("LIST requested by: %r" % properties.app_id)
        # return result
        return json.dumps(response)

    def _on_heartbeat(self, properties, message):
        message = json.loads(message)
        pid = message.get("uuid")
        if pid in self.plugins:
            self.plugins[pid]["last_heartbeat"] = str(datetime.datetime.now())


def main():
    logging.basicConfig(level=logging.DEBUG)
    SonPluginManager()

if __name__ == '__main__':
    main()
