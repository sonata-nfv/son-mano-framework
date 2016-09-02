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
import yaml
import  time
from sonmanobase import messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("ssm1")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class ManoSSM(object):

    def __init__(self):

        self.name = 'ssm1'
        self.version = 'v0.1'
        self.description = 'An empty SSM'
        self.uuid = None

        LOG.info(
            "Starting %r ..." % self.name)
        # create and initialize broker connection
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)

        # register to Specific Manager Registry
        self.publish()

        # jump to run
        self.run()

    def run(self):

        # go into infinity loop

        while True:
            time.sleep(1)

    def on_registration_ok(self):

        LOG.debug("Received registration ok event.")
        pass


    def publish(self):

        """
        Send a register request to the Specific Manager registry to announce this SSM.
        """

        message = {'name': self.name,
                   'version': self.version,
                   'description': self.description}

        self.manoconn.call_async(self._on_publish_response,
                                 'specific.manager.registry.ssm.registration',
                                 yaml.dump(message))

    def _on_publish_response(self, ch, method, props, response):

        response = yaml.load(str(response))

        if response.get("status") != "OK":
            LOG.debug("Response %r" % response)
            LOG.error("SSM registration failed. Exit.")
            exit(1)

        self.uuid = response.get("uuid")

        LOG.info("SSM registered with UUID: %r" % response.get("uuid"))

        # jump to on_registration_ok()
        self.on_registration_ok()


def main():
    ManoSSM()

if __name__ == '__main__':
    main()
