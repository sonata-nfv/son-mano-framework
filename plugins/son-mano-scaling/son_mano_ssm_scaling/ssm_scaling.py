"""
This is SONATA's ssm scaling plugin
"""


import logging
import yaml
import time
import requests
import uuid
import json

from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:ssm_scaling")
LOG.setLevel(logging.DEBUG)

#Topic to register on with SLM
SLM_REGISTRATION_TOPIC = 'ssm.management.register'
#

class SsmScaling(ManoBasePlugin):
    """
    This class implements the scaling ssm.
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
        super(self.__class__, self).__init__(version="0.1-dev",description="This is the SSM plugin")

    def __del__(self):
        """
        Destroy SSM instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics to subscribe to.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()

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
        #SSM lets SLM know it is running. TODO: generalise the name.
        self.manoconn.notify(SLM_REGISTRATION_TOPIC, yaml.dump({'ssm_name': 'ssm_scaling', 'ssm_uuid': self.uuid}))

        #The SSM must subscribe to the topic on which the SLM will make scaling requests. This can't be done in the declare_subscriptions method, since the topic includes the uuid, which is not yet known at that point.
        self.manoconn.register_async_endpoint(self.on_new_scaling_request, 'ssm.scaling.' + str(self.uuid) + '.compute')

        #For now, the SSM imports the different possible scalings and the triggers do differentiate between them.
#        path_descriptors = '/plugins/son-mano-scaling/son_mano_ssm_scaling/scaling_descriptors/'
        path_descriptors = 'scaling_descriptors/'
        scaling_possibilities = open(path_descriptors + 'scaling_possibilities.yml', 'r')
        monitoring_triggers   = open(path_descriptors + 'monitoring_triggers.yml', 'r') 
        self.forwarding_graphs = yaml.load(scaling_possibilities)['forwarding_graphs']
        self.triggers = yaml.load(monitoring_triggers)

    def on_new_scaling_request(self, ch, method, properties, message):
        """
        This method handles scaling requests. The received message should
        be a dictionary. It contains a field 'current_state' to indicate 
        what the current scaling state is. 'current_state' is 0 when the 
        scaling is requested for a first deployment. The dictionary can 
        contain monitoring information in the following field, 'monitoring_input'.
        This is a list of dictionaries, in which each dictionary has the following 
        keys: 'monitoring_metric', 'monitoring_value' and 'monitoring_vnf'.
        """
        msg = yaml.load(message)
        print('scaling request received: ' + str(msg))
        if msg['current_state'] == 0:
            return yaml.dump(self.forwarding_graphs[self.triggers['scale_level_at_boot'] - 1])
        else:
            for trigger in self.triggers:
                if trigger['current_scaling'] == msg['current_state']:
                    current_trigger = trigger
                    break
            if trigger['trigger_metric'] == msg['monitoring_input']['monitoring_metric'] and trigger['trigger_vnf'] == msg['monitoring_input']['monitoring_vnf']:
                if trigger['trigger_value'] >= msg['monitoring_input']['monitoring_value']:
                    new_scale_level = trigger['goto_scaling']
                    self.manoconn.notify('ssm.scaling.' + str(self.uuid) + '.done', yaml.dump(self.forwarding_graphs[new_scale_level]))
        

def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
    # create our ssm scaling plugin
    SsmScaling()

if __name__ == '__main__':
    main()
