"""
Created by Manuel Peuster <manuel@peuster.de>

This is the main module of the plugin manager component.
"""

# TODO encapsulate plugin objects in a class
# TODO make plugin registration state persistant in a DB (Mongo?)

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
        self.manoconn.register_notification_endpoint(self._on_heartbeat, "platform.management.plugin.*.heartbeat")

    def run(self):
        """
        Just go into an endless loop and wait for new plugins.
        """
        while True:
            time.sleep(1)  # lets wait and do nothing

    def send_start_notification(self, plugin):
        """
        Send lifecycle.start notification to given plugin.
        :param plugin:
        :return:
        """
        self.manoconn.notify(
            "platform.management.plugin.%s.lifecycle.start" % str(plugin.get("uuid")))

    def send_plugin_status_update(self):
        """
        Broadcast a plugin status update message to all interested plugins.
        The message always contains the entire list of registered plugins as well
        as status information for each of these plugins.
        This method should always be called when the status of a plugin changes.
        """
        # generate status update message
        message = {"timestamp": str(datetime.datetime.now()),
                    "plugin_dict": self.plugins}
        # broadcast plugin status update message
        self.manoconn.notify(
            "platform.management.plugin.status", json.dumps(message))

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
        self.plugins[pid]["uuid"] = pid
        self.plugins[pid]["state"] = "REGISTERED"
        self.plugins[pid]["resgister_time"] = str(datetime.datetime.now())
        self.plugins[pid]["last_heartbeat"] = None
        self.plugins[pid]["started"] = False
        logging.info("REGISTERED: %r with UUID %r" % (message.get("name"), pid))
        # broadcast a plugin status update to the other plugin
        self.send_plugin_status_update()
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
        # broadcast a plugin status update to the other plugin
        self.send_plugin_status_update()
        # return result
        response = {
            "status": "OK"
        }
        return json.dumps(response)

    def _on_heartbeat(self, properties, message):
        message = json.loads(message)
        pid = message.get("uuid")

        if pid in self.plugins:
            self.plugins[pid]["last_heartbeat"] = str(datetime.datetime.now())
            # TODO ugly: state management of plugins should be hidden with plugin class
            if message.get("state") == "READY" and self.plugins[pid]["state"] != "READY":
                # a plugin just announced that it is ready, lets start it
                self.send_start_notification(self.plugins[pid])
            elif message.get("state") != self.plugins[pid]["state"]:
                # lets keep track of the reported state update
                self.plugins[pid]["state"] = message.get("state")
                # there was a state change lets schedule an plugin status update notification
                self.send_plugin_status_update()


def main():
    logging.basicConfig(level=logging.DEBUG)
    SonPluginManager()

if __name__ == '__main__':
    main()
