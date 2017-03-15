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
import requests
import os
import json
import time
from sonsmbase.smbase import sonSMbase

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("fsm-smart")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class SmartFSM(sonSMbase):

    def __init__(self):

        self.smtype = 'fsm'
        self.name = 'smart'
        self.id = '1'
        self.version = 'v0.2'
        self.description = 'Reconfigures vFW'

        super(self.__class__, self).__init__(smtype=self.smtype,
                                             name=self.name,
                                             id=self.id,
                                             version=self.version,
                                             description=self.description)

    def on_registration_ok(self):

        LOG.debug("Received registration ok event.")
        self.manoconn.subscribe(self.on_alert_recieved,'son.monitoring')
        self.manoconn.publish(topic='specific.manager.registry.ssm.status',
                                message=yaml.dump({'status':'Subscribed to son.monitoring topic, waiting for alert message'}))

    def on_alert_recieved(self, ch, method, props, response):

        alert = json.loads(response)
        if time.time() > self.timeout:

            if alert['alertname'] == 'mon_rule_vm_cpu_usage_85_perc' and alert['exported_job'] == "vnf":

                LOG.info('Alert message received')
                LOG.info('Start reconfiguring vFW ...')

                self.manoconn.publish(topic='specific.manager.registry.ssm.status',
                                  message=yaml.dump({'status': 'cpu usage 85% alert message received, start reconfiguring vFW'}))

                # retrieve vFW IP address
                endpoint = os.environ['HOST']
                self.manoconn.publish(topic='specific.manager.registry.ssm.status',
                                  message=yaml.dump({'status': 'vFW IP address ==> "{0}"'.format(str(endpoint))}))

                entry1 = ''
                try:
                    self.timeout = time.time() + 60 * 5
                    entry1 = requests.post(url='http://' + endpoint + ':8080/stats/flowentry/add',
                                   data=json.dumps({"dpid": 1, "cookie": 200, "priority": 1000,
                                                    "match": {"dl_type": 0x0800, "nw_proto": 17, "udp_dst": 5001}}))
                    if (entry1.status_code == 200):

                        LOG.info('vFW reconfiguration succeeded')
                        self.manoconn.publish(topic='specific.manager.registry.ssm.status',
                                              message=yaml.dump({'status': 'vFW reconfiguration succeeded'}))
                    else:
                        LOG.info('vFW reconfiguration failed')
                        self.manoconn.publish(topic='specific.manager.registry.ssm.status',
                                              message=yaml.dump({'status': 'vFW reconfiguration failed ==> "{0}"'.format(str(entry1))}))
                except BaseException as err:
                    LOG.info('vFW reconfiguration failed')
                    self.manoconn.publish(topic='specific.manager.registry.ssm.status',
                                          message=yaml.dump(
                                              {'status': 'vFW reconfiguration failed ==> "{0}"'.format(str(err))}))

def main():
    SmartFSM()

if __name__ == '__main__':
    main()
