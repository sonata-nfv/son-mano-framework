import unittest
import time

from sonmanobase.messaging import ManoBrokerConnection, ManoBrokerRequestResponseConnection


class TestManoBrokerConnection(unittest.TestCase):
    """
    Test basic broker interactions.
    """

    def setUp(self):
        self._last_message = None
        self.m = ManoBrokerConnection("test")

    def tearDown(self):
        del self.m

    def _simple_subscribe_cbf(self, ch, method, props, body):
        self._last_message = str(body, "utf-8")

    def wait_for_message(self, timeout=2):
        """
        Helper to deal with async messaging system.
        Waits until a message is written to self._last_message
        or until a timeout is reached.
        :param timeout: seconds to wait
        :return:
        """
        waiting = 0
        while self._last_message is None and waiting < timeout:
            time.sleep(0.01)
            waiting += 0.01
        if not waiting < timeout:
            raise Exception("Message lost. Subscription timeout reached.")
            return None
        m = self._last_message
        self._last_message = None
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
        self._last_message = None
        self.m = ManoBrokerRequestResponseConnection("test")

    def tearDown(self):
        del self.m

    def _simple_request_echo_cbf(self, ch, method, properties, message):
        """
        Simple echo function.
        """
        return str(message, "utf-8")

    def _simple_message_cbf(self, ch, method, properties, message):
        self._last_message = str(message, "utf-8")

    def wait_for_messag(self, timeout=2):
        """
        Helper to deal with async messaging system.
        Waits until a response is available in self._last_message
        or until a timeout is reached.
        :param timeout: seconds to wait
        :return:
        """
        waiting = 0
        while self._last_message is None and waiting < timeout:
            time.sleep(0.01)
            waiting += 0.01
        if not waiting < timeout:
            raise Exception("Message lost. Subscription timeout reached.")
        m = self._last_message
        self._last_message = None
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
        self.assertEqual(self.wait_for_messag(), "ping-pong")

    def test_notification(self):
        """
        Test notification messaging pattern.
        """
        self.m.register_notification_endpoint(self._simple_message_cbf, "test.notification")
        time.sleep(0.5)  # give broker some time to register subscriptions
        self.m.notify("test.notification", "my-notification")
        self.assertEqual(self.wait_for_messag(), "my-notification")


if __name__ == "__main__":
    unittest.main()
