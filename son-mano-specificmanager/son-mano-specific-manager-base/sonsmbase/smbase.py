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
import threading
from sonmanobase import messaging


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("son-sm-base")
LOG.setLevel(logging.DEBUG)
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)


class sonSMbase(object):

    def __init__(self, smtype = None, name= None, id = None, version= None, description=None):
        """
        # FSM/SSM name consists of son,smtype(either ssm or fsm), name (a-z), and an id (0-9)

        :param smtype: specific management type: either fsm or ssm
        :param name: the name of the FSM/SSM
        :param id: the Id of the FSM/SSM
        :param version: version
        :param description: a description on what does FSM/SSM do
        """
        #checks if the chosen name by develeopr is correct
        self.name_checker(self.smtype, self.name, self.id)

        self.smtype = smtype
        self.id = id
        self.name = "son{0}{1}{2}".format(smtype, name, id)
        self.version = version
        self.description = description
        self.uuid = None

        LOG.info("Starting {0} ...".format(self.name))

        # create and initialize broker connection
        self.manoconn = messaging.ManoBrokerRequestResponseConnection(self.name)

        self.tLock = threading.Lock()
        t1 = threading.Thread(target=self.registeration)
        t2 = threading.Thread(target=self.run)

        # register to Specific Manager Registry
        t1.start()

        # locks the registration thread
        self.tLock.acquire()

        # jump to run
        t2.start()

    def name_checker(self, smtype, name, id):

        if smtype != 'ssm' and smtype != 'fsm':
            LOG.error("Name Error: smtype must be either ssm or fsm")
            exit(1)
        if not name.isalpha() and not name.islower():
            LOG.error("Name Error: name must be (a-z)")
            exit(1)
        if not id.isdigit():
            LOG.error("Name Error: id must be (0-9)")
            exit(1)


    def run(self):

        # go into infinity loop (we could do anything here)
        while True:
            time.sleep(1)

    def registeration(self):

        """
        Send a register request to the Specific Manager registry.

        """
        self.tLock.acquire()
        message = {'type': self.smtype,
                   'name': self.name,
                   'id':self.id,
                   'version': self.version,
                   'description': self.description}

        self.manoconn.call_async(self._on_registration_response,
                                 'specific.manager.registry.ssm.registration',
                                 yaml.dump(message))

    def _on_registration_response(self, ch, method, props, response):

        response = yaml.load(str(response))

        if response['status'] != "running":
            LOG.error("{0} registration failed. Exit".format(self.name))
            exit(1)
        else:
            self.uuid = response['uuid']
            LOG.info("{0} registered with uuid:{1}".format(self.name, self.uuid))

            # release the registration thread
            self.tLock.release()

            # jump to on_registration_ok()
            self.on_registration_ok()


    def on_registration_ok(self):

        LOG.debug("Received registration ok event.")
