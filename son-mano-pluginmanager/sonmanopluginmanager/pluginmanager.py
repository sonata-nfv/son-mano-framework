import logging
import json
import time
import sys

sys.path.append("../../son-mano-base")
from sonmanobase.plugin import ManoBasePlugin


class SonPluginManager(ManoBasePlugin):

    def __init__(self):
        # plugin management: simple dict for bookkeeping
        self.plugins = {}
        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__()

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.subscribe(self.on_register, "platform.management.plugins.register")
        self.manoconn.subscribe(self.on_deregister, "platform.management.plugins.deregister")
        self.manoconn.subscribe(self.on_list, "platform.management.plugins.list")
        self.manoconn.subscribe(self.callback_print, "platform.management.plugins.heartbeat")
        self.manoconn.subscribe(self.callback_print, "#")
        time.sleep(1)  # TODO: quick hack: Lets wait a bit until our subscriptions are stable. (should work without with persistence? shouldn't it?

    def run(self):
        while True:
            time.sleep(1)  # lets block for now

    def on_register(self, ch, method, properties, body):
        sender = properties.app_id
        message = json.loads(body)
        # simplified example for plugin bookkeeping
        self.plugins[message.get("plugin")] = message
        logging.info("REGISTERED: %r" % message.get("plugin"))

    def on_deregister(self, ch, method, properties, body):
        sender = properties.app_id
        message = json.loads(body)
        # simplified example for plugin bookkeeping
        self.plugins[sender] = message
        logging.info("DE-REGISTERED: %r" % message.get("plugin"))

    def on_list(self, ch, method, properties, body):
        sender = properties.app_id
        message = json.loads(body)
        if message.get("type") == "REQ":
            # we have a request, lets answer
            message = {"type": "REP",
                       "plugins": self.plugins}
            self.manoconn.publish("platform.management.plugins.list", json.dumps(message))


def main():
    logging.basicConfig(level=logging.DEBUG)
    spm = SonPluginManager()

if __name__ == '__main__':
    main()
