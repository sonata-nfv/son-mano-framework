"""
 Copyright 2015-2017 Paderborn University

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""


import unittest
from sonmanobase.executiveplugin import ManoBaseExecutivePlugin


class ExecutivePluginStub(ManoBaseExecutivePlugin):

    def __init__(self, auto_docker_connect=True):
        # initialize plugin without plugin manager, heartbeat, etc.
        super(ExecutivePluginStub, self).__init__(name="ExecutivePluginsStub",
                                                  version="0.0",
                                                  auto_register=False,
                                                  wait_for_registration=False,
                                                  auto_heartbeat_rate=0,
                                                  auto_docker_connect=auto_docker_connect)

    def run(self):
        pass


class TestManoBaseExecutivePluginSsmManagement(unittest.TestCase):

    # @unittest.skip("disabled")
    def test_initialize_plugin(self):
        ExecutivePluginStub(auto_docker_connect=False)

    # @unittest.skip("disabled")
    def test_docker_service_connection(self):
        e = ExecutivePluginStub()
        self.assertIsNotNone(e.dc.info().get("ServerVersion"))

    # @unittest.skip("disabled")
    def test_ssm_board_repository(self):
        e = ExecutivePluginStub()
        # ensure that existing test images are removed
        try:
            e.dc.remove_image("mpeuster/ssm_empty_container", force=True)
        except BaseException as ex:
            pass
        # try to board a NON existing SSM
        img = e.board_ssm(ssm_uri="a_not_existing_container/container")
        self.assertIsNone(img)

        # try to board a existing SSM
        img = e.board_ssm(ssm_uri="mpeuster/ssm_empty_container")
        # verify that the image is available after boarding
        self.assertIsNotNone(img)
        e.dc.get_image(img)

    # @unittest.skip("disabled")
    def test_ssm_board_file(self):
        e = ExecutivePluginStub()
        # ensure that existing test images are removed
        try:
            e.dc.remove_image("ssm_empty_container", force=True)
        except BaseException as ex:
            pass
        # try to board a NON existing SSM
        img = e.board_ssm(ssm_uri="file://a_not_existing_container/container.tar")
        self.assertIsNone(img)

        # try to board a existing SSM
        img = e.board_ssm(ssm_uri="file://test/misc/ssm_empty_container.tar")
        # verify that the image is available after boarding
        self.assertIsNotNone(img)
        e.dc.get_image(img)



if __name__ == "__main__":
    unittest.main()
