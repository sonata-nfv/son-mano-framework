# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, 5GTANGO
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).
#
# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).

import requests
import json
import time
import shutil
import os
import yaml
import uuid
import sonmano.messaging as messaging
import tngsdk.package as tngpkg


class ManoConsumer():
    """
    This class interacts with the MANO setup.
    """

    def __init__(self,
                 broker_host='amqp://guest:guest@localhost:5672/%2F',
                 broker_exchange='son-kernel',
                 cat_url='http://localhost:4011/api/v2/'):
        """
        Instantiate the Mano Consumer

        :return:
        """

        self.ledger = {}
        self.app_id = "mano_consumer"
        self.cat_url = cat_url

        # set up connection with the broker
        self.manoconn = messaging.ManoBrokerConnection(self.app_id,
                                                       broker_host,
                                                       broker_exchange)

        # subscribe to relevant topics
        self.manoconn.subscribe(self.on_mano_reply,
                                'service.instances.create')

        self.manoconn.subscribe(self.on_mano_reply,
                                'service.instance.scale')

        self.manoconn.subscribe(self.on_mano_reply,
                                'service.instance.migrate')

        self.manoconn.subscribe(self.on_mano_reply,
                                'service.instance.terminate')

    def on_mano_reply(self, ch, method, prop, payload):
        """
        Processing MANO replies and updating status of each request

        :param ch: todo
        :param method: todo
        :param prop: dictionary with properties of the message
        :param payload: yaml formatted string with the payload

        :returns:
        """

        # Ignore if the message is self sent
        if prop.app_id == self.app_id:
            return

        message = yaml.load(payload)

        # Ignore if the message is a temporarily status update
        temp_status = ['INSTANTIATING', 'TERMINATING', 'MIGRATING', 'SCALING']

        if message['status'] in temp_status:
            return

        # Check if correlation_id is in the ledger, if not, ignore
        if prop.correlation_id not in self.ledger.keys():
            return

        # Evaluate the status
        if message['status'] in ['ERROR', 'READY']:
            self.ledger[prop.correlation_id]['status'] = message['status']
            self.ledger[prop.correlation_id]['data'] = message
        else:
            print.info("Couldn't process message")
            print.info(payload)
            print.info(prop)

        return

    def instantiate_service(self, pkg_path):
        """
        This method instantiates a service on the local MANO setup

        :param pkg: a path to a package on the local file system.
        """

        # Unpackage the package
        pkg_proj = self._unpack(pkg_path, '_tmp')
        nsds, vnfds = self._obtain_descriptor_paths(pkg_proj)

        # Store descriptors in the catalogue
        res, mes = self._store_descriptors_in_catalogue(nsds, 'nsd')

        if not res:
            return "Instantiation failed, couldn't upload nsd: " + str(mes)

        nsd = mes[0]

        print(nsd)
        res, vnfds = self._store_descriptors_in_catalogue(vnfds, 'vnfd')

        if not res:
            return "Instantiation failed, couldn't upload vnfd: " + str(vnfds)

        # remove unpackaged folder
        shutil.rmtree('_tmp', ignore_errors=True)

        # Build instantiation message
        message = {'NSD': nsd}
        for vnfd in vnfds:
            message['VNFD' + str(vnfds.index(vnfd))] =  vnfd

        message['ingresses'] = []
        message['egresses'] = []
        message['blacklist'] = []
        message['user_data'] = {'customer': {'sla_id': ''}, 'developer': {}}

        # Append to ledger
        corr_id = str(uuid.uuid4())
        self.ledger[corr_id] = {'status': 'PENDING'}

        # Async call to MANO
        topic = 'service.instances.create'

        properties = {'correlation_id': corr_id,
                      'app_id': self.app_id,
                      'reply_to': topic}

        self.manoconn.publish(topic,
                              yaml.dump(message),
                              properties)

        # Wait for response on the async call
        while self.ledger[corr_id]['status'] == 'PENDING':
            time.sleep(1)

        if self.ledger[corr_id]['status'] == 'READY':
            ns_id = self.ledger[corr_id]['data']['nsr']['id']
            return True, ns_id, self.ledger[corr_id]
        else:
            return False, self.ledger[corr_id]['data']

    def scale_out_service(self, service_instance_uuid, vnfd_uuid, num=1):
        """
        Make a scale out request to the MANO Framework

        :param service_instance_uuid: The instance uuid of the service
        :param vnfd_uuid: the vnfd that requires additional instance
        :param num_inst: number of extra instances

        :returns: tuple. [0] is bool, [1] message about result
        """

        # Build message
        message = {'service_instance_uuid': service_instance_uuid,
                   'vnfd_uuid': vnfd_uuid,
                   'number_of_instances': num,
                   'scaling_type': 'addvnf'}

        return self._make_request(message, 'service.instance.scale')

    def scale_in_service(self, service_instance_uuid, vnf_uuid):
        """
        Make a scale in request to the MANO Framework based on vnf

        :param service_instance_uuid: The instance uuid of the service
        :param vnf_uuid: the vnf instance that needs to be scaled in

        :returns: tuple. [0] is bool, [1] message about result
        """

        # Build message
        message = {'service_instance_uuid': service_instance_uuid,
                   'vnf_uuid': vnf_uuid,
                   'scaling_type': 'removevnf'}

        return self._make_request(message, 'service.instance.scale')
        
    def scale_in_service_vnfd(self, service_instance_uuid, vnfd_uuid, num=1):
        """
        Make a scale in request to the MANO Framework based on vnfd

        :param service_instance_uuid: The instance uuid of the service
        :param vnf_uuid: the vnf instance that needs to be scaled in

        :returns: tuple. [0] is bool, [1] message about result
        """

        # Build message
        message = {'service_instance_uuid': service_instance_uuid,
                   'vnfd_uuid': vnfd_uuid,
                   'number_of_instances': num,
                   'scaling_type': 'removevnf'}

        return self._make_request(message, 'service.instance.scale')

    def migrate_service(self, service_instance_uuid, vim_uuid, vnf_uuid):
        """
        Make a migration request to the MANO Framework

        :param service_instance_uuid: The instance uuid of the service
        :param vim_uuid: the uuid of the vim that vnf needs to be migrated to
        :param vnf_uuid: the vnf instance that needs to be migrated

        :returns: tuple. [0] is bool, [1] message about result
        """

        # Build message
        message = {'service_instance_uuid': service_instance_uuid,
                   'vnf_uuid': vnf_uuid,
                   'vim_uuid': vim_uuid}

        return self._make_request(message, 'service.instance.migrate')
        
    def terminate_service(self, service_instance_uuid):
        """
        Make a termination request to the MANO Framework

        :param service_instance_uuid: The instance uuid of the service

        :returns: tuple. [0] is bool, [1] message about result
        """

        # Build message
        message = {'service_instance_uuid': service_instance_uuid}

        return self._make_request(message, 'service.instance.terminate')

    def _make_request(self, payload, topic):
        """
        Make a request to the MANO Framework
        """

        # Append to ledger
        corr_id = str(uuid.uuid4())
        self.ledger[corr_id] = {'status': 'PENDING'}

        # Async call to MANO
        properties = {'correlation_id': corr_id,
                      'app_id': self.app_id,
                      'reply_to': topic}

        self.manoconn.publish(topic,
                              yaml.dump(payload),
                              properties)

        # Wait for response on the async call
        while self.ledger[corr_id]['status'] == 'PENDING':
            time.sleep(1)

        outcome = self.ledger[corr_id]
        return bool(outcome['status'] == 'READY'), outcome['data']

    def _unpack(self, pkg_path, proj_path):
        """
        Wraps the tng-sdk-package unpacking functionality.
        """
        args = [
            "--unpackage", pkg_path,
            "--output", proj_path,
            "--store-backend", "TangoProjectFilesystemBackend",
            "--format", "eu.5gtango",
            "--skip-validation",
            "--quiet",
            "--offline"
        ]
        r = tngpkg.run(args)
        if r.error is not None:
            raise BaseException("Can't read package {}: {}"
                                .format(pkg_path, r.error))
        # return the full path to the project
        proj_path = r.metadata.get("_storage_location")
        return proj_path

    def _obtain_descriptor_paths(self, proj_path):
        """
        Return descriptor paths for unpackaged package folder
        """

        proj = yaml.load(open(proj_path + '/project.yml', 'r'))

        nsds = []
        vnfds = []

        for file in proj['files']:
            if 'eu.5gtango' in file['tags']:
                if file['type'] == 'application/vnd.5gtango.nsd':
                    nsds.append(proj_path + '/' + file['path'])
                elif file['type'] == 'application/vnd.5gtango.vnfd':
                    vnfds.append(proj_path + '/' + file['path'])
                else:
                    pass

        return nsds, vnfds

    def _store_descriptors_in_catalogue(self, paths, dsc_type):
        """
        Store the descriptors in the catalogue
        """

        if dsc_type == 'nsd':
            url = self.cat_url + 'network-services'
        if dsc_type == 'vnfd':
            url = self.cat_url + 'vnfs'

        dscs = []

        for path in paths:
            data = open(path, 'r')
            resp = requests.post(url,
                                 data=data,
                                 headers={"Content-Type":
                                          "application/x-yaml"})

            if resp.status_code not in [200,201]:
                return False, resp.text

            dsc = yaml.load(resp.text)[dsc_type]
            dsc['uuid'] = yaml.load(resp.text)['uuid']
            dscs.append(dsc)

        return True, dscs
