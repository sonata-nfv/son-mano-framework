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
"""
Created by Manuel Peuster <manuel@peuster.de>

This module encapsulates RabbitMQ messaging functionality and
provides a set of sync. and async. methods for topic-based
communication.
"""

# TODO: Add RMQ ack mechanism (cf: http://pika.readthedocs.org/en/latest/examples/asynchronous_publisher_example.html)

from amqpstorm import UriConnection
import logging
import threading
import time
import uuid
import os

logging.basicConfig(level=logging.INFO)
logging.getLogger('pika').setLevel(logging.ERROR)
LOG = logging.getLogger("son-mano-base:messaging")
LOG.setLevel(logging.DEBUG)

# if we don't find a broker configuration in our ENV, we use this URL as default
RABBITMQ_URL_FALLBACK = "amqp://guest:guest@localhost:5672/%2F"
# if we don't find a broker configuration in our ENV, we use this exchange as default
RABBITMQ_EXCHANGE_FALLBACK = "son-kernel"


class ManoBrokerConnection(object):
    """
    This class encapsulates a bare RabbitMQ connection setup.
    It provides helper methods to easily publish/subscribe to a given topic.
    It uses the asynchronous adapter implementation of the pika library.
    """

    def __init__(self, app_id, blocking=False):
        self.app_id = app_id
        # fetch configuration
        self.rabbitmq_url = os.environ.get("broker_host", RABBITMQ_URL_FALLBACK)
        self.rabbitmq_exchange = os.environ.get("broker_exchange", RABBITMQ_EXCHANGE_FALLBACK)
        self.rabbitmq_exchange_type = "topic"

        # create additional members
        self._connection = None

        # trigger connection setup (without blocking)
        self.setup_connection()

    def setup_connection(self):
        """
        Connect to rabbit mq using self.rabbitmq_url.
        """
        self._connection = UriConnection(self.rabbitmq_url)
        return self._connection

    def stop_connection(self):

        try:
            self._connection.close()
        except pika.exceptions.ConnectionClosed:
            LOG.exception("Stop connection error")


    def publish(self,
                topic,
                message,
                content_type="application/json",
                correlation_id=None,
                reply_to=None,
                headers={},
                properties=None
                ):
        """
        Publishes the given message to the given topic.
        :param topic: topic to which the message is published
        :param message: message contents
        :param content_type: type of message
        :param correlation_id: ID to identify messages
        :param headers: header dict
        :param properties: pika.BasicProperties will overwrite other property arguments.
        :return:
        """
        with self._connection.channel() as channel:
            channel.exchange.declare(self.rabbitmq_exchange, exchange_type=self.rabbitmq_exchange_type)

            # Declare the Queue, 'simple_queue'.
            #channel.queue.declare(topic)

            # Message Properties.
            if properties is None:
                properties = {
                    "app_id": self.app_id,
                    "content_type": content_type,
                    "correlation_id": correlation_id,
                    "reply_to": reply_to,
                    "headers": headers
                }

            # Publish the message to a queue called, 'simple_queue'.
            channel.basic.publish(body=message,
                                  routing_key=topic,
                                  exchange=self.rabbitmq_exchange,
                                  properties=properties)


        #self._channel.basic_publish(
        #    exchange=self.rabbitmq_exchange,
        #    routing_key=topic,
        #    body=message,
        #    properties=properties)

        #self._channel.queue.declare(topic)


        LOG.debug("PUBLISHED to %r: %r", topic, message)

    def subscribe(self, cbf, topic):
        """
        Basic publish/subscribe API.
        Subscribes to the given topic and calls callback whenever a
        message is received.
        :return: consumer tag
        """
        # ATTENTION: Queues are identified by base_queue_name, topic, and a uuid for this
        # particular subscription. Ensures that we have exactly one queue per subscription.
        topic_receive_queue = "%s.%s.%s" % (self.base_queue, topic, str(uuid.uuid1()))
        #self._setup_queue(topic_receive_queue, topic)
        # define a callback function to be called whenever a message arrives in our queue
        #bc = self._channel.basic_consume(
        #        cbf,
        #        queue=topic_receive_queue,
        #        no_ack=True)
        consumer_tag = str(uuid.uuid4())

        def wrapper_cbf(msg):
            # do translation to lagacy cbf format
            #  ch, method, props, body
            ch = msg.channel
            method_dict = msg.method
            properties_dict = msg.properties
            body = msg.body

            LOG.debug("ch: %r" % ch)
            LOG.debug("method: %r" % method_dict)
            LOG.debug("properties: %r" % properties_dict)

            method = type('method', (object,), method_dict)
            properties = type('properties', (object,), properties_dict)

            LOG.debug("method o: %r" % method)
            LOG.debug("properties o: %r" % properties)


            cbf(ch, method, properties, body)


        def connection_thread():
            with self._connection.channel() as channel:

                channel.exchange.declare(exchange=self.rabbitmq_exchange, exchange_type=self.rabbitmq_exchange_type)
                # def declare(self, exchange='', exchange_type='direct', passive=False,
                #durable=False, auto_delete=False, arguments=None):

                # Declare the Queue, 'simple_queue'.
                q = channel.queue
                q.declare(topic_receive_queue)
                q.bind(queue=topic_receive_queue, routing_key=topic, exchange=self.rabbitmq_exchange)
                #bind(self, queue='', exchange='', routing_key='', arguments=None):

                # Set QoS to 100.
                # This will limit the consumer to only prefetch a 100 messages.

                # This is a recommended setting, as it prevents the
                # consumer from keeping all of the messages in a queue to itself.
                channel.basic.qos(100)

                # Start consuming the queue 'simple_queue' using the callback
                # 'on_message' and last require the message to be acknowledged.
                channel.basic.consume(wrapper_cbf, topic_receive_queue, consumer_tag=consumer_tag, no_ack=True)

                try:
                    # Start consuming messages.
                    # to_tuple equal to False means that messages consumed
                    # are returned as a Message object, rather than a tuple.
                    channel.start_consuming(to_tuple=False)
                except BaseException:
                    LOG.exception("Error in subscription thread")
                    channel.close()


        t = threading.Thread(target=connection_thread, args=())
        t.daemon = True
        t.start()

        LOG.debug("SUBSCRIBED to %r", topic)
        return consumer_tag


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

    def _execute_async(self, cbf, func, ch, method, props, body):
        """
        Run the given function in an independent thread and call
        cbf when it returns.
        :param cbf: callback function
        :param func: function to execute
        :param ch: channel of message
        :param method: rabbit mq method
        :param props: broker properties
        :param body: body of the request message
        :return: None
        """

        def run(cbf, func, ch, method, props, body):
            result = func(ch, method, props, body)
            if cbf is not None:
                cbf(ch, method, props, result)

        t = threading.Thread(target=run, args=(cbf, func, ch, method, props, body))
        t.daemon = True
        t.start()
        LOG.debug("Async execution started: %r." % str(func))

    def _on_execute_async_finished(self, ch, method, props, result):
        """
        Event method that is called when an async. executed function
        has finishes its execution.
        :param ch: channel of message
        :param method: rabbit mq method
        :param props: broker properties
        :param result: return value of executed function
        :return: None
        """
        LOG.debug("Async execution finished.")
        # check if we have a response destination
        if props.reply_to is None or props.reply_to == "NO_RESPONSE":
            return  # do not send a response
        # we cannot send None
        result = "" if result is None else result
        assert(isinstance(result, str))
        # return its result
        self.publish(props.reply_to, result,
                     correlation_id=props.correlation_id,
                     headers={"key": None, "type": "reply"})

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
        LOG.debug(
            "Async request on topic %r received." % method.routing_key)
        if method.consumer_tag in self._async_calls_endpoints:
            ep = self._async_calls_endpoints.get(method.consumer_tag)
            # check if we really have a request (or a notification), not a response
            if props.reply_to is None and not ep.is_notification:
                LOG.debug("Non-request message dropped at request endpoint.")
                return
            # call the remote procedure asynchronously
            self._execute_async(
                # set a finish method if we want to send a response
                self._on_execute_async_finished if not ep.is_notification else None,
                ep.cbf, ch, method, props, body)
        else:
            LOG.error(
                "Endpoint not implemented: %r " % method.consumer_tag)

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
        # check if we really have a response, not a request
        if props.reply_to is not None:
            LOG.debug("Non-response message dropped at response endpoint.")
            return
        if props.correlation_id in self._async_calls_pending:
            LOG.debug("Async response received. Matches to corr_id: %r" % props.correlation_id)
            # call callback
            self._async_calls_pending[props.correlation_id](ch, method, props, body)
            # remove from pending calls
            del self._async_calls_pending[props.correlation_id]
        else:
            LOG.debug("Received unmatched call response. Ignore it.")

    def call_async(self, cbf, topic, msg=None, key="default",
                   content_type="application/json",
                   correlation_id=None,
                   headers={},
                   response_topic_postfix=""):
        """
        Client method to async. call an endpoint registered and bound to the given topic by any
        other component connected to the broker.
        :param cbf: call back function to receive response
        :param topic: topic for communication (callee has to be described to it)
        :param msg: actual message
        :param key: optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param content_type: type of message
        :param correlation_id: allow to set individual correlation ids
        :param headers: header dict
        :param response_topic_postfix: postfix of response topic
        :return: None
        """
        if msg is None:
            msg = "{}"
        assert(isinstance(msg, str))
        # generate uuid to match requests and responses
        corr_id = str(uuid.uuid4()) if correlation_id is None else correlation_id
        # define response topic
        response_topic = "%s%s" % (topic, response_topic_postfix)
        # initialize response subscription if a callback function was defined
        if cbf is not None:
            # create subscription for responses
            if topic not in self._async_calls_response_topics:
                self.subscribe(self._on_call_async_response_received, response_topic)
            # keep track of request
            self._async_calls_response_topics.append(topic)
            self._async_calls_pending[corr_id] = cbf
        # ensure that optional key is included into header
        headers["key"] = key
        headers["type"] = "request"
        # publish request message
        self.publish(topic, msg,
                     content_type=content_type,
                     reply_to=response_topic if cbf is not None else None,
                     correlation_id=corr_id,
                     headers=headers)

    def call_sync(self, topic, msg=None, key="default",
                  content_type="application/json",
                  correlation_id=None,
                  headers={},
                  response_topic_postfix="",
                  timeout=20):  # a sync. request has a timeout
        """
        Client method to sync. call an endpoint registered and bound to the given topic by any
        other component connected to the broker. The method waits for a response and returns it
        as a tuple containing message properties and content.

        :param topic: topic for communication (callee has to be described to it)
        :param msg: actual message
        :param key: optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param content_type: type of message
        :param correlation_id: allow to set individual correlation ids
        :param headers: header dict
        :param response_topic_postfix: postfix of response topic
        :param timeout: time in s to wait for a response
        :return: message tuple: (ch, method, props, body)
        """
        # we use this lock to wait for the response
        lock = threading.Event()
        result = None

        def result_cbf(ch, method, props, body):
            """
            define a local callback method which receives the response
            """
            nonlocal result
            result = (ch, method, props, body)
            # release lock
            lock.set()

        # do a normal async call
        self.call_async(result_cbf, topic=topic, msg=msg, key=key,
                        content_type=content_type,
                        correlation_id=correlation_id,
                        headers=headers,
                        response_topic_postfix=response_topic_postfix)
        # block until we get our result
        lock.clear()
        lock.wait(timeout)
        # return received result
        return result


    def register_async_endpoint(self, cbf, topic, key="default", is_notification=False):
        """
        Executed by callees that want to expose the functionality implemented in cbf
        to callers that are connected to the broker.
        :param cbf: function to be called when requests with the given topic and key are received
        :param topic: topic for requests and responses
        :param key:  optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param is_notification: define endpoint as notification so that it will not send a response
        :return: None
        """
        if topic not in self._async_calls_request_topics:
            self._async_calls_request_topics.append(topic)
            bc = self.subscribe(self._on_call_async_request_received, topic)
            # we have to match this subscription to our callback method.
            # we use the consumer tag returned by self.subscribe for this.
            # (using topics instead would break wildcard symbol support)
            self._async_calls_endpoints[str(bc)] = AsyncEndpoint(
                cbf, bc, topic, key, is_notification)
        else:
            raise Exception("Already subscribed to this topic")

    def notify(self, topic, msg=None, key="default",
               content_type="application/json",
               correlation_id=None,
               headers={}):
        """
        Wrapper for the call_async method that does not have a callback function since
        it sends notifications instead of requests.
        :param topic: topic for communication (callee has to be described to it)
        :param key: optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param msg: actual message
        :param content_type: type of message
        :param correlation_id: allow to set individual correlation ids
        :param headers: header dict
        :return: None
        """
        self.call_async(None, topic, msg, key=key,
                        content_type=content_type, correlation_id=correlation_id, headers=headers)

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
        LOG.debug("RECEIVED from %r on %r: %r" % (
            properties.app_id, method.routing_key, str(msg)))


class AsyncEndpoint(object):
    """
    Class that represents a async. messaging endpoint.
    """

    def __init__(self, cbf, bc, topic, key, is_notification=False):
        self.cbf = cbf
        self.bc = bc  # basic consumer (created by subscribe method)
        self.topic = topic
        self.key = key
        self.is_notification = is_notification

