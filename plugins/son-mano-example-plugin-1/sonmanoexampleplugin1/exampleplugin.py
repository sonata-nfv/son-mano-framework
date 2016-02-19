import logging
import json
import time
import argparse
import sys

sys.path.append("../../../son-mano-base")
from sonmanobase.plugin import ManoBasePlugin


class DemoPlugin1(ManoBasePlugin):

    def __init__(self):
        # call super class to do all the messaging and registration overhead
        super(self.__class__, self).__init__()

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.subscribe(self.on_list_result, "platform.management.plugins.list")
        self.manoconn.subscribe(self.on_deployment_step, "service.management.#")
        self.manoconn.subscribe(self.callback_print, "#")
        time.sleep(1)  # TODO: quick hack: Lets wait a bit until our subscriptions are stable. (should work without with persistence? shouldn't it?

    def on_list_result(self, ch, method, properties, body):
        sender = properties.app_id
        message = json.loads(body)
        if message.get("type") == "REP":
            # we have a reply, lets print it
            print "-" * 20 + " Plugins " + "-" * 20
            for k, v in message.get("plugins").iteritems():
                print "%s, %s, %s" % (k, v.get("version"), v.get("state"))
            print "-" * 49

    def on_deployment_step(self, ch, method, properties, body):
        sender = properties.app_id
        topic = method.routing_key
        message = json.loads(body)
        if "placement.compute" in topic:
            logging.info("NOTIFY: Running placement ...")
        if "onflictresolution.validate" in topic:
            logging.info("NOTIFY: Running conflict resolution ...")
        if "lifecycle.start" in topic:
            logging.info("NOTIFY: Running lifecycle management ...")

    def list_plugins(self):
        # lets have some fun and query the plugin manager for a list of plugins
        self.manoconn.publish("platform.management.plugins.list", json.dumps({"type": "REQ"}))

    def deploy_example(self):
        # trigger deployment workflow of example B
        self.manoconn.publish("service.management.placement.compute", json.dumps(
            {"service": "Service A", "service_chain_graph": "I am a complex service chain."}))

parser = argparse.ArgumentParser(description='plugin1 example interface')
parser.add_argument(
    "command",
    choices=['deploy', 'list'],
    help="Action to be executed.")


def on_sum_response_received(result):
    print "This is the result callback. I received the result: %r" % result


def on_sum_request_received(message):
    message = json.loads(message)
    print "This is the remote endpoint function. I was called with the argument: %r" % message
    time.sleep(2)  # lets wait a bit to fake some computation time.
    return str(message.get("a") + message.get("b"))


def main():
    logging.basicConfig(level=logging.DEBUG)
    p = DemoPlugin1()
    if len(sys.argv) > 1:
        # parse inputs and react accordingly
        args = vars(parser.parse_args(sys.argv[1:]))
        if args.get("command") == "deploy":
            p.deploy_example()
        else:
            p.list_plugins()
    else:
        p.list_plugins()

    # implement a simple example to show how the async request/response pattern can be used
    p.manoconn.register_async_endpoint(on_sum_request_received, "my.cool.topic")
    # give us some time to react
    time.sleep(0.5)
    p.manoconn.call_async(on_sum_response_received, "my.cool.topic", json.dumps({"a" : 1, "b": 2}))
    p.manoconn.call_async(on_sum_response_received, "my.cool.topic", json.dumps({"a" : 999, "b": 888}))
    print "I am printed to show that the calls are asynchronous."
    time.sleep(4)
    p.deregister()

if __name__ == '__main__':
    main()
