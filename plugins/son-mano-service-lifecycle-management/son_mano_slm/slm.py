"""
This is SONATA's service lifecycle management plugin
"""


import logging
from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:slm")
LOG.setLevel(logging.DEBUG)

#
# Configurations
#
# The topic to which service instantiation requests of the GK are published
GK_INSTANCE_CREATE_TOPIC = "service.instances.create"


class ServiceLifecycleManager(ManoBasePlugin):

    def __init__(self):
        # call super class (will automatically connect to broker and register the SLM to the plugin manger)
        super(self.__class__, self).__init__(version="0.1-dev")

    def __del__(self):
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to listen to.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()
        # TODO implement

    def on_registration_ok(self):
        """
        TODO
        """
        LOG.info("Registration OK event")
        # TODO implement

    def on_lifecycle_start(self, ch, method, properties, message):
        """
        TODO
        :param properties:
        :param message:
        :return:
        """
        super(self.__class__, self).on_lifecycle_start(ch, method, properties, message)
        LOG.info("Lifecycle start event")
        # TODO implement

    def on_gk_service_instance_create(self, ch, method, properties, message):
        """

        :param properties:
        :param message:
        :return:
        """
        pass
        # TODO implement


def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
    # create our service lifecycle manager
    ServiceLifecycleManager()

if __name__ == '__main__':
    main()
