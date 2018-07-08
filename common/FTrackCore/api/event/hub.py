# :coding: utf-8
# :copyright: Copyright (c) 2013 ftrack

import os
import collections
import urlparse
import threading
import Queue as queue
import logging
import time
import getpass
import uuid
import operator
import functools
import json
import socket

import requests
import requests.exceptions
import websocket

from ..ftrackerror import (
    EventHubConnectionError, EventHubPacketError, NotFoundError, NotUniqueError
)
from .. import _python_compatibility
from .base import Event as _Event
from .subscriber import Subscriber as _Subscriber
from .expression import Parser as _Parser


SocketIoSession = collections.namedtuple('SocketIoSession', [
    'id',
    'heartbeatTimeout',
    'supportedTransports',
])


ServerDetails = collections.namedtuple('ServerDetails', [
    'scheme',
    'hostname',
    'port',
])


class EventHub(object):
    '''Manage routing of events.'''

    def __init__(self, server=None):
        '''Initialise hub, connecting to ftrack *server*.'''
        super(EventHub, self).__init__()
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )
        self.id = uuid.uuid4().hex
        self._connection = None

        self._uniquePacketId = 0
        self._packetCallbacks = {}
        self._lock = threading.RLock()

        self._waitTimeout = 4

        self._subscribers = []
        self._replyCallbacks = {}
        self._intentionalDisconnect = False

        self._eventQueue = queue.Queue()
        self._eventNamespace = 'ftrack.event'
        self._expressionParser = _Parser()

        # Default values for auto reconnection timeout on unintentional
        # disconnection. Equates to 5 minutes.
        self._autoReconnectAttempts = 30
        self._autoReconnectDelay = 10

        # Mapping of Socket.IO codes to meaning.
        self._codeNameMapping = {
            '0': 'disconnect',
            '1': 'connect',
            '2': 'heartbeat',
            '3': 'message',
            '4': 'json',
            '5': 'event',
            '6': 'acknowledge',
            '7': 'error'
        }
        self._codeNameMapping.update(
            dict((name, code) for code, name in self._codeNameMapping.items())
        )

        # Parse server URL and store server details.
        if server is None:
            server = os.environ['FTRACK_SERVER']

        urlParseResult = urlparse.urlparse(server)
        self.server = ServerDetails(
            urlParseResult.scheme,
            urlParseResult.hostname,
            urlParseResult.port
        )

    def getServerUrl(self):
        '''Return URL to server.'''
        return '{0}://{1}'.format(self.server.scheme, self.getHostname())

    def getHostname(self):
        '''Return hostname with port.'''
        if self.server.port:
            return '{0}:{1}'.format(self.server.hostname, self.server.port)
        else:
            return self.server.hostname

    @property
    def secure(self):
        '''Return whether secure connection used.'''
        return self.server.scheme == 'https'

    def connect(self):
        '''Initialise connection to server.

        Raise :py:exc:`ftrack.EventHubConnectionError` if already connected or
        connection fails.

        '''
        if self.connected:
            raise EventHubConnectionError(
                'Already connected.'
            )

        # Reset flag tracking whether disconnection was intentional.
        self._intentionalDisconnect = False

        try:
            # Connect to socket.io server using websocket transport.
            session = self._getSocketIoSession()

            if 'websocket' not in session.supportedTransports:
                raise ValueError(
                    'Server does not support websocket sessions.'
                )

            scheme = 'wss' if self.secure else 'ws'
            url = '{0}://{1}/socket.io/1/websocket/{2}'.format(
                scheme, self.getHostname(), session.id
            )

            # timeout is set to 60 seconds to avoid the issue where the socket
            # ends up in a bad state where it is reported as connected but the
            # connection has been closed. The issue happens often when connected
            # to a secure socket and the computer goes to sleep.
            # More information on how the timeout works can be found here:
            # https://docs.python.org/2/library/socket.html#socket.socket.setblocking
            self._connection = websocket.create_connection(url, timeout=60)

        except Exception:
            self.logger.debug(
                'Error connecting to event server at {0}.'
                .format(self.getServerUrl()),
                exc_info=1
            )
            raise EventHubConnectionError(
                'Failed to connect to event server at {0}.'
                .format(self.getServerUrl())
            )

        # Start background processing thread.
        self._processorThread = _ProcessorThread(self)
        self._processorThread.start()

        # Subscribe to reply events if not already. Note: Only adding the
        # subscriber locally as the following block will notify server of all
        # existing subscribers, which would cause the server to report a
        # duplicate subscriber error if EventHub.subscribe was called here.
        try:
            self._addSubscriber(
                'topic=ftrack.meta.reply',
                self._handleReply,
                subscriber=dict(
                    id=self.id
                )
            )
        except NotUniqueError:
            pass

        # Now resubscribe any existing stored subscribers. This can happen when
        # reconnecting automatically for example.
        for subscriber in self._subscribers[:]:
            self._notifyServerAboutSubscriber(subscriber)

    @property
    def connected(self):
        '''Return if connected.'''
        return self._connection is not None and self._connection.connected

    def disconnect(self, unsubscribe=True):
        '''Disconnect from server.

        Raise :py:exc:`ftrack.EventHubConnectionError` if not currently
        connected.

        If *unsubscribe* is True then unsubscribe all current subscribers
        automatically before disconnecting.

        '''
        if not self.connected:
            raise EventHubConnectionError(
                'Not currently connected.'
            )

        else:
            # Set flag to indicate disconnection was intentional.
            self._intentionalDisconnect = True

            # # Unsubscribe all subscribers.
            if unsubscribe:
                for subscriber in self._subscribers[:]:
                    self.unsubscribe(subscriber.metadata['id'])

                # Wait briefly to allow unsubscribe messages to be sent.
                time.sleep(self._waitTimeout)

            # Shutdown background processing thread.
            self._processorThread.cancel()

            # Join to it if it is not current thread to help ensure a clean
            # shutdown.
            if threading.current_thread() != self._processorThread:
                self._processorThread.join(self._waitTimeout)

            # Now disconnect.
            self._connection.close()
            self._connection = None

    def reconnect(self, attempts=10, delay=5):
        '''Reconnect to server.

         Make *attempts* number of attempts with *delay* in seconds between each
         attempt.

        .. note::

            All current subscribers will be automatically resubscribed after
            successful reconnection.

        Raise :py:exc:`ftrack.EventHubConnectionError` if fail to reconnect.

        '''
        try:
            self.disconnect(unsubscribe=False)
        except EventHubConnectionError:
            pass

        for attempt in range(attempts):
            self.logger.debug(
                'Reconnect attempt {0} of {1}'.format(attempt, attempts)
            )

            # Silence logging temporarily to avoid lots of failed connection
            # related information.
            try:
                logging.disable(logging.CRITICAL)

                try:
                    self.connect()
                except EventHubConnectionError:
                    time.sleep(delay)
                else:
                    break

            finally:
                logging.disable(logging.NOTSET)

        if not self.connected:
            raise EventHubConnectionError(
                'Failed to reconnect to event server at {0} after {1} attempts.'
                .format(self.getServerUrl(), attempts)
            )

    def wait(self, duration=None):
        '''Wait for events and handle as they arrive.

        If *duration* is specified, then only process events until duration is
        reached. *duration* is in seconds though float values can be used for
        smaller values.

        '''
        started = time.time()

        while True:
            try:
                event = self._eventQueue.get(timeout=0.1)
            except queue.Empty:
                pass
            else:
                self._handle(event)

                # Additional special processing of events.
                if event['topic'] == 'ftrack.meta.disconnected':
                    break

            if duration is not None:
                if (time.time() - started) > duration:
                    break

    def getSubscriberByIdentifier(self, identifier):
        '''Return subscriber with matching *identifier*.

        Return None if no subscriber with *identifier* found.

        '''
        for subscriber in self._subscribers[:]:
            if subscriber.metadata.get('id') == identifier:
                return subscriber

        return None

    def subscribe(self, subscription, callback, subscriber=None, priority=100):
        '''Register *callback* for *subscription*.

        A *subscription* is a string that can specify in detail which events the
        callback should receive. The filtering is applied against each event
        object. Nested references are supported using '.' separators.
        For example, 'topic=foo and data.eventType=Shot' would match the
        following event::

            <Event {'topic': 'foo', 'data': {'eventType': 'Shot'}}>

        The *callback* should accept an instance of :py:class:`Event` as its
        sole argument.

        Callbacks are called in order of *priority*. The lower the priority
        number the sooner it will be called, with 0 being the first. The
        default priority is 100. Note that priority only applies against other
        callbacks registered with this hub and not as a global priority.

        An earlier callback can prevent processing of subsequent callbacks by
        calling :py:meth:`Event.stop` on the passed `event` before
        returning.

        .. warning::

            Handlers block processing of other received events. For long
            running callbacks it is advisable to delegate the main work to
            another process or thread.

        A *callback* can be attached to *subscriber* information that details
        the subscriber context. A subscriber context will be generated
        automatically if not supplied.

        .. note::

            The subscription will be stored locally, but until the server
            receives notification of the subscription it is possible the
            callback will not be called.

        Return subscriber identifier.

        Raise :py:exc:`ftrack.NotUniqueError` if a subscriber with the same
        identifier already exists.

        '''
        # Add subscriber locally.
        subscriber = self._addSubscriber(
            subscription, callback, subscriber, priority
        )

        # Notify server now if possible.
        try:
            self._notifyServerAboutSubscriber(subscriber)
        except EventHubConnectionError:
            self.logger.debug(
                'Failed to notify server about new subscriber {0} '
                'as server not currently reachable.'
                .format(subscriber.metadata['id'])
            )

        return subscriber.metadata['id']

    def _addSubscriber(
        self, subscription, callback, subscriber=None, priority=100
    ):
        '''Add subscriber locally.

        See :py:meth:`subscribe` for argument descriptions.

        Return :py:class:`ftrack.Subscriber` instance.

        Raise :py:exc:`ftrack.NotUniqueError` if a subscriber with the same
        identifier already exists.

        '''
        if subscriber is None:
            subscriber = {}

        subscriber.setdefault('id', uuid.uuid4().hex)

        # Check subscriber not already subscribed.
        existingSubscriber = self.getSubscriberByIdentifier(subscriber['id'])
        if existingSubscriber is not None:
            raise NotUniqueError(
                'Subscriber with identifier {0} already exists.'
                .format(subscriber['id'])
            )

        subscriber = _Subscriber(
            subscription=subscription,
            callback=callback,
            metadata=subscriber,
            priority=priority
        )

        self._subscribers.append(subscriber)

        return subscriber

    def _notifyServerAboutSubscriber(self, subscriber):
        '''Notify server of new *subscriber*.'''
        subscribeEvent = _Event(
            topic='ftrack.meta.subscribe',
            data=dict(
                subscriber=subscriber.metadata,
                subscription=str(subscriber.subscription)
            )
        )

        self._publish(
            subscribeEvent,
            callback=functools.partial(self._onSubscribed, subscriber)
        )

    def _onSubscribed(self, subscriber, response):
        '''Handle acknowledgement of subscription.'''
        if response.get('success') is True:
            subscriber.active = True
        else:
            self.logger.warning(
                'Server failed to subscribe subscriber {0}: {1}'
                .format(subscriber.metadata['id'], response.get('message'))
            )

    def unsubscribe(self, subscriberIdentifier):
        '''Unsubscribe subscriber with *subscriberIdentifier*.

        .. note::

            If the server is not reachable then it won't be notified of the
            unsubscription. However, the subscriber will be removed locally
            regardless.

        '''
        subscriber = self.getSubscriberByIdentifier(subscriberIdentifier)

        if subscriber is None:
            raise NotFoundError(
                'Cannot unsubscribe missing subscriber with identifier {0}'
                .format(subscriberIdentifier)
            )

        subscriber.active = False
        self._subscribers.pop(self._subscribers.index(subscriber))

        # Notify the server if possible.
        unsubscribeEvent = _Event(
            topic='ftrack.meta.unsubscribe',
            data=dict(subscriber=subscriber.metadata)
        )

        try:
            self._publish(
                unsubscribeEvent,
                callback=functools.partial(self._onUnsubscribed, subscriber)
            )
        except EventHubConnectionError:
            self.logger.debug(
                'Failed to notify server to unsubscribe subscriber {0} as '
                'server not currently reachable.'
                .format(subscriber.metadata['id'])
            )

    def _onUnsubscribed(self, subscriber, response):
        '''Handle acknowledgement of unsubscribing *subscriber*.'''
        if response.get('success') is not True:
            self.logger.warning(
                'Server failed to unsubscribe subscriber {0}: {1}'
                .format(subscriber.metadata['id'], response.get('message'))
            )

    def _prepareEvent(self, event):
        '''Prepare *event* for sending.'''
        event['source'].setdefault('id', self.id)
        event['source'].setdefault('user', {
            'username': getpass.getuser()
        })

    def _prepareReplyEvent(self, event, sourceEvent, source=None):
        '''Prepare *event* as a reply to another *sourceEvent*.

        Modify *event*, setting appropriate values to target event correctly as
        a reply.

        '''
        event['target'] = 'id={0}'.format(sourceEvent['source']['id'])
        event['inReplyToEvent'] = sourceEvent['id']
        if source is not None:
            event['source'] = source

    def publish(self, event, synchronous=False, onReply=None):
        '''Publish *event*.

        If *synchronous* is specified as True then this method will wait and
        return a list of results from any called callbacks.

        .. note::

            Currently, if synchronous is True then only locally registered
            callbacks will be called and no event will be sent to the server.
            This may change in future.

        *onReply* is an optional callable to call with any reply event that is
        received in response to the published *event*.

        .. note::

            Will not be called when *synchronous* is True.

        '''
        return self._publish(event, synchronous=synchronous, onReply=onReply)

    def publishReply(self, sourceEvent, data, source=None):
        '''Publish a reply event to *sourceEvent* with supplied *data*.

        If *source* is specified it will be used for the source value of the
        sent event.

        '''
        replyEvent = _Event(
            'ftrack.meta.reply',
            data=data
        )
        self._prepareReplyEvent(replyEvent, sourceEvent, source=source)
        self.publish(replyEvent)

    def _publish(self, event, synchronous=False, callback=None, onReply=None):
        '''Publish *event*.

        If *synchronous* is specified as True then this method will wait and
        return a list of results from any called callbacks.

        .. note::

            Currently, if synchronous is True then only locally registered
            callbacks will be called and no event will be sent to the server.
            This may change in future.

        A *callback* can also be specified. This callback will be called once
        the server acknowledges receipt of the sent event. A default callback
        that checks for errors from the server will be used if not specified.

        *onReply* is an optional callable to call with any reply event that is
        received in response to the published *event*. Note that there is no
        guarantee that a reply will be sent.

        Raise :py:exc:`ftrack.EventHubConnectionError` if not currently
        connected.

        '''
        # Prepare event adding any relevant additional information.
        self._prepareEvent(event)

        if synchronous:
            # Bypass emitting event to server and instead call locally
            # registered handlers directly, collecting and returning results.
            return self._handle(event, synchronous=synchronous)

        if not self.connected:
            raise EventHubConnectionError(
                'Cannot publish event asynchronously as not connected to '
                'server.'
            )

        # Use standard callback if none specified.
        if callback is None:
            callback = functools.partial(self._onPublished, event)

        # Emit event to central server for asynchronous processing.
        try:
            # Register on reply callback if specified.
            if onReply is not None:
                # TODO: Add a timeout or some other approach to avoid growing
                # endlessly for events that never receive replies.
                self._replyCallbacks[event['id']] = onReply

            try:
                self._emitEventPacket(
                    self._eventNamespace, event, callback=callback
                )
            except EventHubConnectionError:
                # Connection may have dropped temporarily. Wait a few moments to
                # see if background thread reconnects automatically.
                time.sleep(15)

                self._emitEventPacket(
                    self._eventNamespace, event, callback=callback
                )
            except:
                raise

        except Exception:
            # Failure to send event should not cause caller to fail.
            self.logger.exception('Error sending event {0}.'.format(event))

    def _onPublished(self, event, response):
        '''Handle acknowledgement of published event.'''
        if response.get('success', False) is False:
            self.logger.error(
                'Server responded with error while publishing event {0}. '
                'Error was: {1}'
                .format(event, response.get('message'))
            )

    def _handle(self, event, synchronous=False):
        '''Handle *event*.

        If *synchronous* is True, do not send any automatic reply events.

        '''
        # Sort by priority, lower is higher.
        # TODO: Use a sorted list to avoid sorting each time in order to improve
        # performance.
        subscribers = sorted(
            self._subscribers, key=operator.attrgetter('priority')
        )

        results = []

        target = event.get('target', None)
        targetExpression = None
        if target:
            try:
                targetExpression = self._expressionParser.parse(target)
            except Exception:
                self.logger.exception(
                    'Cannot handle event as failed to parse event target '
                    'information: {0}'.format(event)
                )
                return

        for subscriber in subscribers:
            # Check if event is targeted to the subscriber.
            if (
                targetExpression is not None
                and not targetExpression.match(subscriber.metadata)
            ):
                continue

            # Check if subscriber interested in the event.
            if not subscriber.interestedIn(event):
                continue

            response = None

            try:
                response = subscriber.callback(event)
                results.append(response)
            except Exception:
                self.logger.exception(
                    'Error calling subscriber {0} for event {1}.'
                    .format(subscriber, event)
                )

            # Automatically publish a non None response as a reply when not in
            # synchronous mode.
            if not synchronous and response is not None:

                try:
                    self.publishReply(
                        event, data=response, source=subscriber.metadata
                    )

                except Exception:
                    self.logger.exception(
                        'Error publishing response {0} from subscriber {1} '
                        'for event {2}.'
                        .format(response, subscriber, event)
                    )

            # Check whether to continue processing topic event.
            if event.isStopped():
                self.logger.debug(
                    'Subscriber {0} stopped event {1}. Will not process '
                    'subsequent subscriber callbacks for this event.'
                    .format(subscriber, event)
                )
                break

        return results

    def _handleReply(self, event):
        '''Handle reply *event*, passing it to any registered callback.'''
        callback = self._replyCallbacks.pop(event['inReplyToEvent'], None)
        if callback is not None:
            callback(event)

    def subscription(self, subscription, callback, subscriber=None,
                     priority=100):
        '''Return context manager with *callback* subscribed to *subscription*.

        The subscribed callback will be automatically unsubscribed on exit
        of the context manager.

        '''
        return _SubscriptionContext(
            self, subscription, callback, subscriber=subscriber,
            priority=priority,
        )

    # Socket.IO interface.
    #

    def _getSocketIoSession(self):
        '''Connect to server and retrieve session information.'''
        socketIoUrl = (
            '{0}://{1}/socket.io/1/?api_user={2}&api_key={3}'
        ).format(
            self.server.scheme,
            self.getHostname(),
            getpass.getuser(),
            os.environ.get('FTRACK_APIKEY', 'nokeyfound')
        )
        try:
            response = requests.get(
                socketIoUrl,
                timeout=10,
                verify=False  # Allow self-signed SSL.
            )
        except requests.exceptions.Timeout as error:
            raise EventHubConnectionError(
                'Timed out connecting to server: {0}.'.format(error)
            )
        except requests.exceptions.SSLError as error:
            raise EventHubConnectionError(
                'Failed to negotiate SSL with server: {0}.'.format(error)
            )
        except requests.exceptions.ConnectionError as error:
            raise EventHubConnectionError(
                'Failed to connect to server: {0}.'.format(error)
            )
        else:
            status = response.status_code
            if status != 200:
                raise EventHubConnectionError(
                    'Received unexpected status code {0}.'.format(status)
                )

        # Parse result and return session information.
        parts = response.text.split(':')
        return SocketIoSession(
            parts[0],
            parts[1],
            parts[3].split(',')
        )

    def _addPacketCallback(self, callback):
        '''Store callback against a new unique packet ID.

        Return the unique packet ID.

        '''
        with self._lock:
            self._uniquePacketId += 1
            uniqueId = self._uniquePacketId

        self._packetCallbacks[uniqueId] = callback

        return '{0}+'.format(uniqueId)

    def _popPacketCallback(self, packetId):
        '''Pop and return callback for *packetId*.'''
        return self._packetCallbacks.pop(packetId)

    def _emitEventPacket(self, event, args, callback):
        '''Send event packet.'''
        data = json.dumps(
            dict(name=event, args=[args]),
            ensure_ascii=False
        )
        self._sendPacket(
            self._codeNameMapping['event'], data=data, callback=callback
        )

    def _acknowledgePacket(self, packetId, *args):
        '''Send acknowledgement of packet with *packetId*.'''
        packetId = packetId.rstrip('+')
        data = str(packetId)
        if args:
            data += '+{1}'.format(json.dumps(args, ensure_ascii=False))

        self._sendPacket(self._codeNameMapping['acknowledge'], data=data)

    def _sendPacket(self, code, data='', callback=None):
        '''Send packet via connection.'''
        path = ''
        packetID = self._addPacketCallback(callback) if callback else ''
        packetParts = (str(code), packetID, path, data)
        packet = ':'.join(packetParts)

        try:
            self._connection.send(packet)
            self.logger.debug(u'Sent packet: {0}'.format(packet))
        except socket.error as error:
            raise EventHubConnectionError(
                'Failed to send packet: {0}'.format(error)
            )

    def _receivePacket(self):
        '''Receive and return packet via connection.'''
        try:
            packet = self._connection.recv()
        except Exception as error:
            raise EventHubConnectionError(
                'Error receiving packet: {0}'.format(error)
            )

        try:
            parts = packet.split(':', 3)
        except AttributeError:
            raise EventHubPacketError(
                'Received invalid packet {0}'.format(packet)
            )

        code, packetID, path, data = None, None, None, None

        count = len(parts)
        if count == 4:
            code, packetID, path, data = parts
        elif count == 3:
            code, packetID, path = parts
        elif count == 1:
            code = parts[0]
        else:
            raise EventHubPacketError(
                'Received invalid packet {0}'.format(packet)
            )

        self.logger.debug('Received packet: {0}'.format(packet))
        return code, packetID, path, data

    def _handlePacket(self, code, packetId, path, data):
        '''Handle packet received from server.'''
        codeName = self._codeNameMapping[code]

        if codeName == 'connect':
            self.logger.debug('Connected to event server.')
            event = _Event('ftrack.meta.connected')
            self._eventQueue.put(event)

        elif codeName == 'disconnect':
            self.logger.debug('Disconnected from event server.')
            if not self._intentionalDisconnect:
                self.logger.debug(
                    'Disconnected unexpectedly. Attempting to reconnect.'
                )
                try:
                    self.reconnect(
                        attempts=self._autoReconnectAttempts,
                        delay=self._autoReconnectDelay
                    )
                except EventHubConnectionError:
                    self.logger.debug('Failed to reconnect automatically.')
                else:
                    self.logger.debug('Reconnected successfully.')

            if not self.connected:
                event = _Event('ftrack.meta.disconnected')
                self._eventQueue.put(event)

        elif codeName == 'heartbeat':
            # Reply with heartbeat.
            self._sendPacket(self._codeNameMapping['heartbeat'])

        elif codeName == 'message':
            self.logger.debug('Message received: {0}'.format(data))

        elif codeName == 'event':
            payload = json.loads(data)
            args = payload.get('args', [])

            if len(args) == 1:
                eventPayload = args[0]
                if isinstance(eventPayload, collections.Mapping):
                    # For Python <= 2.6.4 ensure that keyword arguments are
                    # strings.
                    _python_compatibility.ensure_compatible_keywords(
                        eventPayload
                    )

                    try:
                        event = _Event(**eventPayload)
                    except Exception:
                        self.logger.exception(
                            'Failed to convert payload into event: {0}'
                            .format(eventPayload)
                        )
                        return

                    self._eventQueue.put(event)

        elif codeName == 'acknowledge':
            parts = data.split('+', 1)
            acknowledgedPacketId = int(parts[0])
            args = []
            if len(parts) == 2:
                args = json.loads(parts[1])

            try:
                callback = self._popPacketCallback(acknowledgedPacketId)
            except KeyError:
                pass
            else:
                callback(*args)

        elif codeName == 'error':
            self.logger.error('Event server reported error: {0}.'.format(data))

        else:
            self.logger.debug('{0}: {1}'.format(codeName, data))


