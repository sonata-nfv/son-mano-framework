"""
 Copyright 2015-2017 Paderborn University

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import logging
import docker
import os
import json
from sonmanobase import plugin, messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-base:executiveplugin")
LOG.setLevel(logging.DEBUG)


class SsmNotFoundException(BaseException):
    pass


class ManoBaseExecutivePlugin(plugin.ManoBasePlugin):
    """
    Abstract class of a MANO executive plugin that can be customized by a FSM/SSM.
    It provides basic methods to board, start, stop, remove FSMs/SSMs that are given
    as Docker images.

    To do so, an executive plugin needs a connection to a Docker instance in which the
    FSMs/SSMs should be executed. The Docker API credentials can be configured with
    environment variables.
    """
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
        self.dc = None  # docker client object
        # connect to Docker
        if auto_docker_connect:
            self.dc = self._connect_docker_client()

    def _connect_docker_client(self):
        """
        Connect to a Docker service on which FSMs/SSMs shall be executed.
        The connection information for this service should be specified with the following
        environment variables (example for a docker machine installation):

            export DOCKER_TLS_VERIFY="1"
            export DOCKER_HOST="tcp://192.168.99.100:2376"
            export DOCKER_CERT_PATH="/Users/<user>/.docker/machine/machines/default"
            export DOCKER_MACHINE_NAME="default"

            Docker machine hint: eval $(docker-machine env default) sets all needed ENV variables.

        If DOCKER_HOST is not set, the default local Docker socket will be tried.
        :return: client object
        """
        # lets check if Docker ENV information is set and use local socket as fallback
        if os.environ.get("DOCKER_HOST") is None:
            os.environ["DOCKER_HOST"] = "unix://var/run/docker.sock"
            LOG.warning("ENV variable 'DOCKER_HOST' not set. Using %r as fallback." % os.environ["DOCKER_HOST"])

        # lets connect to the Docker instance specified in current ENV
        # cf.: http://docker-py.readthedocs.io/en/stable/machine/
        dc = docker.from_env(assert_hostname=False)
        # do a call to ensure that we are connected
        dc.info()
        LOG.info("Connected to Docker host: %r" % dc.base_url)
        return dc

    def board_ssm(self, ssm_uri):
        """
        Process of pulling / importing a SSM given as Docker image.

        SSM can be specified like:
        - ssm_uri = "registry.sonata-nfv.eu:5000/my-ssm" -> Docker PULL (opt B)
        or
        - ssm_uri = "file://this/is/a/path/my-ssm.tar" -> Docker LOAD (opt A)
        :return: ssm_image_name
        """
        if "file://" in ssm_uri:
            # opt A: file based import
            try:
                ssm_path = ssm_uri.replace("file://", "")
                ssm_image_name = os.path.splitext(os.path.basename(ssm_path))[0]
                r = self.dc.import_image(src=ssm_path, repository=ssm_image_name)
                if "error" in r:
                    raise SsmNotFoundException("Import error.")
                return ssm_image_name
            except SsmNotFoundException as ex:
                LOG.error("Cannot import SSM from %r" % ssm_uri)
        else:
            # opt B: repository pull
            try:
                r = self.dc.pull(ssm_uri)
                if "error" in r:
                    raise SsmNotFoundException()
                return ssm_uri  # image name and uri are the same
            except SsmNotFoundException as ex:
                LOG.error("Cannot pull SSM from %r" % ssm_uri)
        return None

    def start_ssm(self, ssm_image):
        """
        Runs the given SSM container image.
        The code in the container should connect itself to the message broker
        given by ENV vars to it (TODO add argument vars for this).

        Method has to return the ID of the running container (ssm_id) as reference.

        :param ssm_image:
        :return: ssm_id
        """
        pass

    def stop_ssm(self, ssm_id):
        """
        Corresponds to docker kill <container id>
        :param ssm_id:
        :return:
        """
        pass

    def remove_ssm(self, ssm_image):
        """
        Corresponds to docker rm <image id>
        :param ssm_id:
        :return:
        """
        pass

    def on_ssm_register(self):
        pass

    def on_ssm_deregister(self):
        pass


