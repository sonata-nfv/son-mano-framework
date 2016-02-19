"""
Created by Manuel Peuster <manuel@peuster.de>

This is a stupid MANO plugin used for testing.
"""

import logging
import json
import time
import sys

sys.path.append("../../../son-mano-base")
from sonmanobase.plugin import ManoBasePlugin


class DemoPlugin1(ManoBasePlugin):
    """
    This is a very simple example plugin to demonstrate
    some APIs.

    It does the following:
    1. registers itself to the plugin manager
    2. waits some seconds
    3. requests a list of active plugins from the plugin manager and prints it
    4. de-registers itself
    """

    def __init__(self):
        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__(version="0.1-dev")

    def declare_subscriptions(self):
        """
        Declare topics to listen.
        """
        pass
        # Activate this to sniff and print all messages on the broker
        #self.manoconn.subscribe(self.manoconn.callback_print, "#")

    def run(self):
        """
        Plugin logic. Does nothing in our example.
        """
        # do nothing and waste time
        time.sleep(5)

    def on_registration_ok(self):
        """
        Event that is triggered after a successful registration process.
        """
        # Wait a bit for a nicer presentation
        time.sleep(1)
        print "Requesting plugin list from SonPluginManager..."
        # Lets request the list of active plugins from the plugin manager
        self.list_plugins()

    def list_plugins(self):
        """
        Request the list of active plugins from the plugin manager.
        :return:
        """
        message = {"filter": None}
        self.manoconn.call_async(self._on_list_response,
                                 "platform.management.plugin.list",
                                 json.dumps(message))

    def _on_list_response(self, props, response):
        """
        Event that is triggered when the response of the list request arrives.
        :param props: response properties
        :param response: response body
        :return:
        """
        print "Received plugin list:"
        sender = props.app_id
        response = json.loads(response)
        if response.get("status") == "OK":
            # we have a reply, lets print it
            print "-" * 30 + " Plugins " + "-" * 30
            for k, v in response.get("list").iteritems():
                print "%s, %s, %s" % (k, v.get("name"), v.get("version"))
            print "-" * 69
        else:
            print "List request error."


def main():
    logging.basicConfig(level=logging.INFO)
    DemoPlugin1()

if __name__ == '__main__':
    main()
