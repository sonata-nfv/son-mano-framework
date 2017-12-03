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
This is the engine module of SONATA's Specific Manager Registry.
'''

import logging
import os
import docker
import requests
import yaml

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-specific-manager-registry-engine")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class SMREngine(object):
    def __init__(self):
        # connect to docker
        self.dc = self.connect()

        # create rabbitmq user that will be used for communication between FSMs/SSMs and MANO plugins
        if 'broker_man_host' in os.environ:
            self.host = os.environ['broker_man_host']
        else:
            self.host = 'http://localhost:15672'
        url_user = "{0}/api/users/specific-management".format(self.host)
        self.headers = {'content-type': 'application/json'}
        data = '{"password":"sonata","tags":"son-sm"}'
        response = requests.put(url=url_user, headers=self.headers, data=data, auth=('guest', 'guest'))
        if response.status_code == 201:
            LOG.info("RabbitMQ user: specific-management has been created!")
        elif response.status_code==204:
            LOG.info("RabbitMQ user: specific-management already exists!")
        else:
            LOG.error("RabbitMQ user creation failed: {0}".format(response.content))
        if 'sm_broker_host' in os.environ:
            self.sm_broker_host = os.environ['sm_broker_host']
        else:
            self.sm_broker_host = 'amqp://specific-management:sonata@son-broker:5672'

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
            LOG.warning("ENV variable 'DOCKER_HOST' not set. Using {0} as fallback.".format(os.environ["DOCKER_HOST"]))

        # lets connect to the Docker instance specified in current ENV
        # cf.: http://docker-py.readthedocs.io/en/stable/machine/
        dc = docker.from_env(assert_hostname=False)
        # do a call to ensure that we are connected
        dc.info()
        LOG.info("Connected to Docker host: {0}".format(dc.base_url))
        return dc

    def pull(self, image):#, ssm_name):

        """
        Process of pulling / importing a SSM given as Docker image.

        SSM can be specified like:
        - ssm_uri = "registry.sonata-nfv.eu:5000/my-ssm" -> Docker PULL (opt B)
        :return: ssm_image_name
        """
        #repository pull
        res= self.dc.pull(image) # image name and uri are the same
        error_count = 1
        while error_count <= 3:
            response = yaml.load(res.split("\n")[1])
            if 'error' in response.keys():
                error_count += 1
                res = self.dc.pull(image)
            else:
                error_count = 4
        return res

    def start(self, id, image, sm_type, uuid, p_key):

        if 'broker_host' in os.environ:
            broker_host = os.environ['broker_host']
        else:
            broker_host = 'amqp://guest:guest@broker:5672/%2F'

        if 'network_id' in os.environ:
            network_id = os.environ['network_id']
        else:
            network_id = 'sonata'

        if 'broker_name' in os.environ:
            broker = self.retrieve_broker_name(os.environ['broker_name'])
        else:
            broker = {'name': 'broker', 'alias': 'broker'}

        vh_name = '{0}-{1}'.format(sm_type,uuid)
        broker_host = "{0}/{1}".format(self.sm_broker_host, vh_name)

        cn_name = "{0}{1}".format(id,uuid)

        container = self.dc.create_container(image=image,
                                             detach=True,
                                             name=cn_name,
                                             environment={'broker_host':broker_host, 'sf_uuid':uuid, 'PRIVATE_KEY':p_key})
        networks = self.dc.networks()
        net_found = False
        for i in range(len(networks)):
            if networks[i]['Name'] == network_id:
                net_found = True
                break

        if (net_found):
                LOG.info('Docker network is used!')
                self.dc.connect_container_to_network(container=container, net_id=network_id, aliases=[id])
                self.dc.start(container=container.get('Id'))
        else:
            LOG.warning('Network ID: {0} Not Found!, deprecated Docker --link is used instead'.format(network_id))
            self.dc.start(container=container.get('Id'), links=[(broker['name'], broker['alias'])])


    def stop(self, ssm_name):
        self.dc.kill(ssm_name)

    def rm (self, id, image, uuid):

        cn_name = "{0}{1}".format(id,uuid)
        LOG.info("{0} Logs: {1}".format(id,self.dc.logs(container=cn_name)))
        self.dc.stop(container=cn_name)
        self.dc.remove_container(container=cn_name, force=True)
        self.dc.remove_image(image= image, force=True)

    def retrieve_broker_name(self, broker):
        mid = broker.find(',')
        name = broker[:mid]
        alias = broker[mid+1:]
        return {'name':name, 'alias':alias}

    def rename(self, current_name, new_name):
        self.dc.rename(current_name,new_name)

    def create_vh(self, sm_type, uuid):
        exists = False
        vh_name = '{0}-{1}'.format(sm_type,uuid)
        api = '/api/vhosts/'
        url_list = '{0}{1}'.format(self.host,api)
        url_create = '{0}{1}{2}'.format(self.host,api,vh_name)
        url_permission = '{0}/api/permissions/{1}/specific-management'.format(self.host,vh_name)
        data = '{"configure":".*","write":".*","read":".*"}'
        list = requests.get(url=url_list, auth= ('guest','guest')).json()
        for i in range(len(list)):
            if list[i]['name'] == vh_name:
                exists = True
                break
        if not exists:
            response = requests.put(url=url_create, headers=self.headers, auth=('guest', 'guest'))
            permission = requests.put(url=url_permission, headers=self.headers, data=data, auth=('guest', 'guest'))
            return response.status_code, permission.status_code
        else:
            return 0,0




