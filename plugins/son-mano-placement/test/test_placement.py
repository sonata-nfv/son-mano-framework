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

import unittest
import time
import json
import yaml
import threading
import logging
import uuid
import son_mano_placement.placement_helpers as tools

from unittest import mock
from multiprocessing import Process
from son_mano_placement.placement import PlacementPlugin
from sonmanobase.messaging import ManoBrokerRequestResponseConnection
from collections import namedtuple

logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:slm_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)


class testPlacementPluginFunctionality(unittest.TestCase):
    """
    Test the different methods of the placement plugin.
    """

    pp = None

########################
# SETUP
########################
    def setUp(self):

        # Create a new placement plugin
        self.pp = PlacementPlugin(auto_register=False, start_running=False)

        # Some threading events that can be used during the tests
        self.wait_for_first_event = threading.Event()
        self.wait_for_first_event.clear()

    def tearDown(self):
        # Clean up

        try:
            del self.pp
        except:
            pass

########################
# TESTS
########################
    def test_Placement_load_balanced_1_vnf_1_vdu_a(self):
        """
        This method tests whether a load_balanced operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_1.yml', 'rb'))
        vnfd = yaml.load(open(path_to_artefacts + 'vnfd_1_1.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd
        vnf_1['id'] = vnf_1_id

        vnfs = []
        vnfs.append(vnf_1)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_1.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'load balanced'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'bar'}]
        egress = [{'nap': '8.8.8.8', 'location': 'bar'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number VNFs doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_load_balanced_1_vnf_1_vdu_b(self):
        """
        This method tests whether a load_balanced operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_2.yml', 'rb'))
        vnfd = yaml.load(open(path_to_artefacts + 'vnfd_1_2.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd
        vnf_1['id'] = vnf_1_id

        vnfs = []
        vnfs.append(vnf_1)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_2.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'load balanced'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number VNFs doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_load_balanced_1_vnf_2_vdu(self):
        """
        This method tests whether a load_balanced operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_3.yml', 'rb'))
        vnfd = yaml.load(open(path_to_artefacts + 'vnfd_1_3.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd
        vnf_1['id'] = vnf_1_id

        vnfs = []
        vnfs.append(vnf_1)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_3.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'load balanced'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_load_balanced_2_vnf_2_vdu(self):
        """
        This method tests whether a load_balanced operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_4.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_4.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_4.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_4.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'load balanced'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_fill_first_2_vnf_2_vdu_a(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_5.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_5.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_5.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_5.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'fill first'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_fill_first_2_vnf_2_vdu_b(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_6.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_6.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_6.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_6.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'fill first'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_fill_first_2_vnf_2_vdu_c(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_7.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_7.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_7.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_7.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'fill first'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_fill_first_2_vnf_2_vdu_d(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_8.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_8.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_8.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_8.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'fill first'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_fill_first_2_vnf_2_vdu_e(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_9.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_9.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_9.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_9.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'fill first'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_priority_2_vnf_2_vdu_a(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_10.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_10.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_10.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_10.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Athens', 'Ghent', 'Aveiro']
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_priority_2_vnf_2_vdu_b(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_11.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_11.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_11.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_11.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Athens', 'Ghent', 'Aveiro']
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        customer_policy = {}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_load_balanced_blacklist_2_vnf_2_vdu(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_12.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_12.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_12.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_12.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'load balanced'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        blacklist = ['Aveiro']
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_fill_first_blacklist_2_vnf_2_vdu(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_13.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_13.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_13.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_13.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'fill first'
        operator_policy['policy_list'] = []
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        blacklist = ['Athens']
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_priority_blacklist_2_vnf_2_vdu(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_14.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_14.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_14.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_14.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']
        operator_policy['weights'] = {'operator': 1.0, 'developer': '0.0'}

        blacklist = ['Athens']
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress,  vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_proximity_blacklist_2_vnf_2_vdu(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_15.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_15.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_15.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_15.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']

        operator_weight = 0.0
        developer_weight = 1.0

        blacklist = ['Athens']
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '8.8.8.8', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=operator_weight, developer_weight=developer_weight, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_proximity_2_vnf_2_vdu(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_16.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_16.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_16.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_16.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']

        operator_weight = 0.0
        developer_weight = 1.0

        blacklist = []
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '10.1.10.1', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=operator_weight, developer_weight=developer_weight, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_affinity_2_vnf_2_vdu_a(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_17.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_17.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_17.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_17.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']

        operator_weight = 0.0
        developer_weight = 1.0

        blacklist = []
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '10.1.10.1', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=operator_weight, developer_weight=developer_weight, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_affinity_blacklist_2_vnf_2_vdu_a(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_18.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_18.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_18.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_18.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']

        operator_weight = 0.0
        developer_weight = 1.0

        blacklist = ['Aveiro']
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '10.1.10.1', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=operator_weight, developer_weight=developer_weight, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-6666',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_affinity_proximity_blacklist_2_vnf_2_vdu(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_19.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_19.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_19.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_19.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'priority'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']

        operator_weight = 0.0
        developer_weight = 1.0

        blacklist = ['Aveiro']
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '10.1.10.1', 'location': 'foo'}]

        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=operator_weight, developer_weight=developer_weight, vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

    def test_Placement_load_balanced_proximity_2_vnf_2_vdu_a(self):
        """
        This method tests whether a fill_first operator constraint
        is correctly executed.
        """
        path_to_artefacts = '/plugins/son-mano-placement/test/artefacts/'
        nsd = yaml.load(open(path_to_artefacts + 'nsd_20.yml', 'rb'))
        vnfd1 = yaml.load(open(path_to_artefacts + 'vnfd_1_20.yml', 'rb'))
        vnfd2 = yaml.load(open(path_to_artefacts + 'vnfd_2_20.yml', 'rb'))

        serv_id = str(uuid.uuid4())

        vnf_1_id = str(uuid.uuid4())
        vnf_1 = {}
        vnf_1['vnfd'] = vnfd1
        vnf_1['id'] = vnf_1_id

        vnf_2_id = str(uuid.uuid4())
        vnf_2 = {}
        vnf_2['vnfd'] = vnfd2
        vnf_2['id'] = vnf_2_id

        vnfs = []
        vnfs.append(vnf_1)
        vnfs.append(vnf_2)

        top = yaml.load(open(path_to_artefacts + 'infrastructure_20.yml', 'rb'))

        operator_policy = {}
        operator_policy['policy'] = 'load balanced'
        operator_policy['policy_list'] = ['Ghent', 'Athens', 'Aveiro']

        operator_weight = 0.50
        developer_weight = 0.50

        blacklist = []
        customer_policy = {'blacklist': blacklist}

        ingress = [{'nap': '10.100.10.100', 'location': 'foo'}]
        egress = [{'nap': '10.1.10.1', 'location': 'foo'}]

        op_corr = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=1.0, developer_weight=0.0, vnf_single_pop=True)[2]
        de_corr = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=0.0, developer_weight=1.0, vnf_single_pop=True)[2]
        mapping = self.pp.placement(serv_id, nsd, vnfs, top, operator_policy, customer_policy, ingress, egress, operator_weight=abs(operator_weight/op_corr), developer_weight=abs(developer_weight/de_corr), vnf_single_pop=True)

        # Check if every VNF is mapped.
        self.assertEqual(len(mapping[0].keys()),
                         len(vnfs),
                         msg="Number images doesn't match number of mappings.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_1_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if correct VNF id is used.
        self.assertIn(vnf_2_id,
                      mapping[0].keys(),
                      msg="Function ID in mapping incorrect.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_1_id],
                         '1111-22222222-33333333-5555',
                         msg="VNF mapped on wrong PoP.")

        # Check if VNF is mapped on PoP with lowest load.
        self.assertEqual(mapping[0][vnf_2_id],
                         '1111-22222222-33333333-4444',
                         msg="VNF mapped on wrong PoP.")

if __name__ == '__main__':
    unittest.main()
