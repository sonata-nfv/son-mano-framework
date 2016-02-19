"""
Created by Manuel Peuster <manuel@peuster.de>

This module encapsulates RabbitMQ messaging functionality and
provides a set of sync. and async. methods for topic-based
communication.
"""

# TODO: Add API for synchronous request / reply calls
# TODO: Add error handling when broker is not reachable
# TODO: Add RMQ ack mechanism (cf: http://pika.readthedocs.org/en/latest/examples/asynchronous_publisher_example.html)

import pika
import logging
import threading
import time
import uuid
logging.getLogger('pika').setLevel(logging.ERROR)

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"
RABBITMQ_EXCHANGE = "son-kernel"


class ManoBrokerConnection(object):
    """
    This class encapsulates a bare RabbitMQ connection setup.
    It provides helper methods to easily publish/subscribe to a given topic.
    It uses the asynchronous adapter implementation of the pika library.
    """

    def __init__(self, app_id, blocking=False):
        self.app_id = app_id
        self._connection = None
        self._channel = None
        self.rabbitmq_url = RABBITMQ_URL
        self.rabbitmq_exchange = RABBITMQ_EXCHANGE
        self.rabbitmq_exchange_type = "topic"
        self.base_queue = "%s.%s" % (self.rabbitmq_exchange, self.app_id)
        self._connected = False
        self._closing = False
        # trigger connection setup (without blocking)
        self.setup_connection()

    def setup_connection(self, blocking=False):
        """
        Setup RabbitMQ connection, channel, exchange etc.
        :param blocking: do not run IO loop in separated thread
        :return: connection
        """
        # setup RabbitMQ connection
        self._connection = self._connect()

        def connection_thrad():
            # run connection IO loop
            self._connection.ioloop.start()

        if blocking:
            connection_thrad()
            return self._connection

        t = threading.Thread(target=connection_thrad, args=())
        t.daemon = True
        t.start()

        # TODO: quick-hack! Basic connection setup should behave synchronous.
        while not self._connected:
            time.sleep(0.001)
        return self._connection

    def stop_connection(self):
        self._closing = True
        self._connection.close()

    def _connect(self):
        # connect to RabbitMQ
        logging.info("Connecting to RabbitMQ on %r...", self.rabbitmq_url)
        return pika.SelectConnection(parameters=None,
                                     on_open_callback=self._on_connection_open,
                                     on_close_callback=self._on_connection_closed,
                                     stop_ioloop_on_close=False)

    def _reconnect(self):
        self._connection.ioloop.stop()
        if not self._closing:
            self.setup_connection()

    def _setup_channel(self):
        logging.info("Creating a new channel...")
        self._connection.channel(on_open_callback=self._on_channel_open)

    def _setup_exchange(self):
        logging.info("Declaring exchange %r...", self.rabbitmq_exchange)
        self._channel.exchange_declare(self._on_exchange_declared,
                                       self.rabbitmq_exchange,
                                       self.rabbitmq_exchange_type)

    def _setup_queue(self, queue, topic):
        logging.debug("Declaring queue %r...", queue)
        self._channel.queue_declare(self._on_queue_declared, queue)
        logging.debug("Binding queue %r to topic %r..." % (queue, topic))
        self._channel.queue_bind(
            self._on_queue_bound,
            exchange=self.rabbitmq_exchange,
            queue=queue,
            routing_key=topic)

    def _on_connection_open(self, connection):
        logging.debug("Connected: %r" % connection)
        self._setup_channel()

    def _on_channel_open(self, channel):
        logging.debug("Channel created: %r" % channel)
        self._channel = channel
        self._channel.add_on_close_callback(self._on_channel_closed)
        self._setup_exchange()

    def _on_connection_closed(self, connection, reply_code, reply_text):
        self._channel = None
        self._connected = False
        if self._closing:
            self._connection.ioloop.stop()
        else:
            logging.warning("Connection closed, reopening in 5 seconds: (%s) %s",
                            reply_code, reply_text)
            self._connection.add_timeout(5, self._reconnect)

    def _on_channel_closed(self, channel, reply_code, reply_text):
        logging.warning("Channel %i was closed: (%s) %s",
                        channel, reply_code, reply_text)
        self._connection.close()

    def _on_exchange_declared(self, f):
        logging.debug("Exchange declared: %r" % f)
        # self._setup_queue(self.base_queue)
        self._connected = True

    def _on_queue_declared(self, f):
        logging.debug("Queue declared: %r" % f)

    def _on_queue_bound(self, f):
        logging.debug("Queue bound: %r" % f)

    def publish(self, topic, message, properties=None):
        """
        Basic publish/subscribe API.
        Publishes the given message to the given topic.
        """
        if properties is None:
            properties = pika.BasicProperties(
                app_id=self.app_id,
                content_type='application/json')

        self._channel.basic_publish(
            exchange=self.rabbitmq_exchange,
            routing_key=topic,
            body=message,
            properties=properties)
        logging.debug("PUBLISHED to %r: %r", topic, message)

    def subscribe(self, cbf, topic):
        """
        Basic publish/subscribe API.
        Subscribes to the given topic and calls callback whenever a
        message is received.
        """
        topic_receive_queue = self.base_queue + "." + topic
        self._setup_queue(topic_receive_queue, topic)
        # define a callback function to be called whenever a message arrives in our queue
        self._channel.basic_consume(
            cbf,
            queue=topic_receive_queue,
            no_ack=True)
        logging.debug("SUBSCRIBED to %r", topic)


