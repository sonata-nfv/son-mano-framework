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

import logging
import yaml
import time
import os
from sonmanobase import messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-fakeslm")

LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class fakeslm_updating(object):

    def __init__(self):

        self.name = 'fake-slm'
        self.version = '0.1-dev'
        self.description = 'description'

        LOG.info("Starting SLM1:...")

        # create and initialize broker connection
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)

        self.end = False

        self.publish_updating()

        self.run()

    def run(self):

        # go into infinity loop

        while self.end == False:
            time.sleep(1)

    def publish_updating(self):

        LOG.info("Sending updating request")
        nsd = open('test/test_descriptors/nsdu.yml', 'r')
        message = {'NSD': yaml.load(nsd), 'UUID':'937213ae-890b-413c-a11e-45c62c4eee3f'}
        self.manoconn.call_async(self._on_publish_ins_response,
                                 'specific.manager.registry.ssm.update',
                                 yaml.dump(message))


        vnfd1 = open('test/test_descriptors/vnfdu.yml', 'r')
        message = {'VNFD': yaml.load(vnfd1), 'UUID':'754fe4fe-96c9-484d-9683-1a1e8b9a31a3'}
        self.manoconn.call_async(self._on_publish_ins_response,
                                 'specific.manager.registry.fsm.update',
                                 yaml.dump(message))
        nsd.close()
        vnfd1.close()

    def _on_publish_ins_response(self, ch, method, props, response):

        response = yaml.load(str(response))
        if type(response) == dict:
            try:
                print(response)
            except BaseException as error:
                print(error)

def main():
    fakeslm_updating()


if __name__ == '__main__':
    main()