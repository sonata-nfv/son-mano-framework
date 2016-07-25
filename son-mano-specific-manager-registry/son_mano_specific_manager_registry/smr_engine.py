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
'''
This is the SMR engine module.
'''

import logging
import os
import docker

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-specific-manager-registry")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class SsmNotFoundException(BaseException):
    pass

class SMREngine(object):

    def __init__(self):
        self.dc = self.connect()

    def connect(self):
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

    def pull(self, ssm_uri, ssm_name):

        """
        Process of pulling / importing a SSM given as Docker image.

        SSM can be specified like:
        - ssm_uri = "registry.sonata-nfv.eu:5000/my-ssm" -> Docker PULL (opt B)
        or
        - ssm_uri = "file://this/is/a/path/my-ssm.tar" -> Docker LOAD (opt A)
        :return: ssm_image_name
        """
        response = {}
        img = None

        if "file://" in ssm_uri:
            # opt A: file based import
            try:
                ssm_path = ssm_uri.replace("file://", "")
                ssm_image_name = os.path.splitext(os.path.basename(ssm_path))[0]
                img = self.dc.images(name= ssm_uri)
                if len(img) != 0:
                    self.dc.remove_image(force=True, image = ssm_uri)
                r = self.dc.import_image(ssm_path, repository=ssm_image_name)
                if "error" in r:
                    raise SsmNotFoundException("Import error: %r" % r)
                LOG.debug("%r pull done" % ssm_name)
                response = {'on-board':'OK'}
            except BaseException as ex:
                LOG.exception("Cannot import SSM from %r" % ssm_uri)
                response= {'on-board':'failed'}
        else:
            # opt B: repository pull
            try:
                img = self.dc.images(name= ssm_uri)
                if len(img) != 0:
                    self.dc.remove_image(force=True, image = ssm_uri)
                r = self.dc.pull(ssm_uri)
                if "error" in r:
                    raise SsmNotFoundException("Pull error: %r" % r)
                LOG.info("%r pull done" % ssm_name)
                response = {'on-board':'OK'}  # image name and uri are the same
            except BaseException as ex:
                LOG.exception("Cannot pull SSM from %r" % ssm_uri)
                response = {'on-board':'failed'}
        return response

    def start(self,image_name,ssm_name):
        response = {}
        container = None
        try:
            con = None
            con = self.dc.containers(all= True, filters={'name':ssm_name})
            if len(con) != 0:
                LOG.info('waiting for instantiation')
                self.dc.stop(ssm_name)
                self.dc.remove_container(ssm_name)
            container = self.dc.create_container(image=image_name , tty=True, name=ssm_name)
            self.dc.start(container=container.get('Id'), links=[('broker', 'broker')])
            LOG.debug("%r instantiation done" % ssm_name)
            response = {'instantiation':'OK'}
        except BaseException as ex:
            LOG.exception("Cannot instantiate SSM: %r" % image_name)
            response = {'instantiation': 'failed'}
        response = {'instantiation':'OK', 'container': container.get('Id')}
        return response

    def stop(self,ssm_name):
        try:
            self.dc.kill(ssm_name)
            response = 'done'
            LOG.debug('kill ssm1 done')
        except BaseException as ex:
            LOG.exception('Cannot stop %s' % ssm_name)
            response = 'failed'
        return response
