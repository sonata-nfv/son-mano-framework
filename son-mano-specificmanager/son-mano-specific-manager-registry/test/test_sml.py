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

import logging
import yaml
import time
import uuid
from sonmanobase import messaging


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-slm_test")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class fakeslmu(object):
    def __init__(self):

        self.name = 'fake-slm'
        self.version = '0.1-dev'
        self.description = 'description'

        LOG.info("Starting SLM Test:...")

        # create and initialize broker connection
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)
        self.path_descriptors = "/home/hadi/son-mano-framework/plugins/son-mano-service-lifecycle-management/test/test_descriptors/"
        self.test_records = "/home/hadi/son-mano-framework/plugins/son-mano-service-lifecycle-management/test/test_records/"
        self.nsd_descriptor   = open(self.path_descriptors + 'sonata-demo.yml', 'r')
        self.vnfd1_descriptor = open(self.path_descriptors + 'firewall-vnfd.yml', 'r')
        self.vnfd2_descriptor = open(self.path_descriptors + 'iperf-vnfd.yml', 'r')
        self.vnfd3_descriptor = open(self.path_descriptors + 'tcpdump-vnfd.yml', 'r')
        self.end = False
        self.manoconn.register_async_endpoint(self.check1, 'infrastructure.management.compute.list')
        self.manoconn.register_async_endpoint(self.check2, 'infrastructure.service.deploy')
        self.publish_nsd()
        time.sleep(50)
        self.update()
        self.run()

    def run(self):

        # go into infinity loop

        while self.end == False:
            time.sleep(1)


    def publish_nsd(self):




        message = {'NSD': yaml.load(self.nsd_descriptor), 'VNFD1': yaml.load(self.vnfd1_descriptor),
                           'VNFD2': yaml.load(self.vnfd2_descriptor), 'VNFD3': yaml.load(self.vnfd3_descriptor)}

        self.manoconn.call_async(self._on_publish_nsd_response,
                                 'service.instances.create',
                                 yaml.dump(message))
    def check1(self, ch, method, props, response):
        res = yaml.load(str(response))
        VIM_list = [{'vim_uuid': uuid.uuid4().hex}, {'vim_uuid': uuid.uuid4().hex}, {'vim_uuid': uuid.uuid4().hex}]
        return (yaml.dump(VIM_list))

    def check2(self, ch, method, props, response):
        time.sleep(20)
        res= yaml.load(str(response))
        ia_response = yaml.load(open(self.test_records + 'ia-nsr.yml', 'r'))
        return (yaml.dump(ia_response))


    def _on_publish_nsd_response(self, ch, method, props, response):

        response = yaml.load(str(response))
        print (response)
        print('Response Recieved')

    def update(self):
        nsd_descriptor = open('test_descriptors/nsd2.yml', 'r')
        message = {'NSD': yaml.load(nsd_descriptor)}
        self.manoconn.call_async(self.on_publish,'service.instances.update', yaml.dump(message))

    def on_publish(self,ch, method, props, response):
        response = yaml.load(str(response))
        print (response)

def main():
    fakeslmu()


if __name__ == '__main__':
    main()