class _SubscriptionContext(object):
    '''Context manager for a one-off subscription.'''

    def __init__(self, hub, subscription, callback, subscriber, priority):
        '''Initialise context.'''
        self._hub = hub
        self._subscription = subscription
        self._callback = callback
        self._subscriber = subscriber
        self._priority = priority
        self._subscriberIdentifier = None

    def __enter__(self):
        '''Enter context subscribing callback to topic.'''
        self._subscriberIdentifier = self._hub.subscribe(
            self._subscription, self._callback, subscriber=self._subscriber,
            priority=self._priority
        )

    def __exit__(self, exception_type, exception_value, traceback):
        '''Exit context unsubscribing callback from topic.'''
        self._hub.unsubscribe(self._subscriberIdentifier)


class _ProcessorThread(threading.Thread):
    '''Process messages from server.'''

    daemon = True

    def __init__(self, client):
        '''Initialise thread with Socket.IO *client* instance.'''
        super(_ProcessorThread, self).__init__()
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )
        self.client = client
        self.done = threading.Event()

    def run(self):
        '''Perform work in thread.'''
        while not self.done.is_set():
            try:
                code, packetID, path, data = self.client._receivePacket()
                self.client._handlePacket(code, packetID, path, data)

            except EventHubPacketError as error:
                self.logger.debug(
                    'Ignoring invalid packet: {0}'.format(error)
                )
                continue

            except EventHubConnectionError:
                self.cancel()

                # Fake a disconnection event in order to trigger reconnection
                # when necessary.
                self.client._handlePacket('0', '', '', '')

                break

            except Exception as error:
                self.logger.debug(
                    'Aborting processor thread: {0}'.format(error)
                )
                self.cancel()
                break

    def cancel(self):
        '''Cancel work as soon as possible.'''
        self.done.set()
