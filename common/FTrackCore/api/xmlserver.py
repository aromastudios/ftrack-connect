from __future__ import with_statement
import os,sys
if sys.version_info[0] == 2 and sys.version_info[1] == 6:
    from xmlrpc27 import xmlrpclib
    from xmlrpc27 import urllib2
else:
    import xmlrpclib
    import urllib2

from socket import error as socket_error

from ftrackerror import FTrackError, PermissionDeniedError

import time
import httplib
import getpass
from version_data import *
import datetime
import threading

from . import cache

# Increase the max integer limit for xmlrpc to match the 64-bit limit so that
# large numbers can be exchanged over xmlrpc. Note that this does violate the
# spec, but works as is guaranteed both the server and client support 64bit.
# Hardcoded value is used instead of system max since windows always reports
# 32-bit value. This is another good reason to get away from xmlrpc though.
xmlrpclib.MAXINT = 9223372036854775807

def getOS():
    import sys

    platform = "unix"

    if (sys.platform in ["win32","cygwin","win64"]):
        platform = "windows"
    elif (sys.platform in ["linux","linux2","darwin"]):
        platform = "unix"

    return platform


_proxy_variables = (
    'FTRACK_PROXY',
    'https_proxy',
    'http_proxy'

)

http_proxy_url = None
if set(_proxy_variables).intersection(set([k for k,v in os.environ.items() if v])):
    # Check if there are proxy settings available, we check the legacy
    # environment variable FTRACK_PROXY first followed by https_proxy and
    # end with http_proxy.


    for proxy_variable in _proxy_variables:
        http_proxy_url = os.environ.get(
            proxy_variable, None
        )

        if http_proxy_url:
            break

    class addinfourl(urllib2.addinfourl):
        """
        Replacement addinfourl class compatible with python-2.7's xmlrpclib
    
        In python-2.7, xmlrpclib expects that the response object that it receives
        has a getheader method. httplib.HTTPResponse provides this but
        urllib2.addinfourl does not. Add the necessary functions here, ported to
        use the internal data structures of addinfourl.
        """
        def getheader(self, name, default=None):
            if self.headers is None:
                raise httplib.ResponseNotReady()
            return self.headers.getheader(name, default)
    
        def getheaders(self):
            if self.headers is None:
                raise httplib.ResponseNotReady()
            return self.headers.items()
    urllib2.addinfourl = addinfourl


    class Urllib2Transport(xmlrpclib.Transport):
        def __init__(self, opener=None, https=False, use_datetime=0):
            xmlrpclib.Transport.__init__(self, use_datetime)
            self.opener = opener or urllib2.build_opener()
            self.https = https
        
        def request(self, host, handler, request_body, verbose=0):
            proto = ('http', 'https')[bool(self.https)]
            req = urllib2.Request('%s://%s%s' % (proto, host, handler), request_body)
            req.add_header('User-agent', host)
            req.add_header('Content-type', 'text/xml')
            
            #Add custom headers
            req.add_header("Ftrack-bulk", os.environ.get('FTRACK_BULK','false'))
            req.add_header("Ftrack-Apikey", os.environ.get('FTRACK_APIKEY','nokeyfound'))
            req.add_header("Ftrack-User", getpass.getuser())
            req.add_header("Ftrack-Os", getOS())
            req.add_header("Ftrack-Version", ftrackVersion)
            
            self.verbose = verbose
            return self.parse_response(self.opener.open(req))
    
    
    class HTTPProxyTransport(Urllib2Transport):
        def __init__(self, proxies, use_datetime=0):
            opener = urllib2.build_opener(urllib2.ProxyHandler(proxies))
            Urllib2Transport.__init__(self, opener, use_datetime)



