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

import unittest
import time

from sonmanobase.messaging import ManoBrokerConnection, ManoBrokerRequestResponseConnection

# TODO the active waiting for messages should be replaced by threading.Event() functionality


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self._message_buffer = list()
        self._message_buffer.append(list())
        self._message_buffer.append(list())
        self.m = None

    def tearDown(self):
        self.m.stop_connection()
        self.m.stop_threads()
        del self.m

    def _simple_subscribe_cbf1(self, ch, method, props, body):
        self.assertIsNotNone(props.app_id)
        self.assertIsNotNone(props.headers)
        self.assertIsNotNone(props.content_type)
        self.waiting = 0
        self._message_buffer[0].append(body)
        print("SUBSCRIBE CBF1: %s" % body)

    def _simple_subscribe_cbf2(self, ch, method, props, body):
        self.assertIsNotNone(props.app_id)
        self.assertIsNotNone(props.headers)
        self.assertIsNotNone(props.content_type)
        self.waiting = 0
        self._message_buffer[1].append(body)
        print("SUBSCRIBE CBF2: %s" % body)

    def _simple_request_echo_cbf(self, ch, method, props, body):
        self.assertIsNotNone(props.app_id)
        self.assertIsNotNone(props.reply_to)
        self.assertIsNotNone(props.correlation_id)
        self.assertIsNotNone(props.headers)
        self.assertIsNotNone(props.content_type)
        print("REQUEST ECHO CBF: %s" % body)
        return body

    def wait_for_messages(self, buffer=0, n_messages=1, timeout=5):
        """
        Helper to deal with async messaging system.
        Waits until a message is written to self._last_message
        or until a timeout is reached.
        :param timeout: seconds to wait
        :return:
        """
        self.waiting = 0
        while len(self._message_buffer[buffer]) < n_messages and self.waiting < timeout:
            time.sleep(0.01)
            self.waiting += 0.01
        if not self.waiting < timeout:
            raise Exception("Message lost. Subscription timeout reached. Buffer: %r" % self._message_buffer[buffer])
        return self._message_buffer[buffer]

    def wait_for_particular_messages(self, message, buffer=0, timeout=5):
        """
        Helper to deal with async messaging system.
        Waits until a the specified message can be found in the buffer.
        :param timeout: seconds to wait
        :return:
        """
        self.waiting = 0
        while message not in self._message_buffer[buffer] and self.waiting < timeout:
            time.sleep(0.01)
            self.waiting += 0.01
        if not self.waiting < timeout:
            raise Exception(
                "Message never found. Subscription timeout reached. Buffer: %r" % self._message_buffer[buffer])
        return True


class TestManoBrokerConnection(BaseTestCase):
    """
    Test basic broker interactions.
    """

    def setUp(self):
        super().setUp()
        self.m = ManoBrokerConnection("test-basic-broker-connection")

    #@unittest.skip("disabled")
    def test_broker_connection(self):
        """
        Test broker connection.
        """
        self.m.publish("test.topic", "testmessage")

    #@unittest.skip("disabled")
    def test_broker_bare_publishsubscribe(self):
        """
        Test publish / subscribe messaging.
        """
        self.m.subscribe(self._simple_subscribe_cbf1, "test.topic")
        time.sleep(1)
        self.m.publish("test.topic", "testmsg")
        self.assertEqual(self.wait_for_messages()[0], "testmsg")

    #@unittest.skip("disabled")
    def test_broker_multi_publish(self):
        """
        Test publish / subscribe messaging.
        """
        self.m.subscribe(self._simple_subscribe_cbf1, "test.topic")
        time.sleep(1)
        for i in range(0, 100):
            self.m.publish("test.topic", "%d" % i)
        self.assertEqual(self.wait_for_messages(n_messages=100)[99], "99")

    #@unittest.skip("disabled")
    def test_broker_doulbe_subscription(self):
        """
        Test publish / subscribe messaging.
        """
        self.m.subscribe(self._simple_subscribe_cbf1, "test.topic")
        self.m.subscribe(self._simple_subscribe_cbf2, "test.topic")
        time.sleep(1)
        for i in range(0, 100):
            self.m.publish("test.topic", "%d" % i)
        self.assertEqual(self.wait_for_messages(buffer=0, n_messages=100)[99], "99")
        self.assertEqual(self.wait_for_messages(buffer=1, n_messages=100)[99], "99")


