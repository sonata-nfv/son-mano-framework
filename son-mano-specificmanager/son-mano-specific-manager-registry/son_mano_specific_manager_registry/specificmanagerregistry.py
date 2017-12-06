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
This is the main module of SONATA's Specific Manager Registry plugin.
"""
import logging
import time
import uuid
import yaml
import string
import random
import threading
import os

from sonmanobase.plugin import ManoBasePlugin
from sonmanobase import messaging
from son_mano_specific_manager_registry import smr_engine as engine
from son_mano_specific_manager_registry import smr_topics as topic

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-specific-manager-registry")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class SpecificManagerRegistry(ManoBasePlugin):

    def __init__(self):

        self.version = 'v0.02'
        self.description = 'Specific Manager Registry'

        # a storage for f/ssms
        self.ssm_repo = {}

        # connect to the docker daemon
        self.smrengine = engine.SMREngine()

        # register smr into the plugin manager
        super(self.__class__, self).__init__(version=self.version, description=self.description)

    def __del__(self):
        """
        Destroy SMR instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def deregister(self):
        """
        Send a deregister request to the plugin manager.
        """
        LOG.info('De-registering SMR with uuid ' + str(self.uuid))
        message = {"uuid": self.uuid}
        self.manoconn.notify("platform.management.plugin.deregister",
                             yaml.dump(message))
        os._exit(0)

    def on_registration_ok(self):
        """
        This method is called when the SMR is registered to the plugin manager
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")



    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.register_async_endpoint(self.on_ssm_onboard, topic.SSM_ONBOARD)
        self.manoconn.register_async_endpoint(self.on_fsm_onboard, topic.FSM_ONBOARD)
        self.manoconn.register_async_endpoint(self.on_ssm_instantiate, topic.SSM_INSTANTIATE)
        self.manoconn.register_async_endpoint(self.on_fsm_instantiate, topic.FSM_INSTANTIATE)
        self.manoconn.register_async_endpoint(self.on_ssm_update, topic.SSM_UPDATE)
        self.manoconn.register_async_endpoint(self.on_fsm_update, topic.FSM_UPDATE)
        self.manoconn.register_async_endpoint(self.on_ssm_terminate, topic.SSM_TERMINATE)
        self.manoconn.register_async_endpoint(self.on_fsm_terminate, topic.FSM_TERMINATE)
        self.manoconn.subscribe(self.on_ssm_status, topic.FSM_STATUS)

    def on_ssm_onboard(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'NSD' in message:
                result = self.onboard(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'NSD not found'})

    def on_fsm_onboard(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'VNFD' in message:
                result = self.onboard(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'VNFD not found'})

    def on_ssm_instantiate(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'NSD' in message:
                result = self.instantiate(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'NSD not found'})

    def on_fsm_instantiate(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'VNFD' in message:
                result = self.instantiate(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'VNFD not found'})


    def on_ssm_update(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'NSD' in message:
                result = self.update(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'NSD not found'})

    def on_fsm_update(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'VNFD' in message:
                result = self.update(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'VNFD not found'})

    def on_ssm_terminate(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'NSD' in message:
                result = self.terminate(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'NSD not found'})

    def on_fsm_terminate(self, ch, method, properties, message):

        if properties.app_id != self.name:
            message = yaml.load(message)
            if 'VNFD' in message:
                result = self.terminate(message)
                return yaml.dump(result)
            else:
                return yaml.dump({'status': 'Failed', 'error': 'VNFD not found'})

    def on_ssm_register(self, ch, method, properties, message):

        if properties.app_id != self.name:
            try:
                message = yaml.load(message)

                # check if the message format is correct
                if 'specific_manager_id' in message:
                    LOG.debug("Registration request received for: {0}".format(message['specific_manager_id']))
                    sm_repo_id = "{0}{1}".format(message['specific_manager_id'], message['sf_uuid'])

                    # check if the SM is already registered
                    if sm_repo_id in self.ssm_repo.keys():
                        # check if the sm is an updating version
                        if message['update_version'] == 'true':
                            self.ssm_repo[sm_repo_id]['status']= 'registered'
                            self.ssm_repo[sm_repo_id]['version'] = message['version']
                            self.ssm_repo[sm_repo_id]['description'] = message['description']
                            result = self.ssm_repo[sm_repo_id]
                        else:
                            LOG.error("Cannot register '{0}', already exists".format(message['specific_manager_id']))
                            result = {'status': 'Failed', 'error': "Cannot register '{0}', "
                                                                   "already exists".format(message['specific_manager_id'])}
                    else:
                        pid = str(uuid.uuid4())
                        response = {
                            "status": "registered",
                            "specific_manager_type": message['specific_manager_type'],
                            "service_name": message['service_name'],
                            "function_name": message['function_name'],
                            "specific_manager_id": message['specific_manager_id'],
                            "version": message['version'],
                            "description": message['description'],
                            "uuid": pid,
                            "sfuuid": message['sf_uuid'],
                            "error": None
                        }
                        self.ssm_repo.update({sm_repo_id: response})
                        result = response
                else:
                    result = {'status': 'Failed', 'error': 'Invalid registration request format'}
                    LOG.error("registration failed, invalid registration request format")
            except BaseException as err:

                if 'specific_manager_id' in message:
                    result = {'status': 'Failed', 'error': str(err)}
                    LOG.error("{0} registration failed, Error: {1}".format(message['specific_manager_id'], str(err)))
                else:
                    result = {'status': 'Failed', 'error': str(err)}
                    LOG.error("registration failed, Error: {0}".format(str(err)))

            return yaml.dump(result)

    def onboard(self, message):

        descriptor = None; manager = None; result_dict = {}

        if 'NSD' in message:
            descriptor = 'NSD'
            manager = 'service_specific_managers'
        elif 'VNFD' in message:
            descriptor = 'VNFD'
            manager = 'function_specific_managers'

        for i in range(len(message[descriptor][manager])):

            m_id = message[descriptor][manager][i]['id']
            m_image = message[descriptor][manager][i]['image']

            LOG.info('On-boarding request received for: {0}'.format(m_id))
            try:
                result = self.smrengine.pull(image=m_image)
            except BaseException as error:
                result_dict.update({m_id: {'status': 'Failed', 'error': str(error)}})
                LOG.error('On-boarding failed for: {0}'.format(m_id))
            else:
                try:
                    result = yaml.load(result.split("\n")[1])
                except BaseException as error:
                    LOG.error('On-boarding failed for: {0}'.format(m_id))
                    result_dict.update({m_id: {'status': 'Failed', 'error': error}})
                else:
                    if 'error' not in result.keys():
                        LOG.info('On-boarding succeeded for: {0}'.format(m_id))
                        result_dict.update({m_id: {'status': 'On-boarded', 'error': 'None'}})
                    else:
                        LOG.error('On-boarding failed for: {0}'.format(m_id))
                        result_dict.update({m_id: {'status': 'Failed', 'error': result['error']}})

        return result_dict

    def instantiate(self, message):

        descriptor = None; manager = None; result_dict = {}; sm_type='ssm'; v_host_error=False

        if 'NSD' in message:
            descriptor = 'NSD'
            manager = 'service_specific_managers'
        elif 'VNFD' in message:
            descriptor = 'VNFD'
            manager = 'function_specific_managers'
            sm_type = 'fsm'

        # Create virtual host for the service/function to be used by SSM/FSM
        response = self.smrengine.create_vh(sm_type=sm_type, uuid=message['UUID'])

        if response == (201, 201) or (0,0):
            url = "{0}/{1}-{2}".format(self.smrengine.sm_broker_host, sm_type, message['UUID'])
            connection = messaging.ManoBrokerRequestResponseConnection(app_id=self.name, url=url)
            connection.register_async_endpoint(self.on_ssm_register, topic.SSM_REGISTRATION)
            time.sleep(1)
            if response == (201, 201):
                LOG.info('Virtual Host: {0}-{1} has been created!'.format(sm_type, message['UUID']))
            else:
                LOG.info('Virtual Host already exists')
        else:
            v_host_error = True
        for i in range(len(message[descriptor][manager])):
            if not v_host_error:
                m_id = message[descriptor][manager][i]['id']
                m_image = message[descriptor][manager][i]['image']
                if 'private_key' in message:
                    p_key = message['private_key']
                else:
                    p_key = None
                LOG.info('Instantiation request received for: {0}'.format(m_id))
                sm_repo_name= "{0}{1}".format(m_id, message['UUID'])
                try:
                    self.smrengine.start(id=m_id, image=m_image, sm_type=sm_type, uuid=message['UUID'], p_key= p_key)
                except BaseException as error:
                    LOG.error('Instantiation failed for: {0}, Error: {1}'.format(m_id, error))
                    result_dict.update({m_id: {'status': 'Failed', 'uuid': 'None', 'error': str(error)}})
                else:
                    registration = threading.Thread(target= self._wait_for_sm_registration, args=[sm_repo_name,m_id])
                    registration.daemon = True
                    registration.start()
                    registration.join()
                    if sm_repo_name in self.ssm_repo.keys():
                        LOG.debug('Registration & instantiation succeeded for: {0}'.format(m_id))
                        self.ssm_repo[sm_repo_name]['status'] = 'running'
                        result_dict.update({m_id: {'status': 'Instantiated',
                                            'uuid': self.ssm_repo[sm_repo_name]['uuid'], 'error': 'None'}})
                    else:
                        LOG.error('Instantiation failed:SSM name {0} not found!'.format(m_id))
                        result_dict.update({m_id: {'status': 'Failed', 'uuid': 'None', 'error': 'Registration failed'}})
                        self.smrengine.rm(id=m_id, image=m_image, uuid= message['UUID'])
            else:
                LOG.error('Instantiation failed for: {0}, Error: RabbitMQ virtual host creation failed'.format(m_id))
                result_dict.update(
                    {m_id: {'status': 'Failed', 'uuid': 'None', 'error': 'RabbitMQ virtual host creation failed'}})

        return result_dict


    def update(self, message):

        descriptor = None; manager = None; result_dict = {}; sm_type = 'ssm'; v_host_error = False

        if 'NSD' in message:
            descriptor = 'NSD'
            manager = 'service_specific_managers'
        elif 'VNFD' in message:
            descriptor = 'VNFD'
            manager = 'function_specific_managers'
            sm_type = 'fsm'

        # Create virtual host for the service/function to be used by SSM/FSM
        response = self.smrengine.create_vh(sm_type=sm_type, uuid=message['UUID'])
        if response == (201, 201) or (0,0):
            url = "{0}/{1}-{2}".format(self.smrengine.sm_broker_host, sm_type, message['UUID'])
            connection = messaging.ManoBrokerRequestResponseConnection(app_id=self.name, url=url)
            connection.register_async_endpoint(self.on_ssm_register, topic.SSM_REGISTRATION)
            time.sleep(1)
            if (201,201):
                LOG.info('Virtual Host: {0}-{1} has been created!'.format(sm_type, message['UUID']))
            else:
                LOG.info('Virtual Host already exists')
        else:
            v_host_error = True

        for i in range(len(message[descriptor][manager])):

            if not v_host_error:
                # retrieve current id and image
                op_list = message[descriptor][manager][i]['options']
                c_id = None; c_image = None

                for j in range(len(op_list)):
                    if op_list[j]['key'] == 'currentId':
                        c_id = op_list[j]['value']
                        break
                for k in range(len(op_list)):
                    if op_list[k]['key'] == 'currentImage':
                        c_image = op_list[k]['value']
                        break

                if c_id and c_image is not None:

                    LOG.info('Updating request received for: {0}'.format(c_id))
                    m_id = message[descriptor][manager][i]['id']
                    m_image = message[descriptor][manager][i]['image']
                    sm_repo_name = "{0}{1}".format(m_id, message['UUID'])

                    # onboard the new SM
                    LOG.info('On-boarding started for : {0}'.format(m_id))
                    try:
                        result = self.smrengine.pull(image=m_image)
                    except BaseException as error:
                        result_dict.update({m_id: {'status': 'Failed', 'error': str(error)}})
                        LOG.error('On-boarding failed for: {0}'.format(m_id))
                    else:
                        result = yaml.load(result.split("\n")[1])
                        if 'error' in result.keys():
                            LOG.error('On-boarding failed for: {0}'.format(m_id))
                            result_dict.update({m_id: {'status': 'Failed', 'error': result['error']}})
                        else:
                            LOG.info('On-boarding succeeded for: {0}'.format(m_id))

                            if c_id == m_id and self.ssm_repo[sm_repo_name]['sfuuid'] == message['UUID']:

                                # instantiate the new SM
                                LOG.info('Instantiation started for: {0}'.format(m_id))
                                if 'private_key' in message:
                                    p_key = message['private_key']
                                else:
                                    p_key = None
                                try:
                                    random_id = self.id_generator()
                                    self.smrengine.start(id=random_id, image=m_image, sm_type=sm_type,
                                                         uuid=message['UUID'], p_key= p_key)
                                except BaseException as error:
                                    LOG.error('Instantiation failed for: {0}, Error: {1}'.format(m_id, error))
                                    result_dict.update({m_id: {'status': 'Failed', 'uuid': 'None',
                                                               'error': str(error)}})
                                else:

                                    # Check if update is successfully done.
                                    update = threading.Thread(target=self._wait_for_update, args=[sm_repo_name])
                                    update.daemon = True
                                    update.start()
                                    update.join()

                                    if self.ssm_repo[sm_repo_name]['status'] == 'registered':
                                        LOG.debug('Registration & instantiation succeeded for: {0}'.format(m_id))
                                        self.ssm_repo[sm_repo_name]['status'] = 'running'
                                        result_dict.update({m_id: {'status': 'Updated',
                                                                   'uuid': self.ssm_repo[sm_repo_name]['uuid'],
                                                                   'error': 'None'}})

                                        # terminate the current SM
                                        try:
                                            self.smrengine.rm(id=c_id, image=c_image, uuid=message['UUID'])
                                        except BaseException as error:
                                            LOG.error("Termination failed for: {0} , Error: {1}".format(c_id, error))
                                            self.smrengine.rm(id=random_id, image=m_image, uuid=message['UUID'])
                                            result_dict.update({m_id: {'status': 'Failed', 'error': str(error)}})
                                        else:
                                            try:
                                                self.smrengine.rename("{0}{1}".format(random_id, message['UUID']),
                                                                      "{0}{1}".format(m_id, message['UUID']))

                                            except BaseException as error:
                                                LOG.error("Rename failed for: {0} , Error: {1}".format(c_id, error))
                                                self.smrengine.rm(id=random_id, image=m_image, uuid= message['UUID'])
                                                result_dict.update({m_id: {'status': 'Failed', 'error': str(error)}})
                                            else:
                                                self.ssm_repo[sm_repo_name]['status'] = 'updated'
                                                LOG.debug("Termination succeeded for: {0} (old version)".format(c_id))
                                                LOG.debug('{0} updating succeeded'.format(m_id))
                                    else:
                                        LOG.error("Instantiation failed for: {0}, "
                                                  "Error: Registration failed".format(m_id))
                                        result_dict.update(
                                            {m_id: {'status': 'Failed', 'uuid': 'None',
                                                    'error': 'Registration failed'}})
                                        self.smrengine.rm(id=m_id, image=m_image, uuid=message['UUID'])
                            else:
                                # instantiate the new SM
                                LOG.info('Instantiation started for: {0}'.format(m_id))
                                if 'private_key' in message:
                                    p_key = message['private_key']
                                else:
                                    p_key = None
                                try:
                                    self.smrengine.start(id=m_id, image=m_image, sm_type=sm_type, uuid=message['UUID'], p_key= p_key)
                                except BaseException as error:
                                    LOG.error('Instantiation failed for: {0}, Error: {1}'.format(m_id, error))
                                    result_dict.update({m_id: {'status': 'Failed',
                                                               'uuid': 'None', 'error': str(error)}})
                                else:

                                    # Check if the registration is successfully done
                                    registration = threading.Thread(target=self._wait_for_sm_registration,
                                                                    args=[sm_repo_name, m_id])
                                    registration.daemon = True
                                    registration.start()
                                    registration.join()

                                    if sm_repo_name in self.ssm_repo.keys():
                                        LOG.debug('Registration & instantiation succeeded for: {0}'.format(m_id))
                                        self.ssm_repo[sm_repo_name]['status'] = 'running'
                                        result_dict.update({m_id: {'status': 'Updated',
                                                            'uuid': self.ssm_repo[sm_repo_name]['uuid'], 'error': 'None'}})

                                        # terminate the current SM
                                        try:
                                            self.smrengine.rm(id=c_id, image=c_image, uuid=message['UUID'])
                                        except BaseException as error:
                                            LOG.error("Termination failed for: {0} , Error: {1}".format(c_id, error))
                                            self.smrengine.rm(id=m_id, image=m_image, uuid=message['UUID'])
                                            del self.ssm_repo[sm_repo_name]
                                            result_dict.update({m_id: {'status': 'Failed', 'error': str(error)}})
                                        else:
                                            LOG.debug("Termination succeeded for: {0} (old version)".format(c_id))
                                            self.ssm_repo[sm_repo_name]['status'] = 'terminated'
                                            LOG.debug('Updating succeeded, {0} has replaced by {1}'.format(c_id, m_id))
                                    else:
                                        LOG.error("Instantiation failed for: {0}, Error: Registration failed".format(m_id))
                                        result_dict.update(
                                            {m_id: {'status': 'Failed', 'uuid': 'None', 'error': 'Registration failed'}})
                                        self.smrengine.rm(id=m_id, image=m_image, uuid=message['UUID'])
            else:
                LOG.error('Instantiation failed for: {0}, Error: RabbitMQ virtual host creation failed'.format(m_id))
                result_dict.update(
                    {m_id: {'status': 'Failed', 'uuid': 'None', 'error': 'RabbitMQ virtual host creation failed'}})
        return result_dict

    def terminate(self, message):

        descriptor = None; manager = None; result_dict = {}

        if 'NSD' in message:
            descriptor = 'NSD'
            manager = 'service_specific_managers'
        elif 'VNFD' in message:
            descriptor = 'VNFD'
            manager = 'function_specific_managers'

        # terminating all SSMs within the NSD/VNFD
        for i in range(len(message[descriptor][manager])):
            op_list = message[descriptor][manager][i]['options']
            for j in range(len(op_list)):
                if op_list[j]['key'] == 'termination' and op_list[j]['value'] == 'true':
                    m_id = message[descriptor][manager][i]['id']
                    m_image = message[descriptor][manager][i]['image']
                    try:
                        self.smrengine.rm(id=m_id,image=m_image, uuid=message['UUID'])
                    except BaseException as error:
                        LOG.error("Termination failed for: {0} , Error: {1}".format(m_id,error))
                        result_dict.update({m_id: {'status': 'Failed', 'error': str(error)}})
                    else:
                        LOG.debug("Termination succeeded for: {0}".format(m_id))
                        self.ssm_repo["{0}{1}".format(m_id, message['UUID'])]['status']= 'terminated'
                        result_dict.update({m_id: {'status': 'Terminated', 'error': 'None'}})

        return result_dict

    def _wait_for_sm_registration(self, rep_name, name):
        c = 0
        timeout = 60
        sleep_interval = 2
        while rep_name not in self.ssm_repo.keys() and c < timeout:
            time.sleep(sleep_interval)
            c += sleep_interval

        if c >= 60:
            LOG.error('Instantiation failed for: {0}, Registration failed- timeout error'.format(name))

    def _wait_for_update(self, name):
        c = 0
        timeout = 60
        sleep_interval = 2
        while self.ssm_repo[name]['status'] != 'registered' and c < timeout:
            time.sleep(sleep_interval)
            c += sleep_interval

        if c >= 60:
            LOG.error('Updating failed for: {0}, timeout error'.format(name))


    def on_ssm_status(self, ch, method, properties, message):
        message = yaml.load(message)
        LOG.info('{0} status: {1}'.format(message['name'], message['status']))

    def id_generator(self):
        size = 10; chars=string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(size))



def main():
    SpecificManagerRegistry()


if __name__ == '__main__':
     main()