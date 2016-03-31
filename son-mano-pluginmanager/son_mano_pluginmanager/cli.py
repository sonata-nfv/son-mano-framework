"""
This module implements a simple command line tool that wraps the REST management interface of son-plugin-manager.
"""
import argparse
import requests
import json


def plugin_list(endpoint):
    r = requests.get("%s/api/plugins" % endpoint)
    if r.status_code != 200:
        _request_failed(r.status_code)
    print(r.json())


def plugin_info(uuid, endpoint):
    r = requests.get("%s/api/plugins/%s" % (endpoint, uuid))
    if r.status_code != 200:
        _request_failed(r.status_code)
    print(r.json())


def plugin_remove(uuid, endpoint):
    r = requests.delete("%s/api/plugins/%s" % (endpoint, uuid))
    if r.status_code != 200:
        _request_failed(r.status_code)
    print(r.json())


def plugin_lifecycle_start(uuid, endpoint):
    req = {"target_state": "start"}
    r = requests.put("%s/api/plugins/%s/lifecycle" % (endpoint, uuid),
                     json=json.dumps(req))
    if r.status_code != 200:
        _request_failed(r.status_code)
    print(r.json())


def plugin_lifecycle_pause(uuid, endpoint):
    req = {"target_state": "pause"}
    r = requests.put("%s/api/plugins/%s/lifecycle" % (endpoint, uuid),
                     json=json.dumps(req))
    if r.status_code != 200:
        _request_failed(r.status_code)
    print(r.json())


def plugin_lifecycle_stop(uuid, endpoint):
    req = {"target_state": "stop"}
    r = requests.put("%s/api/plugins/%s/lifecycle" % (endpoint, uuid),
                     json=json.dumps(req))
    if r.status_code != 200:
        _request_failed(r.status_code)
    print(r.json())


def _argument_missing(arg="UUID"):
    print("Error: Missing argument %r." % arg)
    print("Run with --help to get more info.")
    print("Abort.")
    exit(0)


def _request_failed(code):
    print("Request failed with code %r." % code)
    print("Abort.")
    exit(0)


parser = argparse.ArgumentParser(description='son-pm-cli')
parser.add_argument(
    "command",
    choices=['list', 'info', 'remove', 'lifecycle-start', 'lifecycle-pause', 'lifecycle-stop'],
    help="Action to be executed.")
parser.add_argument(
    "--uuid", "-u", dest="uuid",
    help="UUID of the plugin to be manipulated.")
parser.add_argument(
    "--endpoint", "-e", dest="endpoint",
    default="http://127.0.0.1:8001",
    help="UUID of the plugin to be manipulated.")


def main():
    args = vars(parser.parse_args())
    # basic input checks
    if args.get("command") != "list" and args.get("uuid") is None:
        _argument_missing()
    # call command functions (yeah, static mapping is not nice, I know)
    if args.get("command") == "list":
        plugin_list(args.get("endpoint"))
    elif args.get("command") == "info":
        plugin_info(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "remove":
        plugin_remove(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "lifecycle-start":
        plugin_lifecycle_start(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "lifecycle-pause":
        plugin_lifecycle_pause(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "lifecycle-stop":
        plugin_lifecycle_stop(args.get("uuid"), args.get("endpoint"))


if __name__ == '__main__':
    main()