class TestManoBrokerRequestResponseConnection(BaseTestCase):
    """
    Test async. request/response and notification functionality.
    """

    def setUp(self):
        super().setUp()
        self.m = ManoBrokerRequestResponseConnection("test-request-response-broker-connection")

    #@unittest.skip("disabled")
    def test_broker_connection(self):
        """
        Test broker connection.
        """
        self.m.notify("test.topic2", "simplemessage")

    #@unittest.skip("disabled")
    def test_request_response(self):
        """
        Test request/response messaging pattern.
        """
        self.m.register_async_endpoint(self._simple_request_echo_cbf, "test.request")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.call_async(self._simple_subscribe_cbf1, "test.request", "ping-pong")
        self.assertEqual(self.wait_for_messages()[0], "ping-pong")

    #@unittest.skip("disabled")
    def test_request_response_sync(self):
        """
        Test request/response messaging pattern (synchronous).
        """
        self.m.register_async_endpoint(self._simple_request_echo_cbf, "test.request.sync")
        time.sleep(0.5)  # give broker some time to register subscriptions
        result = self.m.call_sync("test.request.sync", "ping-pong")
        self.assertTrue(len(result) == 4)
        self.assertEqual(str(result[3]), "ping-pong")

    #@unittest.skip("disabled")
    def test_notification(self):
        """
        Test notification messaging pattern.
        """
        self.m.register_notification_endpoint(self._simple_subscribe_cbf1, "test.notification")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.notify("test.notification", "my-notification")
        self.assertTrue(self.wait_for_particular_messages("my-notification"))

    #@unittest.skip("disabled")
    def test_notification_pub_sub_mix(self):
        """
        Test notification messaging pattern mixed with basic pub/sub calls.
        """
        self.m.register_notification_endpoint(self._simple_subscribe_cbf1, "test.notification1")
        self.m.subscribe(self._simple_subscribe_cbf1, "test.notification2")
        time.sleep(0.5)  # give broker some time to register subscriptions
        # send publish to notify endpoint
        self.m.publish("test.notification1", "my-notification1")
        self.assertEqual(self.wait_for_messages()[0], "my-notification1")
        # send notify to subscribe endpoint
        self.m.notify("test.notification2", "my-notification2")
        #res = self.wait_for_messages(n_messages=2)
        self.assertTrue(self.wait_for_particular_messages("my-notification1"))
        self.assertTrue(self.wait_for_particular_messages("my-notification2"))

    #@unittest.skip("disabled")
    def test_double_subscriptions(self):
        """
        Ensure that messages are delivered to all subscriptions of a topic.
        (e.g. identifies queue setup problems)
        :return:
        """
        self.m.subscribe(self._simple_subscribe_cbf1, "test.interleave")
        self.m.subscribe(self._simple_subscribe_cbf2, "test.interleave")
        time.sleep(0.5)
        # send publish to notify endpoint
        self.m.publish("test.interleave", "my-notification1")
        # enusre that it is received by each subscription
        self.assertTrue(self.wait_for_particular_messages("my-notification1", buffer=0))
        self.assertTrue(self.wait_for_particular_messages("my-notification1", buffer=1))

    #@unittest.skip("disabled")
    def test_interleaved_subscriptions(self):
        """
        Ensure that interleaved subscriptions to the same topic do not lead to problems.
        :return:
        """
        self.m.subscribe(self._simple_subscribe_cbf2, "test.interleave2")
        time.sleep(0.5)
        # do a async call on the same topic
        self.m.register_async_endpoint(self._simple_request_echo_cbf, "test.interleave2")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.call_async(self._simple_subscribe_cbf1, "test.interleave2", "ping-pong")
        self.assertTrue(self.wait_for_particular_messages("ping-pong"))
        # send publish to notify endpoint
        self.m.publish("test.interleave2", "my-notification1")
        time.sleep(0.5)
        # ensure that the subcriber still gets the message (and also sees the one from async_call)
        self.assertTrue(self.wait_for_particular_messages("ping-pong"))
        self.assertTrue(self.wait_for_particular_messages("my-notification1", buffer=1))

if __name__ == "__main__":
    #unittest.main()
    t = TestManoBrokerRequestResponseConnection()
    t.setUp()
    t.test_request_response()
    t.tearDown()


