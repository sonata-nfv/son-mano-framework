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
import json
import time
import yaml

from sonmanobase import messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-fakeslm")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class fakeslmU(object):
    def __init__(self):

        self.name = 'fake-slm-update'
        self.version = '0.1-dev'
        self.description = 'description'

        LOG.info(
            "Starting SLM:...")
        # create and initialize broker connection
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)

        self.result = {'on-board': None, 'instantiation': None}
        # register to plugin manager
        self.publish_update_nsd()

        # jump to run
        self.run()

    def run(self):

        # go into infinity loop

        while True:
            time.sleep(1)

    def publish_update_nsd(self):

        # message = {'name': 'ssm2',
        #            'version': '0.1',
        #            'uri': 'hadik3r/ssm2'}  # 'registry.sonata-nfv.eu:5000/ssm/ssm2'}
        nsd = open('son_mano_specific_manager_registry/NSD2.yaml', 'r')
        message = yaml.load(nsd)
        self.manoconn.call_async(self._on_publish_update_nsd_response,
                                 'specific.manager.registry.ssm.update',
                                 yaml.dump(message))

    def _on_publish_update_nsd_response(self, ch, method, props, response):

        response = yaml.load(str(response))  # , "utf-8"))
        if response['instantiation'] == 'OK' and response['on-board'] == 'OK':
            LOG.info("pull and instantiation done")
        else:
            LOG.error("SMR instantiation failed. Exit.")
            exit(1)


def main():
    fakeslmU()


if __name__ == '__main__':
    main()
