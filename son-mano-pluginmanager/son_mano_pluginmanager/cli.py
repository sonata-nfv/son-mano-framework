"""
This module implements a simple command line tool that wraps the REST management interface of son-plugin-manager.
"""
import argparse
import requests


def list(endpoint):
    print("list %r" % endpoint)


def info(uuid, endpoint):
    print("info %r %r" % (uuid, endpoint))


def remove(uuid, endpoint):
    print("remove %r %r" % (uuid, endpoint))


def lifecycle_start(uuid, endpoint):
    print("lifecycle_start %r %r" % (uuid, endpoint))


def lifecycle_pause(uuid, endpoint):
    print("lifecycle_pause %r %r" % (uuid, endpoint))


def lifecycle_stop(uuid, endpoint):
    print("lifecycle_stop %r %r" % (uuid, endpoint))

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
    if args.get("command") == "list":
        list(args.get("endpoint"))
    elif args.get("command") == "info":
        info(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "remove":
        remove(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "lifecycle-start":
        lifecycle_start(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "lifecycle-pause":
        lifecycle_pause(args.get("uuid"), args.get("endpoint"))
    elif args.get("command") == "lifecycle-stop":
        lifecycle_stop(args.get("uuid"), args.get("endpoint"))

if __name__ == '__main__':
    main()
