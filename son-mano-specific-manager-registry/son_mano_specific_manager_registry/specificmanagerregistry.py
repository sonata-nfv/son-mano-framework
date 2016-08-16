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
This is the main module of the Specific Manager Registry component.
"""
import logging
import json
import time
import uuid
import yaml
from sonmanobase.plugin import ManoBasePlugin

from son_mano_specific_manager_registry.smr_engine import SMREngine

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-specific-manager-registry")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class SsmNotFoundException(BaseException):
    pass


class SpecificManagerRegistry(ManoBasePlugin):
    def __init__(self):

        self.name = "SMR"
        self.version = 'v0.01'
        self.description = 'Specific Manager Registry'
        self.auto_register = True
        self.wait_for_registration = True
        self.auto_heartbeat_rate = 0
        self.ssm_repo = {}

        # connect to the docker daemon
        self.smrengine = SMREngine()

        # register smr into the plugin manager
        super(SpecificManagerRegistry, self).__init__(self.name,
                                                      self.version,
                                                      self.description,
                                                      self.auto_register,
                                                      self.wait_for_registration,
                                                      self.auto_heartbeat_rate)

        LOG.info("Starting Specific Manager Registry (SMR) ...")

        # register subscriptions
        self.declare_subscriptions()

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.register_async_endpoint(self.on_board, "specific.manager.registry.ssm.on-board")
        self.manoconn.register_async_endpoint(self.on_instantiate, "specific.manager.registry.ssm.instantiate")
        self.manoconn.register_async_endpoint(self.on_ssm_register, "specific.manager.registry.ssm.registration")
        self.manoconn.register_async_endpoint(self.on_ssm_update, "specific.manager.registry.ssm.update")

    def on_board(self, ch, method, properties, message):

        message = yaml.load(message)
        return yaml.dump(self.smrengine.pull(ssm_uri=message['service_specific_managers'][0]['image'],
                                              ssm_name=message['service_specific_managers'][0]['id']))

    def on_instantiate(self, ch, method, properties, message):

        message = yaml.load(message)
        return yaml.dump(self.smrengine.start(image_name= message['service_specific_managers'][0]['image'],
                                               ssm_name= message['service_specific_managers'][0]['id']))

    def on_ssm_register(self, ch, method, properties, message):

        message = json.loads(str(message))  # , "utf-8"))
        response = {}
        keys = self.ssm_repo.keys()
        if message['name'] in keys:
            LOG.error('Cannot register SSM: %r, already exists' % message['name'])
            response = {'status': 'failed'}
        else:

            try:
                pid = str(uuid.uuid4())
                self.ssm_repo.update({message['name']: message})
                response = {
                    "status": "running",
                    "name": message['name'],
                    "version": message['version'],
                    "description": message['description'],
                    "uuid": pid,
                    "error": None
                }
                self.ssm_repo.update({message['name']: response})
                LOG.debug("SSM registration done %r" % self.ssm_repo)
                response = {'status': 'OK', 'name': response['name']}
            except BaseException as ex:
                response = {'status': 'failed'}
                LOG.exception('Cannot register SSM: %r' % message['name'])
        return json.dumps(response)

    def on_ssm_update(self, ch, method, properties, message):

        message = yaml.load(message)
        ssm_uri = message['service_specific_managers'][0]['image']
        ssm_name = message['service_specific_managers'][0]['id']
        result = {}
        result.update(self.smrengine.pull(ssm_uri, ssm_name))
        result.update(self.smrengine.start(ssm_uri, ssm_name))
        LOG.info("Waiting for ssm2 registration ...")
        self._wait_for_ssm()
        result.update(self.ssm_kill())
        return yaml.dump(result)

    def ssm_kill(self):

        result = self.smrengine.stop('ssm1')
        if result == 'done':
            self.ssm_repo['ssm1']['status'] = 'killed'
            LOG.debug("%r" % self.ssm_repo)
        return {'status': self.ssm_repo['ssm1']['status']}

    def _wait_for_ssm(self, timeout=5, sleep_interval=0.1):

        c = 0
        rep = str(self.ssm_repo)
        while 'ssm2' not in rep and c < timeout:
            time.sleep(sleep_interval)
            c += sleep_interval


def main():
    SpecificManagerRegistry()


if __name__ == '__main__':
    main()
