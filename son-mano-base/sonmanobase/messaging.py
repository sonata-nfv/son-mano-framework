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

from amqpstorm import UriConnection
import logging
import threading
import concurrent.futures as pool
import uuid
import time
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
    It uses the asynchronous adapter implementation of the amqpstorm library.
    """

    def __init__(self, app_id, **kwargs):
        """
        Initialize broker connection.
        :param app_id: string that identifies application

        """
        self.app_id = app_id
        # fetch configuration
        if "url" in kwargs:
            self.rabbitmq_url = kwargs['url']
        else:
            self.rabbitmq_url = os.environ.get("broker_host", RABBITMQ_URL_FALLBACK)
        self.rabbitmq_exchange = os.environ.get("broker_exchange", RABBITMQ_EXCHANGE_FALLBACK)
        self.rabbitmq_exchange_type = "topic"
        # create additional members
        self._connection = None
        # trigger connection setup (without blocking)
        self.setup_connection()

        # Threading workers
        self.thrd_pool = pool.ThreadPoolExecutor(max_workers=100)
        # Track the workers
        self.tasks = []

    def setup_connection(self):
        """
        Connect to rabbit mq using self.rabbitmq_url.
        """
        self._connection = UriConnection(self.rabbitmq_url)
        return self._connection

    def stop_connection(self):
        """
        Close the connection
        :return:
        """
        self._connection.close()

    def stop_threads(self):
        """
        Stop all the threads that are consuming messages
        """
        for task in self.tasks:
            task.cancel()

    def publish(self, topic, message, properties=None):
        """
        This method provides basic topic-based message publishing.

        :param topic: topic the message is published to
        :param message: the message (JSON/YAML/STRING)
        :param properties: custom properties for the message (as dict)
        :return:
        """
        # create a new channel
        with self._connection.channel() as channel:
            # declare the exchange to be used
            channel.exchange.declare(self.rabbitmq_exchange, exchange_type=self.rabbitmq_exchange_type)
            # update the default properties with custom ones from the properties argument
            if properties is None:
                properties = dict()
            default_properties = {
                "app_id": self.app_id,
                "content_type": "application/json",
                "correlation_id": None,
                "reply_to": None,
                "headers": dict()
            }
            default_properties.update(properties)
            # fix properties (amqpstorm does not like None values):
            for k, v in default_properties.items():
                default_properties[k] = "" if v is None else v
            if "headers" in default_properties:
                for k, v in default_properties["headers"].items():
                    default_properties["headers"][k] = "" if v is None else v
            # publish the message
            channel.basic.publish(body=message,
                                  routing_key=topic,
                                  exchange=self.rabbitmq_exchange,
                                  properties=default_properties)
            LOG.debug("PUBLISHED to %r: %r", topic, message)

    def subscribe(self, cbf, topic, subscription_queue=None):
        """
        Implements basic subscribe functionality.
        Starts a new thread for each subscription in which messages are consumed and the callback functions
        are called.

        :param cbf: callback function cbf(channel, method, properties, body)
        :param topic: topic to subscribe to
        :return:
        """

        def _wrapper_cbf(msg):
            """
            This internal cbf translates amqpstorm message arguments
            to pika's legacy cbf argument format.
            :param msg: amqp message
            :return:
            """
            # translate msg properties
            ch = msg.channel
            body = msg.body
            method = type('method', (object,), msg.method)
            # ensure that we have a header field
            if "headers" not in msg.properties:
                msg.properties["headers"] = dict()
            # make emtpy strings to None to be compatible
            for k, v in msg.properties.items():
                msg.properties[k] = None if v == "" else v
            properties = type('properties', (object,), msg.properties)
            # call cbf of subscription
            cbf(ch, method, properties, body)
            # ack the message to let broker know that message was delivered
            msg.ack()

        def connection_thread():
            """
            Each subscription consumes messages in its own thread.
            :return:
            """
            with self._connection.channel() as channel:
                # declare exchange for this channes
                channel.exchange.declare(exchange=self.rabbitmq_exchange, exchange_type=self.rabbitmq_exchange_type)
                # create queue for subscription
                q = channel.queue
                q.declare(subscription_queue)
                # bind queue to given topic
                q.bind(queue=subscription_queue, routing_key=topic, exchange=self.rabbitmq_exchange)
                # recommended qos setting
                channel.basic.qos(100)
                # setup consumer (use queue name as tag)
                channel.basic.consume(_wrapper_cbf, subscription_queue, consumer_tag=subscription_queue, no_ack=False)
                try:
                    # start consuming messages.
                    channel.start_consuming(to_tuple=False)
                except BaseException:
                    LOG.exception("Error in subscription thread:")
                    channel.close()

        # Attention: We crate an individual queue for each subscription to allow multiple subscriptions
        # to the same topic.
        if subscription_queue is None:
            queue_uuid = str(uuid.uuid4())
            subscription_queue = "%s.%s.%s" % ("q", topic, queue_uuid)
        # each subscriber is an own thread
        LOG.debug("start new thread to consume " + str(subscription_queue))
        task = self.thrd_pool.submit(connection_thread)
        task.add_done_callback(self.done_with_task)

        self.tasks.append(task)

        #Make sure that consuming has started, before method finishes.
        time.sleep(0.1)

        LOG.debug("SUBSCRIBED to %r", topic)
        return subscription_queue

    def done_with_task(self, f):
        """
        This function is called when a thread that consumes a queue is finished
        """
        # TODO: indicate that the thread is finished.


class ManoBrokerRequestResponseConnection(ManoBrokerConnection):
    """
    This class extends the ManoBrokerConnection class and adds functionality
    for a simple request/response messaging pattern on top of the topic-based
    publish/subscribe transport.

    The request/response implementation is strictly asynchronous on both sides:
    - the caller does not block and has to specify a callback function to
      receive a result (its even possible to receive multiple results because of
      the underlying publish/subscribe terminology).
    - the callee provides an RPC like endpoint specified by its topic and executes
      each request in an independent thread.
    """

    def __init__(self, app_id, **kwargs):
        self._async_calls_pending = {}
        self._async_calls_response_topics = {}
        # call superclass to setup the connection
        super(self.__class__, self).__init__(app_id, **kwargs)

    def _execute_async(self, async_finish_cbf, func, ch, method, props, body):
        """
        Run the given function
        cbf when it returns.
        :param async_finish_cbf: callback function
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

        run(async_finish_cbf, func, ch, method, props, body)
        LOG.debug("Async execution finished: %r." % str(func))

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

        # build header
        reply_headers = {
            "key": None,
            "type": "reply"
        }
        if props.headers is None:
            props.headers = dict()
        props.headers.update(reply_headers)

        # build properties
        properties = {
            "content_type": props.content_type,
            "reply_to": None,
            "correlation_id": props.correlation_id,
            "headers": props.headers
        }

        # return its result
        self.publish(props.reply_to, result, properties=properties)

    def _generate_cbf_call_async_rquest_received(self, cbf):
        """
        Generates a callback function. Only reacts if reply_to is set.
        CBF is executed asynchronously. Publishes CBF return value to reply to.
        :param cbf: function
        :return:
        """

        def _on_call_async_request_received(ch, method, props, body):
            # verify that the message is a request (reply_to != None)
            if props.reply_to is None:
                LOG.debug("Async request cbf: reply_to is None. Drop!")
                return
            LOG.debug("Async request on topic %r received." % method.routing_key)
            # call the user defined callback function (in a new thread to be async.
            self._execute_async(
                self._on_execute_async_finished,  # function called after execution of cbf
                cbf,  # function to be executed
                ch, method, props, body)

        return _on_call_async_request_received

    def _generate_cbf_notification_received(self, cbf):
        """
        Generates a callback function. Only reacts if reply_to is None.
        CBF is executed asynchronously.
        :param cbf: function
        :return:
        """

        def _on_notification_received(ch, method, props, body):
            # verify that the message is a notification (reply_to == None)
            if props.reply_to is not None:
                LOG.debug("Notification cbf: reply_to is not None. Drop!")
                return
            LOG.debug("Notification on topic %r received." % method.routing_key)
            # call the user defined callback function (in a new thread to be async.
            self._execute_async(
                None,
                cbf,  # function to be executed
                ch, method, props, body)

        return _on_notification_received

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
            #LOG.debug("Non-response message dropped at response endpoint.")
            return
        if props.correlation_id in self._async_calls_pending.keys():
            LOG.debug("Async response received. Matches to corr_id: %r" % props.correlation_id)
            # call callback (in new thread)
            self._execute_async(None,
                                self._async_calls_pending[props.correlation_id]['cbf'],
                                ch, method, props, body
                                )
            # if no other call_async is using this queue, remove the queue
            queue_tag = self._async_calls_pending[props.correlation_id]['queue']
            queue_empty = True
            for corr_id in self._async_calls_pending.keys():
                if corr_id != props.correlation_id:
                    if self._async_calls_pending[corr_id]['queue'] == queue_tag:
                        queue_empty = False
                        break
            if queue_empty:
                LOG.debug("Removing queue, as it is no longer used by any async call")
                ch.queue.delete()
                del self._async_calls_response_topics[self._async_calls_pending[props.correlation_id]['topic']]

            # remove from pending calls
            del self._async_calls_pending[props.correlation_id]

        else:
            LOG.debug("Received unmatched call response. Ignore it.")

    def call_async(self, cbf, topic, msg=None, key="default",
                   content_type="application/json",
                   correlation_id=None,
                   headers=None):
        """
        Sends a request message to a topic. If a "register_async_endpoint" is listening to this topic,
        it will execute the request and reply. This method sets up the subscriber for this reply and calls it
        when the reply is received.
        :param cbf: Function that is called when reply is received.
        :param topic: Topic for this call.
        :param msg: The message (STRING)
        :param key: additional header field
        :param content_type: default: application/json
        :param correlation_id: used to match requests to replies. If correlation_id is not given, a new one is generated.
        :param headers: Dictionary with additional header fields.
        :return:
        """
        if msg is None:
            msg = "{}"
        assert(isinstance(msg, str))
        if cbf is None:
            raise BaseException(
                "No callback function (cbf) given to call_async. Use notify if you want one-way communication.")
        # generate uuid to match requests and responses
        correlation_id = str(uuid.uuid4()) if correlation_id is None else correlation_id
        # initialize response subscription if a callback function was defined
        if topic not in self._async_calls_response_topics.keys():
            queue_uuid = str(uuid.uuid4())
            subscription_queue = "%s.%s.%s" % ("q", topic, queue_uuid)

            self.subscribe(self._on_call_async_response_received, topic, subscription_queue)
            # keep track of request
            self._async_calls_response_topics[topic] = subscription_queue
        else:
            #find the queue related to this topic
            subscription_queue = self._async_calls_response_topics[topic]

        self._async_calls_pending[correlation_id] = {'cbf':cbf, 'topic':topic, 'queue':subscription_queue}

        # build headers
        if headers is None:
            headers = dict()
        default_headers = {
            "key": key,
            "type": "request"
        }
        default_headers.update(headers)

        # build properties
        properties = {
            "content_type": content_type,
            "reply_to": topic,
            "correlation_id": correlation_id,
            "headers": default_headers
        }

        # publish request message
        LOG.debug("async request made on " + str(topic) + ", with corr_id " + str(correlation_id))
        self.publish(topic, msg, properties=properties)

    def register_async_endpoint(self, cbf, topic):
        """
        Executed by callees that want to expose the functionality implemented in cbf
        to callers that are connected to the broker.
        :param cbf: function to be called when requests with the given topic and key are received
        :param topic: topic for requests and responses
        :return: None
        """
        self.subscribe(self._generate_cbf_call_async_rquest_received(cbf), topic)
        LOG.debug("Registered async endpoint: topic: %r cbf: %r" % (topic, cbf))

    def notify(self, topic, msg=None, key="default",
               content_type="application/json",
               correlation_id=None,
               headers={},
               reply_to=None):
        """
        Sends a simple one-way notification that does not expect a reply.
        :param topic: topic for communication (callee has to be described to it)
        :param key: optional identifier for endpoints (enables more than 1 endpoint per topic)
        :param msg: actual message
        :param content_type: type of message
        :param correlation_id: allow to set individual correlation ids
        :param headers: header dict
        :param reply_to: (normally not used)
        :return: None
        """
        if msg is None:
            msg = "{}"
        assert (isinstance(msg, str))

        # build headers
        if headers is None:
            headers = dict()
        default_headers = {
            "key": key,
            "type": "request"
        }
        default_headers.update(headers)

        # build properties
        properties = {
            "content_type": content_type,
            "reply_to": reply_to,
            "correlation_id": correlation_id,
            "headers": default_headers
        }

        # publish request message
        self.publish(topic, msg, properties=properties)

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
        return self.subscribe(self._generate_cbf_notification_received(cbf), topic)

    def call_sync(self, topic, msg=None, key="default",
                  content_type="application/json",
                  correlation_id=None,
                  headers={},
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
                        headers=headers)
        # block until we get our result
        lock.clear()
        lock.wait(timeout)
        # return received result
        return result


def callback_print(self, ch, method, properties, msg):
        """
        Helper callback that prints the received message.
        """
        LOG.debug("RECEIVED from %r on %r: %r" % (
            properties.app_id, method.routing_key, str(msg)))