class SpecialTransport(xmlrpclib.Transport):
    def send_content(self, connection, request_body):
        #Add custom headers
        connection.putheader("Ftrack-bulk", os.environ.get('FTRACK_BULK','false'))
        connection.putheader("Ftrack-Apikey", os.environ.get('FTRACK_APIKEY','nokeyfound'))
        connection.putheader("Ftrack-User", getpass.getuser())
        connection.putheader("Ftrack-Os", getOS())
        connection.putheader("Ftrack-Version", ftrackVersion)
        
        xmlrpclib.Transport.send_content(self,connection, request_body)

class SpecialSafeTransport(xmlrpclib.SafeTransport):
    def send_content(self, connection, request_body):
        #Add custom headers
        connection.putheader("Ftrack-bulk", os.environ.get('FTRACK_BULK','false'))
        connection.putheader("Ftrack-Apikey", os.environ.get('FTRACK_APIKEY','nokeyfound'))
        connection.putheader("Ftrack-User", getpass.getuser())
        connection.putheader("Ftrack-Os", getOS())
        connection.putheader("Ftrack-Version", ftrackVersion)
        
        xmlrpclib.SafeTransport.send_content(self,connection, request_body)

class XMLServer:

    def __init__(self,url,verbose=False,allow_none=True):
        self.lock = threading.RLock()
        self.user = getpass.getuser()

        # Caching of get action.
        self._getCache = cache.MemoryCache()
        self._getCacheKeyMaker = cache.KeyMaker()
        self._getCacheEnabled = 0
        self._getCacheFunctionKey = 'ftrack.xmlserver.get'

        self.resetDebug()
      
        self.batchObjects = []
        self.isBatch = False
        self.tempId = 0
      
        p = None
        if http_proxy_url:
            p = HTTPProxyTransport({ 'http': http_proxy_url, 'https': http_proxy_url, })
            if url.startswith('https'):
                p.https = True
        else:
            if url.startswith('https'):
                p = SpecialSafeTransport()
            else:
                p = SpecialTransport()
        try:
            self.xmlServer = xmlrpclib.ServerProxy(url,verbose=verbose,allow_none=allow_none,transport=p)
        except IOError, e:
            raise FTrackError("Unable to connect on " + url)


    def getTotalTime(self):
        return self.time
    
    def getTotalRequests(self):
        return self.requests

    def getStatistics(self):
        '''Return current statistics.'''
        statistics = {
            'time': self.getTotalTime(),
            'requests': self.getTotalRequests(),
            'cachedRequests': self._cachedRequests
        }

        return statistics

    def resetStatistics(self):
        '''Reset statistics.'''
        self.resetDebug()

    def resetDebug(self):
        self.time = 0.0
        self.requests = 0
        self._cachedRequests = 0

    def _verifyResponse(self, response):
        '''Analyze the *response* and raise exceptions if appropriate.'''
        if '_exception' in response:
            status = None
            try:
                status = int(response['_status'][:3])
            except (KeyError, ValueError):
                pass

            if status in (401, 402, 403):
                raise PermissionDeniedError(response['detail'])

            raise FTrackError(response['detail'])

        if (response['status'] == 0):
            raise FTrackError("Server exited with status 0")
        if not 'data' in response:
            raise FTrackError("Returned object is not valid")
        return response['data']

    def handleServerErrors(self,error):

        code = error.errcode if hasattr(error,'errcode') else error.code
        
        if code == 302:
            raise FTrackError("Server responded with a redirection message (302) - make sure your server url is set correctly. This could be the result of your server using https and the SERVER_URL is set to only use http.")        
        elif code in [401,402,403]:
            message = error.headers.getheader('FTRACK_ERROR')
            if not message:
                message = error.errmsg
            raise PermissionDeniedError(
                u'Server responded with an error - {0}'.format(message)
            )

    def _convertArgToIds(self,arg):
        if not arg:
            return arg
        
        def toId(item):
            if hasattr(item, 'getId'):
                return item.getId()
            elif isinstance(item,datetime.date):
                return str(item)
            elif isinstance(item,datetime.datetime):
                return str(item)
            return item
        
        #list
        if isinstance(arg,list):
            return [self._convertArgToIds(item) for item in arg]
        
        #dict - need to recurse
        if isinstance(arg,dict):
            for k,v in arg.iteritems():
                arg[k] = self._convertArgToIds(v)         
            
            return arg    
        
        #object
        return toId(arg) 

    def action(self,_action,data):
        actionName = _action.lower()

        with self.lock:
            #convert args
            data = self._convertArgToIds(data)
            
            data = self._appendOS(data)
            
            function = getattr(self.xmlServer, _action)
            
            if self.isBatch and _action == 'create':
                
                tempObject = {
                    'tempid' : "ftracktempid_" + str(self.tempId) + "_",
                    'tempdata' : data
                }
                
                self.tempId += 1
                
                return tempObject
            
            data['ftrack_user'] = self.user
            
            try:
                now = time.time()

                #HACK - to avoid ssl error after 2 minutes of inactivity in maya on windows
                try:
                    if actionName == 'get' and self._getCacheEnabled:
                        # NOTE: Can't use memoise helper as the xmlserver
                        # action function is not compatible with keymaker.
                        key = self._getCacheKeyMaker.key(
                            self._getCacheFunctionKey, (data,), {}
                        )
                        try:
                            response = self._getCache.get(key)
                            self._cachedRequests += 1
                        except KeyError:
                            response = function(data)
                            self._getCache.set(key, response)
                    else:
                        response = function(data)

                except socket_error,e:
                    #on error 10053 or 10054 retry
                    if e.args[0] in [10053, 10054, 1]:
                        response = function(data)
                    else:
                        raise

                requestTime = time.time() - now
            except (xmlrpclib.ProtocolError,urllib2.HTTPError), e:
                self.handleServerErrors(e)
                raise #re-raise error
            except socket_error, e:
                if hasattr(self.xmlServer,'_ServerProxy__host'):
                    raise FTrackError("Unable to connect on " + self.xmlServer._ServerProxy__host)
                else:
                    raise FTrackError("Unable to connect to ftrack server")

            #log debug info
            self.requests += 1
            self.time += requestTime
            
            return self._verifyResponse(response)

    def getOS(self):
        import sys

        platform = "unix"

        if (sys.platform in ["win32","cygwin","win64"]):
            platform = "windows"
        elif (sys.platform in ["linux","linux2","darwin"]):
            platform = "unix"

        return platform


    def _appendOS(self,data):
        data['ftrack_os'] = self.getOS()
        return data
    
    
    
    def startBatch(self):
        self.isBatch = True
    
    def endBatch(self):
        self.isBatch = False
        
        batchData = []
        
        for o in self.batchObjects:
            batchData.append({
                'attributes' : o.unsavedAttributes,
                'data' : o.dict['tempdata'],
                'id' : o.dict['tempid']
            })

            
        result = self.action('batch',{'objects':batchData})
        
        for o in self.batchObjects:
            o.__init__(dict=result[o.dict['tempid']])
        
        self.batchObjects = []
        
    def addTempObject(self,item):
        self.batchObjects.append(item)
    
        #set id
        item.dict[item._idkey] = item.dict['tempid']
    
    def enableGetCache(self):
        '''Enable caching of get calls.'''
        self._getCacheEnabled += 1

    def disableGetCache(self):
        '''Disable caching of get calls.

        Also, remove any stored values for cached get calls.

        '''
        self._getCacheEnabled -= 1

        if self._getCacheEnabled < 0:
            raise Exception(
                'Unbalanced calls to enable/disable get cache detected.'
            )

        if self._getCacheEnabled == 0:
            # Remove any cached key values that were stored for the get action.
            # NOTE: If cache is used for anything other than get action this
            # will have to be updated to only removing appropriate keys.
            self.clearGetCache()

    def clearGetCache(self):
        '''Clear any data stored in get cache.'''
        self._getCache.clear()
