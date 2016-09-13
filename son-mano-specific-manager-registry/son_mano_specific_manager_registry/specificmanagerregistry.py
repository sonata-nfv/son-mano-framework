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
        self.manoconn.subscribe(self.on_ssm_status, "specific.manager.registry.ssm.status")

    def on_board(self, ch, method, properties, message):
        id = None
        try:
            message = yaml.load(message)
            image = message['service_specific_managers'][0]['image']
            id = message['service_specific_managers'][0]['id']
            LOG.info('Onboarding request received for SSM id: {0}'.format(id))
            self.smrengine.pull(ssm_uri=image, ssm_name= id)
            return yaml.dump({'status': 'On-boarded', 'error': 'None'})
        except BaseException as err:
            if id is not None:
                LOG.error("'{0}' pull: failed ==> '{1}'".format(id, err))
            else:
                LOG.error("SSM pull: failed ==> '{0}'".format(err))
            return yaml.dump({'status': 'Failed', 'error': str(err)})

    def on_instantiate(self, ch, method, properties, message):
        id = None
        try:
            message = yaml.load(message)
            image = message['NSD']['service_specific_managers'][0]['image']
            id = message['NSD']['service_specific_managers'][0]['id']
            LOG.info('Instantiation request received for SSM id: {0}'.format(id))
            self.smrengine.start(image_name= image, ssm_name= id, host_ip= None)
            self._wait_for_ssm_registration(ssm_name= id)
            if id in self.ssm_repo.keys():
                return yaml.dump({'status': 'Instantiated', 'error': 'None'})
            else:
                LOG.error("'{0}' instantiation: failed ==> SSM registration in SMR failed'".format(id))
                return yaml.dump({'status':'failed', 'error': 'SSM registration in SMR failed'})
        except BaseException as err:
            if id is not None:
                LOG.error("'{0}' instantiation: failed ==> '{1}'".format(id, err))
            else:
                LOG.error("SSM instantiation: failed ==> '{0}'".format(err))
            return yaml.dump({'status': 'Failed', 'error': str(err)})

    def on_ssm_register(self, ch, method, properties, message):

        try:
            message = yaml.load(str(message))
            keys = self.ssm_repo.keys()
            if message['name'] in keys:
                LOG.error("Cannot register '{0}', already exists".format(message['name']))
                result = {'status': 'failed', 'error':"Cannot register '{0}', already exists".format(message['name'])}
            else:
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
                LOG.debug("Registration: succeeded ==> '{0}' ".format(self.ssm_repo))
                result = response
        except BaseException as err:
            result = {'status': 'failed', 'error': str(err)}
            LOG.exception("'{0}' registeration failed: ".format(message['name']))
        return yaml.dump(result)


    def on_ssm_update(self, ch, method, properties, message):
        id = None
        try:
            message = yaml.load(message)
            image = message['NSD']['service_specific_managers'][0]['image']
            id = message['NSD']['service_specific_managers'][0]['id']
            LOG.info('Update request received for SSM id: {0}'.format(id))
            host_ip = ''
            try:
                list = message['VNFR']
                for x in range(len(list)):
                    if message['VNFR'][x]['virtual_deployment_units'][0]['vm_image'] == 'sonata-vfw':
                        host_ip =(message['VNFR'][x]['virtual_deployment_units'][0]['vnfc_instance'][0]['connection_points'][0][
                            'type']['address'])
                #host_ip = message['VNFR'][0]['virtual_deployment_units'][0]['vnfc_instance'][0]['connection_points'][0]['type']['address']
                #message['NSR'][1]['virtual_deployment_units'][1]['vnfc_instance'][0]['connection_points'][0]['type']['address']
            except BaseException as err:
                LOG.error("'{0}' Update: failed ==> Host IP address does not exist in the VNFR")
                return yaml.dump({'status': 'Failed', 'error': 'Host IP address does not exist in the VNFR'})
            LOG.info('vFW IP address "{0}"'.format(host_ip))
            self.smrengine.pull(image, id)
            self.smrengine.start(image_name=image, ssm_name=id, host_ip=host_ip)
            LOG.info("Waiting for '{0}' registration ...".format(id))
            self._wait_for_ssm_registration(ssm_name=id)
            if id in self.ssm_repo.keys():
                self.ssm_kill()
                LOG.debug("SSM update: succeeded ")
                return yaml.dump({'status': 'Updated', 'error': 'None'})
            else:
                LOG.error("'{0}' Update: failed ==> SSM registration in SMR failed'".format(id))
                return yaml.dump({'status':'Failed', 'error': 'SSM registration in SMR failed'})
        except BaseException as err:
            LOG.error("'{0}' Update: failed ==> '{1}'".format(id, err))
            return yaml.dump({'status': 'Failed', 'error': str(err)})

    def ssm_kill(self):
        self.smrengine.stop('ssmdumb')
        self.ssm_repo['ssmdumb']['status'] = 'killed'
        LOG.debug('ssmdumb kill: succeeded')

    def _wait_for_ssm_registration(self, ssm_name, timeout=20, sleep_interval=0.1):

        c = 0
        rep = str(self.ssm_repo)
        while ssm_name not in rep and c < timeout:
            time.sleep(sleep_interval)
            c += sleep_interval

    def on_ssm_status(self, ch, method, properties, message):
        message = yaml.load(message)
        LOG.info(message['status'])

def main():
    SpecificManagerRegistry()


if __name__ == '__main__':
    main()