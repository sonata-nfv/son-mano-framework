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
import time

from sonmanobase.messaging import ManoBrokerConnection, ManoBrokerRequestResponseConnection

# TODO the active waiting for messages should be replaced by threading.Event() functionality

class TestManoBrokerConnection(unittest.TestCase):
    """
    Test basic broker interactions.
    """

    def setUp(self):
        self._last_message = [None, None, None , None]
        self.m = ManoBrokerConnection("test")

    def tearDown(self):
        del self.m

    def _simple_subscribe_cbf(self, ch, method, props, body):
        self._last_message[0] = str(body, "utf-8")

    def _simple_subscribe_cbf2(self, ch, method, props, body):
        self._last_message[1] = str(body, "utf-8")

    def wait_for_message(self, last_message_id=0, timeout=2):
        """
        Helper to deal with async messaging system.
        Waits until a message is written to self._last_message
        or until a timeout is reached.
        :param timeout: seconds to wait
        :return:
        """
        waiting = 0
        while self._last_message[last_message_id] is None and waiting < timeout:
            time.sleep(0.01)
            waiting += 0.01
        if not waiting < timeout:
            raise Exception("Message lost. Subscription timeout reached.")
            return None
        m = self._last_message[last_message_id]
        self._last_message[last_message_id] = None
        return m

    def test_broker_connection(self):
        """
        Test broker connection.
        """
        self.m.publish("test.topic", "testmessage")

    def test_broker_bare_publishsubscribe(self):
        """
        Test publish / subscribe messaging.
        """
        self.m.subscribe(self._simple_subscribe_cbf, "test.topic")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.publish("test.topic", "testmessage")
        self.assertEqual(self.wait_for_message(), "testmessage")


class TestManoBrokerRequestResponseConnection(unittest.TestCase):
    """
    Test async. request/response and notification functionality.
    """

    def setUp(self):
        self._last_message = [None, None, None, None]
        self.m = ManoBrokerRequestResponseConnection("test")

    def tearDown(self):
        del self.m

    def _simple_request_echo_cbf(self, ch, method, properties, message):
        """
        Simple echo function.
        """
        assert(properties.correlation_id is not None)
        assert(properties.reply_to is not None)
        assert(properties.content_type == "application/json")
        assert("key" in properties.headers)
        return str(message, "utf-8")

    def _simple_message_cbf(self, ch, method, props, body):
        self._last_message[0] = str(body, "utf-8")

    def _simple_message_cbf2(self, ch, method, props, body):
        self._last_message[1] = str(body, "utf-8")

    def wait_for_message(self, last_message_id=0, timeout=2):
        """
        Helper to deal with async messaging system.
        Waits until a message is written to self._last_message
        or until a timeout is reached.
        :param timeout: seconds to wait
        :return:
        """
        waiting = 0
        while self._last_message[last_message_id] is None and waiting < timeout:
            time.sleep(0.01)
            waiting += 0.01
        if not waiting < timeout:
            raise Exception("Message lost. Subscription timeout reached.")
            return None
        m = self._last_message[last_message_id]
        self._last_message[last_message_id] = None
        return m

    def test_broker_connection(self):
        """
        Test broker connection.
        """
        self.m.notify("test.topic", "simplemessage")

    def test_request_response(self):
        """
        Test request/response messaging pattern.
        """
        self.m.register_async_endpoint(self._simple_request_echo_cbf, "test.request")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.call_async(self._simple_message_cbf, "test.request", "ping-pong")
        self.assertEqual(self.wait_for_message(), "ping-pong")

    def test_request_response_sync(self):
        """
        Test request/response messaging pattern (synchronous).
        """
        self.m.register_async_endpoint(self._simple_request_echo_cbf, "test.request.sync")
        time.sleep(0.5)  # give broker some time to register subscriptions
        result = self.m.call_sync("test.request.sync", "ping-pong")
        self.assertTrue(len(result) == 4)
        self.assertEqual(str(result[3], "utf-8"), "ping-pong")

    def test_notification(self):
        """
        Test notification messaging pattern.
        """
        self.m.register_notification_endpoint(self._simple_message_cbf, "test.notification")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.notify("test.notification", "my-notification")
        self.assertEqual(self.wait_for_message(), "my-notification")

    def test_notification_pub_sub_mix(self):
        """
        Test notification messaging pattern mixed with basic pub/sub calls.
        """
        self.m.register_notification_endpoint(self._simple_message_cbf, "test.notification1")
        self.m.subscribe(self._simple_message_cbf, "test.notification2")
        time.sleep(0.5)  # give broker some time to register subscriptions
        # send publish to notify endpoint
        self.m.publish("test.notification1", "my-notification1")
        self.assertEqual(self.wait_for_message(), "my-notification1")
        # send notify to subscribe endpoint
        self.m.notify("test.notification2", "my-notification2")
        self.assertEqual(self.wait_for_message(), "my-notification2")

    #@unittest.skip("disabled")
    def test_double_subscriptions(self):
        """
        Ensure that messages are delivered to all subscriptions of a topic.
        (e.g. identifies queue setup problems)
        :return:
        """
        self.m.subscribe(self._simple_message_cbf, "test.interleave")
        self.m.subscribe(self._simple_message_cbf2, "test.interleave")
        time.sleep(0.5)
        # send publish to notify endpoint
        self.m.publish("test.interleave", "my-notification1")
        # enusre that it is received by each subscription
        self.assertEqual(self.wait_for_message(), "my-notification1")
        self.assertEqual(self.wait_for_message(last_message_id=1), "my-notification1")

    #@unittest.skip("disabled")
    def test_interleaved_subscriptions(self):
        """
        Ensure that interleaved subscriptions to the same topic do not lead to problems.
        :return:
        """
        self.m.subscribe(self._simple_message_cbf2, "test.interleave2")
        time.sleep(0.5)
        # do a async call on the same topic
        self.m.register_async_endpoint(self._simple_request_echo_cbf, "test.interleave2")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.call_async(self._simple_message_cbf, "test.interleave2", "ping-pong")
        self.assertEqual(self.wait_for_message(), "ping-pong")
        # send publish to notify endpoint
        self.m.publish("test.interleave2", "my-notification1")
        # ensure that the subcriber still gets the message (and also sees the one from async_call)
        self.assertEqual(self.wait_for_message(last_message_id=1), "ping-pong")
        self.assertEqual(self.wait_for_message(last_message_id=1), "my-notification1")

if __name__ == "__main__":
    unittest.main()
