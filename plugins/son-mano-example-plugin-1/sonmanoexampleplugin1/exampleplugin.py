"""
Created by Manuel Peuster <manuel@peuster.de>

This is a stupid MANO plugin used for testing.
"""

import logging
import json
import time
import sys
import os

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

    def __del__(self):
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to listen.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()
        # Examples to demonstrate how a plugin can listen to certain events:
        self.manoconn.register_async_endpoint(
            self._on_example_request,  # call back method (expected to return a response message)
            "example.plugin.*.request")
        self.manoconn.register_notification_endpoint(
            self._on_example_notification,  # call back method
            "example.plugin.*.notification")

        # Activate this to sniff and print all messages on the broker
        #self.manoconn.subscribe(self.manoconn.callback_print, "#")

    def run(self):
        """
        Plugin logic. Does nothing in our example.
        """
        # go into infinity loop (we could do anything here)
        while True:
            time.sleep(1)

    def on_registration_ok(self):
        """
        Event that is triggered after a successful registration process.
        """
        logging.info("Registration OK.")

    def on_lifecycle_start(self, properties, message):
        super(self.__class__, self).on_lifecycle_start(properties, message)

        # Example that shows how to send a request/response message
        time.sleep(1)
        self.manoconn.call_async(
                        self._on_example_request_response,
                        "example.plugin.%s.request" % str(self.uuid),
                        json.dumps({"content": "my request"}))
        time.sleep(1)
        # Example that shows how to send a notification message
        self.manoconn.notify(
                        "example.plugin.%s.notification" % str(self.uuid),
                        json.dumps({"content": "my notification"}))

        time.sleep(5)
        os._exit(0)

    def _on_example_request(self, properties, message):
        """
        Only used for the examples.
        """
        print "Example message: %r " % message
        return json.dumps({"content" : "my response"})

    def _on_example_request_response(self, properties, message):
        """
        Only used for the examples.
        """
        print "Example message: %r " % message

    def _on_example_notification(self, properties, message):
        """
        Only used for the examples.
        """
        print "Example message: %r " % message


def main():
    logging.basicConfig(level=logging.INFO)
    DemoPlugin1()

if __name__ == '__main__':
    main()