class ManoBrokerRequestResponseConnection(ManoBrokerConnection):
    """
    This class extends the ManoBrokerConnection class and adds functionality
    for a simple request/response messaging pattern on top of the topic-based
    publish/subscribe transport.

    The request/response implementation is strictly asynchronous on both sides:
    - the caller does not block and has to specify a callback function to
      receive a result (its even possible to receive multiple results because of
      the underlying publish/subscribe terminology).
    - the callee provides an RPC like endpoint specified by a keystring and executes
      each request in an independent thread.
    """

    def __init__(self, app_id, blocking=False):
        self._async_calls_pending = {}
        self._async_calls_endpoints = {}
        self._async_calls_request_topics = []
        self._async_calls_response_topics = []
        # call superclass to setup the connection
        super(self.__class__, self).__init__(app_id, blocking=blocking)

    def _execute_async(self, cbf, func, args, props=None):
        """
        Run the given function in an independent thread and call
        cbf when it returns.
        :param cbf: callback function
        :param func: function to execute
        :param args: arguments for executed function
        :param props: broker properties
        :return: None
        """

        def run(cbf, func, args):
            result = func(props, args)
            if cbf is not None:
                cbf(props, result)

        t = threading.Thread(target=run, args=(cbf, func, args))
        t.daemon = True
        t.start()
        logging.debug("Async execution started: %r." % str(func))

    def _on_execute_async_finished(self, props, result):
        """
        Event method that is called when an async. executed function
        has finishes its execution.
        :param props: broker properties
        :param result: return value of executed function
        :return: None
        """
        logging.debug("Async execution finished.")
        # check if we have a response destination
        if props.reply_to is None:
            return  # do not send a response
        # we cannot send None
        result = "" if result is None else result
        assert(isinstance(result, basestring))
        # return its result
        properties=pika.BasicProperties(
            app_id=self.app_id,
            correlation_id=props.correlation_id)
        self.publish(props.reply_to, result, properties=properties)

    def _on_call_async_request_received(self, ch, method, props, body):
        """
        Event method that is called on callee side when an request for an async. call was received.
        Will trigger the local execution of the registered function.
        :param ch: broker channel
        :param method: broker method
        :param props: broker properties
        :param body: message body
        :return: None
        """
        key = "%s.%s" % (method.routing_key, props.headers.get("key"))
        logging.debug("Async request for key %r received." % str(key))
        if key in self._async_calls_endpoints:
            ep = self._async_calls_endpoints.get(key)
            # call the remote procedure asynchronously
            self._execute_async(
                # set a finish method if we want to send a response
                self._on_execute_async_finished if not ep.is_notification else None,
                ep.cbf,
                (body),
                props=props)
        else:
            logging.error("Endpoint not implemented: %r" % key)

    def _on_call_async_response_received(self, ch, method, props, body):
        """
        Event method that is called on caller side when a response for an previously
        issued request is received. Might be called multiple times if more than one callee
        are subscribed to the used topic.
        :param ch: broker channel
        :param method: broker method
        :param props: broker properties
        :param body: message body
        :return: None
        """
        if props.correlation_id in self._async_calls_pending:
            logging.debug("Async response received. Matches to corr_id: %r" % props.correlation_id)
            # call callback
            self._async_calls_pending[props.correlation_id](props, body)
            # remove from pending calls
            del self._async_calls_pending[props.correlation_id]
        else:
            logging.warning("Received malformed call response.")

    def call_async(self, cbf, topic, msg, key="default"):
        """
        Client method to async. call an endpoint registered and bound to the given topic by any
        other component connected to the broker.
        :param cbf: call back function to receive response
        :param topic: topic for communication (callee has to be described to it)
        :param key: optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param msg: actual message
        :return: None
        """
        assert(isinstance(msg, basestring))
        # generate uuid to match requests and responses
        corr_id = str(uuid.uuid4())
        # define response topic
        response_topic = "%s.response" % topic
        # initialize response subscription if a callback function was defined
        if cbf is not None:
            # create subscription for responses
            if topic not in self._async_calls_response_topics:
                self._async_calls_response_topics.append(topic)
                self.subscribe(self._on_call_async_response_received, response_topic)
                # keep track of request
                self._async_calls_pending[corr_id] = cbf
        # setup request message properties
        properties = pika.BasicProperties(
                app_id=self.app_id,
                content_type='application/json',
                reply_to=response_topic if cbf is not None else None,
                correlation_id=corr_id,
                headers={"key": key})
        # publish request message
        self.publish(topic, msg, properties=properties)

    def register_async_endpoint(self, cbf, topic, key="default", is_notification=False):
        """
        Executed by callees that want to expose the functionality implemented in cbf
        to callers that are connected to the broker.
        :param cbf: function to be called when requests with the given topic and key are received
        :param topic: topic for requests and responses
        :param key:  optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param isnotification: define endpoint as notification so that it will not send a response
        :return: None
        """
        # TODO: Can we implement this as a Python function annotation?
        if topic not in self._async_calls_request_topics:
            self._async_calls_request_topics.append(topic)
            self.subscribe(self._on_call_async_request_received, topic)
        self._async_calls_endpoints["%s.%s" % (topic, key)] = AsyncEndpoint(
            cbf, topic, key, is_notification)

    def notify(self, topic, msg, key="default"):
        """
        Wrapper for the call_async method that does not have a callback function since
        it sends notifications instead of requests.
        :param topic: topic for communication (callee has to be described to it)
        :param key: optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param msg: actual message
        :return: None
        """
        self.call_async(None, topic, msg, key=key)

    def register_notification_endpoint(self, cbf, topic, key="default"):
        """
        Wrapper for register_async_endpoint that allows to register
        notification endpoints that to not send responses after executing
        the callback function.
        :param cbf: function to be called when requests with the given topic and key are received
        :param topic: topic for requests and responses
        :param key:  optional identifier for endpoints (enables more than 1 endpoint per topic)
        :return: None
        """
        return self.register_async_endpoint(cbf, topic, key=key, is_notification=True)

    def callback_print(self, ch, method, properties, msg):
        """
        Helper callback that prints the received message.
        """
        logging.debug("RECEIVED from %r on %r: %r" % (
            properties.app_id, method.routing_key, str(msg)))


class AsyncEndpoint(object):
    """
    Class that represents a async. messaging endpoint.
    """

    def __init__(self, cbf, topic, key, is_notifiaction=False):
        self.cbf = cbf
        self.topic = topic
        self.key = key
        self.is_notification = is_notifiaction

