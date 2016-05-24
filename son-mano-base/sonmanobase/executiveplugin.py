"""
Created by Manuel Peuster <manuel@peuster.de>

Base class of an executive MANO plugin (a plugin that can control FSMs/SSMs).

Main purpose: Provide a simple API to board, start, stop FSMs/SSMs given as Docker containers.
Uses docker-py to control a local or remote Docker environment.
"""

import logging
import json
import time
import threading
import docker
import os

from sonmanobase import plugin, messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-base:executiveplugin")
LOG.setLevel(logging.DEBUG)

# Configuration:
# ENV: DOCKER_HOST -> points to Docker API to be used
ENV_DOCKER_HOST = "DOCKER_HOST"

# Docker machine hint:
# eval $(docker-machine env default)

# TODO doc comments


class ManoBaseExecutivePlugin(plugin.ManoBasePlugin):

    def __init__(self,
                 name="son-plugin",
                 version=None,
                 description=None,
                 auto_register=True,
                 wait_for_registration=True,
                 auto_heartbeat_rate=0.5,
                 auto_docker_connect=True):
        # initialize the base plugin
        super(ManoBaseExecutivePlugin, self).__init__(name,
                                                      version,
                                                      description,
                                                      auto_register,
                                                      wait_for_registration,
                                                      auto_heartbeat_rate)
        # initialize executive plugin
        self.ssmconn = None  # pointer to the ssm message object
        # get the Docker API address
        self.docker_api_address = os.environ.get(ENV_DOCKER_HOST, "/var/run/docker.sock")
        self.dc = None  # docker client object
        # connect to Docker
        if auto_docker_connect:
            self._connect_docker_client()

    def _connect_docker_client(self):
        assert(self.docker_api_address is not None)
        self.dc = docker.Client(base_url=self.docker_api_address)
        LOG.info("Connected to Docker host: %r" % self.docker_api_address)

    def board_ssm(self):
        pass

    def start_ssm(self):
        pass

    def pause_ssm(self):
        pass

    def stop_ssm(self):
        pass

    def on_ssm_register(self):
        pass

    def on_ssm_deregister(self):
        pass


