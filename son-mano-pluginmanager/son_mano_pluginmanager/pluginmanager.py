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

"""
This is the main module of the plugin manager component.
"""
import logging
import json
import datetime
import yaml
import uuid
import os
import time
from mongoengine import DoesNotExist

from sonmanobase.plugin import ManoBasePlugin
from son_mano_pluginmanager import model
from son_mano_pluginmanager import interface

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-pluginmanger")
LOG.setLevel(logging.INFO)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class SonPluginManager(ManoBasePlugin):
    """
    This is the core of SONATA's plugin manager component.
    All plugins that want to interact with the system have to register
    themselves to it by doing a registration call.
    """

    def __init__(self):
        # initialize plugin DB model
        model.initialize()

        # start up management interface
        interface.start(self)

        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__(auto_register=False,
                                             auto_heartbeat_rate=0)

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.subscribe(self._on_register, "platform.management.plugin.register")
        self.manoconn.subscribe(self._on_deregister, "platform.management.plugin.deregister")
        self.manoconn.register_notification_endpoint(self._on_heartbeat, "platform.management.plugin.*.heartbeat")

    def _send_lifecycle_notification(self, plugin, operation):
        """
        Send lifecycle.X notification to given plugin.
        :param plugin: plugin object
        :param operation: operation string, e.g., start/pause/stop
        :return:
        """
        self.manoconn.notify(
            "platform.management.plugin.%s.lifecycle.%s" % (str(plugin.uuid), str(operation)))

    def send_start_notification(self, plugin):
        self._send_lifecycle_notification(plugin, "start")

    def send_stop_notification(self, plugin):
        self._send_lifecycle_notification(plugin, "stop")

    def send_pause_notification(self, plugin):
        self._send_lifecycle_notification(plugin, "pause")

    def send_plugin_status_update(self):
        """
        Broadcast a plugin status update message to all interested plugins.
        The message always contains the entire list of registered plugins as well
        as status information for each of these plugins.
        This method should always be called when the status of a plugin changes.
        """
        # generate status update message
        plugin_dict = {}
        for p in model.Plugin.objects:
            plugin_dict[p.uuid] = p.to_dict()
        # create correct message format
        message = {"timestamp": str(datetime.datetime.now()),
                    "plugin_dict": plugin_dict}
        LOG.info("Broadcasting plugin status update to 'platform.management.plugin.status': %r" % message)
        # broadcast plugin status update message
        self.manoconn.notify(
            "platform.management.plugin.status", json.dumps(message))

    def _on_register(self, ch, method, properties, message):
        """
        Event method that is called when a registration request is received.
        Registers the new plugin in the internal data model and returns
        a fresh UUID that is used to identify it.
        :param properties: request properties
        :param message: request body
        :return: response message
        """

        #Don't trigger on messages coming from the PM
        if properties.app_id == self.name:
            return

        message = json.loads(str(message))
        pid = str(uuid.uuid4())
        # create a entry in our plugin database
        p = model.Plugin(
            uuid=pid,
            name=message.get("name"),
            version=message.get("version"),
            description=message.get("description"),
            state="REGISTERED"
        )

        p.save()
        LOG.info("REGISTERED: %r" % p)
        # return result
        response = {
            "status": "OK",
            "name": p.name,
            "version": p.version,
            "description": p.description,
            "uuid": pid,
            "error": None
        }
        self.manoconn.notify(
            'platform.management.plugin.register', json.dumps(response), correlation_id=properties.correlation_id)
        # broadcast a plugin status update to the other plugin
        self.send_plugin_status_update()

    def _on_deregister(self, ch, method, properties, message):
        """
        Event method that is called when a de-registration request is received.
        Removes the given plugin from the internal data model.
        :param properties: request properties
        :param message: request body (contains UUID to identify plugin)
        :return: response message
        """
        message = json.loads(str(message))

        try:
            p = model.Plugin.objects.get(uuid=message.get("uuid"))
            p.delete()
        except DoesNotExist:
            LOG.debug("Couldn't find plugin with UUID %r in DB" % pid)

        LOG.info("DE-REGISTERED: %r" % message.get("uuid"))
        # broadcast a plugin status update to the other plugin
        self.send_plugin_status_update()
        # return result
        response = {
            "status": "OK"
        }
        return json.dumps(response)

    def _on_heartbeat(self, ch, method, properties, message):
        message = json.loads(str(message))
        pid = message.get("uuid")

        try:
            p = model.Plugin.objects.get(uuid=pid)

            # update heartbeat timestamp
            p.last_heartbeat_at = datetime.datetime.now()

            change = False

            # TODO ugly: state management of plugins should be hidden with plugin class
            if message.get("state") == "READY" and p.state != "READY":
                # a plugin just announced that it is ready, lets start it
                self.send_start_notification(p)
                change = True
            elif message.get("state") != p.state:
                # lets keep track of the reported state update
                p.state = message.get("state")
                change = True

            p.save()
            if change:
                # there was a state change lets schedule an plugin status update notification
                self.send_plugin_status_update()
        except DoesNotExist:
            LOG.debug("Couldn't find plugin with UUID %r in DB" % pid)


def main():
    SonPluginManager()

if __name__ == '__main__':
    main()
