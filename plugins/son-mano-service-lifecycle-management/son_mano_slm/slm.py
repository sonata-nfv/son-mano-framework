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
    """
    This class implements the service lifecycle manager.

    see: https://github.com/sonata-nfv/son-mano-framework/issues/23
    """

    def __init__(self):
        """
        Initialize class and son-mano-base.plugin.BasePlugin class.
        This will automatically connect to the broker, contact the
        plugin manager, and self-register this plugin to the plugin
        manager.

        After the connection and registration procedures are done, the
        'on_lifecycle_start' method is called.
        :return:
        """
        # call super class (will automatically connect to broker and register the SLM to the plugin manger)
        super(self.__class__, self).__init__(version="0.1-dev")

    def __del__(self):
        """
        Destroy SLM instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to subscribe to.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()
        #
        # GK <-> SLM interface
        #
        # We want to subscribe to GK_INSTANCE_CREATE_TOPIC to react on GK messages
        self.manoconn.register_notification_endpoint(
            self.on_gk_service_instance_create,  # function called when message received
            GK_INSTANCE_CREATE_TOPIC)  # topic to listen to
        #
        # SLM <-> infra. adaptor interface
        #
        # TODO implement reply topics for infrastructure adapter

    def on_lifecycle_start(self, ch, method, properties, message):
        """
        This event is called after the plugin has successfully registered itself
        to the plugin manager and received its lifecycle.start event from the
        plugin manager. The plugin is expected to do its work after this event.

        This is a default method each plugin should implement.

        :param ch: RabbitMQ channel
        :param method: RabbitMQ method
        :param properties: RabbitMQ properties
        :param message: RabbitMQ message content
        :return:
        """
        super(self.__class__, self).on_lifecycle_start(ch, method, properties, message)
        LOG.info("Lifecycle start event")
        # TODO does the SLM need to perform any actions after it has been started?

    def on_gk_service_instance_create(self, ch, method, properties, message):
        """
        This is our first SLM specific event method. It is called when the SLM
        receives a message from the GK published to GK_INSTANCE_CREATE_TOPIC.

        Here we should react and trigger the service instantiation.

        :param ch: RabbitMQ channel
        :param method: RabbitMQ method
        :param properties: RabbitMQ properties
        :param message: RabbitMQ message content
        :return:
        """
        LOG.info("GK service.instance.start event")
        # TODO implement
        # What has do be done? E.g.:
        # 1. extract NSD etc. from message
        # 2. (do translations)
        # 3. send requests to infra adaptor
        # 4. write back NSR to repository
        # 5. send an acknowledgement to the GK


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
