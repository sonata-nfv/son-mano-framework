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
This is the main module of the Scaling Executive Plugin.
"""
import logging
import yaml
import os
from sonmanobase.plugin import ManoBasePlugin
from sonmanobase import messaging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-mano-scaling-executive")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class ScalingExecutive(ManoBasePlugin):

    def __init__(self):

        self.version = 'v0.01'
        self.description = 'Scaling Executive Plugin'

        if 'sm_broker_host' in os.environ:
            self.sm_broker_host = os.environ['sm_broker_host']
        else:
            self.sm_broker_host = 'amqp://specific-management:sonata@son-broker:5672'

        # register scaling executive in the plugin manager
        super(self.__class__, self).__init__(version=self.version, description=self.description)

    def declare_subscriptions(self):
        """
        Declare topics to which we want to listen and define callback methods.
        """
        self.manoconn.subscribe(self.on_scaling_request, "scaling.executive.request")

    def __del__(self):
        """
        Destroy Scaling Executive instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def deregister(self):
        """
        Send a de-register request to the plugin manager.
        """
        LOG.info('De-registering Scaling Executive with uuid ' + str(self.uuid))
        message = {"uuid": self.uuid}
        self.manoconn.notify("platform.management.plugin.deregister",
                             yaml.dump(message))
        os._exit(0)

    def on_registration_ok(self):
        """
        This method is called when the Scaling Executive is registered to the plugin manager
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")

    def on_scaling_request(self, ch, method, properties, payload):
        if properties.app_id != self.name:
            LOG.info('Scaling request received')
            message = yaml.load(payload)
            req = yaml.dump(message)
            topic = 'scaling.fsm.{0}'.format(message['uuid'])
            url = "{0}/fsm-{1}".format(self.sm_broker_host, message['uuid'])
            connection = messaging.ManoBrokerRequestResponseConnection(app_id=self.name, url=url)
            connection.call_async(self.on_scaling_result,topic=topic, msg=req, correlation_id= properties.correlation_id)
            LOG.info("Scaling request forwarded to FSM on topic: {0}".format(topic))

    def on_scaling_result(self, ch, method, properties, payload):
        if properties.app_id != self.name:
            LOG.info('Scaling result received')
            message = yaml.load(payload)
            resp = yaml.dump(message)
            inspect = self.inspector(resp)
            if inspect:

                self.manoconn.notify(topic= 'scaling.executive.request', msg=resp, correlation_id=properties.correlation_id)
                LOG.info('Scaling result sent to FLM')

            else:
                LOG.info('FSM message was dropped!')

    def inspector(self, message):
        check = message
        return True


def main():
    ScalingExecutive()


if __name__ == '__main__':
    main()