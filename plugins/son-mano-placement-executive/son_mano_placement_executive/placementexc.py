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
This is the main module of the Placement Executive Plugin.
"""
import logging
import yaml
from sonmanobase.plugin import ManoBasePlugin


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-specific-manager-registry")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class PlacementExecutive(ManoBasePlugin):

    def __init__(self):

        self.version = 'v0.01'
        self.description = 'Placement Executive Plugin'
        self.auto_heartbeat_rate = 0

        # register smr into the plugin manager
        super(self.__class__, self).__init__(version=self.version, description= self.description)

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.subscribe(self.on_placement_request, "placement.executive.request")

    def on_placement_request(self, ch, method, properties, payload):
        if properties.app_id != self.name:
            message = yaml.load(payload)
            LOG.info('Placement request received: ' + str(message.keys()))
            topic = 'placement.ssm'+ message['uuid']
            req = yaml.dump(message)
            self.manoconn.call_async(self.on_placement_result, topic= topic, msg=req, correlation_id= properties.correlation_id)
            LOG.info("Placement request forwarded to SSM on topic: " + str(topic))

    def on_placement_result(self, ch, method, properties, payload):
            print ('Placement result recieved')
            message = yaml.load(payload)
            resp = yaml.dump(message)
            self.manoconn.notify(topic = "placement.executive.request", msg= resp, correlation_id=properties.correlation_id)
            print ('Placement result sent to SLM')


def main():
    PlacementExecutive()


if __name__ == '__main__':
    main()
