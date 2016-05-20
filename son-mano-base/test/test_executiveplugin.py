"""
Attention: Requires an running RabbitMQ instance.
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


if __name__ == "__main__":
    unittest.main()
