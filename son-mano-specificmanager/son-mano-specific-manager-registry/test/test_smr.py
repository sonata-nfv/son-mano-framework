import unittest
import threading
import time
import yaml
import logging
from multiprocessing import Process

try:
    from test.onboarding import fakeslm_onboarding
except:
    from onboarding import fakeslm_onboarding

try:
    from test.instantiation import fakeslm_instantiation
except:
    from instantiation import fakeslm_instantiation

try:
    from test.updating import fakeslm_updating
except:
    from updating import fakeslm_updating

try:
    from test.terminating import fakeslm_termination
except:
    from terminating import fakeslm_termination
from sonmanobase.messaging import ManoBrokerRequestResponseConnection
from son_mano_specific_manager_registry.specificmanagerregistry import SpecificManagerRegistry


logging.basicConfig(level=logging.INFO)
logging.getLogger('amqp-storm').setLevel(logging.INFO)
LOG = logging.getLogger("son-mano-plugins:smr_test")
logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
LOG.setLevel(logging.INFO)

class test_SMR_functionalities(unittest.TestCase):

    @classmethod
    def setUpClass(self):

        self.smr_proc = Process(target=SpecificManagerRegistry)

        self.smr_proc.daemon = True

        self.manoconn = ManoBrokerRequestResponseConnection('son-plugin.SpecificManagerRegistry')


        self.wait_for_ssm_event = threading.Event()
        self.wait_for_ssm_event.clear()

        self.wait_for_fsm_event = threading.Event()
        self.wait_for_fsm_event.clear()

        self.event1 = False
        self.event2 = False

        self.smr_proc.start()
        time.sleep(4)

    @classmethod
    def tearDownClass(self):

        if self.smr_proc is not None:
            self.smr_proc.terminate()
        del self.smr_proc

        try:
            self.manoconn.stop_connection()
        except Exception as e:
            LOG.exception("Stop connection exception.")

        del self.wait_for_fsm_event
        del self.wait_for_ssm_event

    def ssm_eventFinished(self):
        self.wait_for_ssm_event.set()


    def waitForSSMEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_ssm_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)


    def fsm_eventFinished(self):
        self.wait_for_fsm_event.set()


    def waitForFSMEvent(self, timeout=5, msg="Event timed out."):
        if not self.wait_for_fsm_event.wait(timeout):
            self.assertEqual(True, False, msg=msg)

    def test_1_SMR_onboard(self):

        self.event1 = False
        self.event2 = False

        def on_ssm_onboarding_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':
                result = yaml.load(message)

                self.assertTrue(list(result.keys()) == ['sonssmservice1dumb1','sonssmservice1placement1'] or
                                list(result.keys()) == ['sonssmservice1placement1', 'sonssmservice1dumb1'],
                                msg='not all SSMs results received')

                self.assertTrue(result['sonssmservice1dumb1']['status'] == 'On-boarded',
                                msg='error in onbording sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1dumb1']['error'] == 'None',
                                msg='error in onbording sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1placement1']['status'] == 'On-boarded',
                                msg='error in onbording sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1placement1']['error'] == 'None',
                                msg='error in onbording sonssmservice1placement1')

                self.ssm_eventFinished()

        def on_fsm_onboarding_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':

                result = yaml.load(message)
                if list(result.keys()) == ['sonfsmservice1function1dumb1']:

                    self.assertTrue(list(result.keys()) == ['sonfsmservice1function1dumb1'],
                                    msg='not all FSMs results in VNFD1 received')

                    self.assertTrue(result['sonfsmservice1function1dumb1']['status'] == 'On-boarded',
                                    msg='error in onbording sonssmservice1dumb1')

                    self.assertTrue(result['sonfsmservice1function1dumb1']['error'] == 'None',
                                    msg='error in onbording sonfsmservice1function1dumb1')

                    self.event1 = True
                else:
                    self.assertTrue(list(result.keys()) ==
                                    ['sonfsmservice1function1monitoring1', 'sonfsmservice1firewallconfiguration1']or
                                    list(result.keys()) ==
                                    ['sonfsmservice1firewallconfiguration1','sonfsmservice1function1monitoring1']
                                    , msg='not all FSMs results in VNFD2 received')

                    self.assertTrue(result['sonfsmservice1function1monitoring1']['status'] == 'On-boarded',
                                    msg='error in onbording sonssmservice1dumb1')

                    self.assertTrue(result['sonfsmservice1function1monitoring1']['error'] == 'None',
                                    msg='error in onbording sonfsmservice1function1monitoring1')

                    self.assertTrue(result['sonfsmservice1firewallconfiguration1']['status'] == 'On-boarded',
                                    msg='error in onbording sonssmservice1dumb1')

                    self.assertTrue(result['sonfsmservice1firewallconfiguration1']['error'] == 'None',
                                    msg='error in onbording sonfsmservice1firewallconfiguration1')

                    self.event2 = True

                if self.event1 and self.event2 == True:
                    self.fsm_eventFinished()



        self.manoconn.subscribe(on_ssm_onboarding_result, 'specific.manager.registry.ssm.on-board')
        self.manoconn.subscribe(on_fsm_onboarding_result, 'specific.manager.registry.fsm.on-board')

        onboaring_proc = Process(target=fakeslm_onboarding)
        onboaring_proc.daemon = True

        onboaring_proc.start()

        self.waitForSSMEvent(timeout=70 , msg='SSM Onboarding request not received.')
        self.waitForFSMEvent(timeout=70, msg='FSM Onboarding request not received.')

        self.wait_for_fsm_event.clear()
        self.wait_for_ssm_event.clear()

        onboaring_proc.terminate()
        del onboaring_proc


    def test_2_SMR_instantiation(self):

        self.event1 = False
        self.event2 = False

        def on_ssm_instantiation_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':
                result = yaml.load(message)
                self.assertTrue(list(result.keys()) == ['sonssmservice1dumb1', 'sonssmservice1placement1'] or
                                list(result.keys()) == ['sonssmservice1placement1', 'sonssmservice1dumb1'],
                                msg='not all SSMs results received')

                self.assertTrue(result['sonssmservice1dumb1']['status'] == 'Instantiated',
                                msg='error in instantiation sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1dumb1']['error'] == 'None',
                                msg='error in instantiation sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1placement1']['status'] == 'Instantiated',
                                msg='error in instantiation sonssmservice1placement1')

                self.assertTrue(result['sonssmservice1placement1']['error'] == 'None',
                                msg='error in instantiation sonssmservice1placement1')

                self.ssm_eventFinished()

        def on_fsm_instantiation_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':

                result = yaml.load(message)
                if list(result.keys()) == ['sonfsmservice1function1dumb1']:

                    self.assertTrue(list(result.keys()) == ['sonfsmservice1function1dumb1'],
                                    msg='not all FSMs instantiation results in VNFD1 received')

                    self.assertTrue(result['sonfsmservice1function1dumb1']['status'] == 'Instantiated',
                                    msg='error in instantiation sonfsmservice1function1dumb1')

                    self.assertTrue(result['sonfsmservice1function1dumb1']['error'] == 'None',
                                    msg='error in instantiation sonfsmservice1function1dumb1')

                    self.event1 = True
                else:
                    self.assertTrue(list(result.keys()) ==
                                    ['sonfsmservice1function1monitoring1', 'sonfsmservice1firewallconfiguration1'] or
                                    list(result.keys()) ==
                                    ['sonfsmservice1firewallconfiguration1', 'sonfsmservice1function1monitoring1']
                                    , msg='not all FSMs instantiation results in VNFD2 received')

                    self.assertTrue(result['sonfsmservice1function1monitoring1']['status'] == 'Instantiated',
                                    msg='error in instantiation sonfsmservice1function1monitoring1')

                    self.assertTrue(result['sonfsmservice1function1monitoring1']['error'] == 'None',
                                    msg='error in instantiation sonfsmservice1function1monitoring1')

                    self.assertTrue(result['sonfsmservice1firewallconfiguration1']['status'] == 'Instantiated',
                                    msg='error in instantiation sonfsmservice1firewallconfiguration1')

                    self.assertTrue(result['sonfsmservice1firewallconfiguration1']['error'] == 'None',
                                    msg='error in instantiation sonfsmservice1firewallconfiguration1')

                    self.event2 = True

                if self.event1 and self.event2:
                    self.fsm_eventFinished()

        self.manoconn.subscribe(on_ssm_instantiation_result, 'specific.manager.registry.ssm.instantiate')
        self.manoconn.subscribe(on_fsm_instantiation_result, 'specific.manager.registry.fsm.instantiate')

        instantiation_proc = Process(target=fakeslm_instantiation)
        instantiation_proc.daemon = True

        instantiation_proc.start()

        self.waitForSSMEvent(timeout=70, msg='SSM instantiation request not received.')
        self.waitForFSMEvent(timeout=70, msg='FSM instantiation request not received.')

        self.wait_for_ssm_event.clear()
        self.wait_for_fsm_event.clear()

        instantiation_proc.terminate()
        del instantiation_proc


    def test_3_SMR_update(self):

        def on_ssm_updating_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':
                result = yaml.load(message)
                self.assertTrue(list(result.keys()) == ['sonssmservice1dumb1'],
                                msg='not all SSMs results received')

                self.assertTrue(result['sonssmservice1dumb1']['status'] == 'Updated',
                                msg='error in updating status filed sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1dumb1']['error'] == 'None',
                                msg='error in updating error filed sonssmservice1dumb1')

                self.ssm_eventFinished()

        def on_fsm_updating_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':

                result = yaml.load(message)
                self.assertTrue(list(result.keys()) ==
                                ['sonfsmservice1function1updateddumb1']
                                , msg='not all FSMs updating results in VNFD2 received')

                self.assertTrue(result['sonfsmservice1function1updateddumb1']['status'] == 'Updated',
                                msg='error in updating sonfsmservice1function1monitoring1')

                self.assertTrue(result['sonfsmservice1function1updateddumb1']['error'] == 'None',
                                msg='error in updating sonfsmservice1function1monitoring1')

                self.fsm_eventFinished()

        self.manoconn.subscribe(on_ssm_updating_result, 'specific.manager.registry.ssm.update')
        self.manoconn.subscribe(on_fsm_updating_result, 'specific.manager.registry.fsm.update')

        updating_proc = Process(target=fakeslm_updating)
        updating_proc.daemon = True
        updating_proc.start()

        self.waitForSSMEvent(timeout=70, msg='SSM updating request not received.')
        self.waitForFSMEvent(timeout=70, msg='FSM updating request not received.')

        self.wait_for_fsm_event.clear()
        self.wait_for_ssm_event.clear()

        updating_proc.terminate()
        del updating_proc

    def test_4_SMR_terminate(self):

        self.event1 = False
        self.event2 = False

        def on_ssm_termination_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':
                result = yaml.load(message)
                self.assertTrue(list(result.keys()) == ['sonssmservice1dumb1','sonssmservice1placement1'] or
                                ['sonssmservice1placement1','sonssmservice1dumb1'],
                                msg='not all SSMs results received')

                self.assertTrue(result['sonssmservice1dumb1']['status'] == 'Terminated',
                                msg='error in termination status field sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1dumb1']['error'] == 'None',
                                msg='error in termination error field sonssmservice1dumb1')

                self.assertTrue(result['sonssmservice1placement1']['status'] == 'Terminated',
                                msg='error in termination status field sonssmservice1placement1')

                self.assertTrue(result['sonssmservice1placement1']['error'] == 'None',
                            msg='error in termination error field sonssmservice1placement1')

                self.ssm_eventFinished()

        def on_fsm_termination_result(ch, method, properties, message):

            if properties.app_id == 'son-plugin.SpecificManagerRegistry':

                result = yaml.load(message)

                if list(result.keys()) == ['sonfsmservice1function1dumb1']:

                    self.assertTrue(result['sonfsmservice1function1dumb1']['status'] == 'Terminated',
                                    msg='error in termination status field sonfsmservice1function1dumb1')

                    self.assertTrue(result['sonfsmservice1function1dumb1']['error'] == 'None',
                                msg='error in termination error field sonfsmservice1function1dumb1')

                    self.event1 = True

                else:
                    self.assertTrue(list(result.keys()) ==
                                    ['sonfsmservice1function1monitoring1', 'sonfsmservice1function1updateddumb1'] or
                                    list(result.keys()) ==
                                    ['sonfsmservice1function1updateddumb1', 'sonfsmservice1function1monitoring1']
                                    , msg='not all FSMs Termination results in vnfdt2 received')

                    self.assertTrue(result['sonfsmservice1function1monitoring1']['status'] == 'Terminated',
                                    msg='error in termination status field sonfsmservice1function1monitoring1')

                    self.assertTrue(result['sonfsmservice1function1monitoring1']['error'] == 'None',
                                msg='error in termination error field sonfsmservice1function1monitoring1')

                    self.assertTrue(result['sonfsmservice1function1updateddumb1']['status'] == 'Terminated',
                                    msg='error in termination status field sonfsmservice1function1updateddumb1')

                    self.assertTrue(result['sonfsmservice1function1updateddumb1']['error'] == 'None',
                                msg='error in termination error field sonfsmservice1function1updateddumb1')

                    self.event2 = True

                self.fsm_eventFinished()

            if self.event1 and self.event2:
                self.fsm_eventFinished()

        self.manoconn.subscribe(on_ssm_termination_result, 'specific.manager.registry.ssm.terminate')
        self.manoconn.subscribe(on_fsm_termination_result, 'specific.manager.registry.fsm.terminate')

        termination_proc = Process(target=fakeslm_termination)
        termination_proc.daemon = True
        termination_proc.start()

        self.waitForSSMEvent(timeout=70, msg='SSM termination request not received.')
        self.waitForFSMEvent(timeout=70, msg='FSM termination request not received.')

        self.wait_for_fsm_event.clear()
        self.wait_for_ssm_event.clear()

        termination_proc.terminate()
        del termination_proc

if __name__ == "__main__":
    unittest.main()