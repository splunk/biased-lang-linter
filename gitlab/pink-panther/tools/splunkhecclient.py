import os
import sys
import ssl
import socket
import time
import json
from urllib import request, error, parse
from utils import TimeFunction

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

def get_lib_dir(base_dir):
    return os.path.abspath(os.path.join(base_dir, 'libs'))

sys.path.append(get_lib_dir(BASE_DIR))

class SplunkHECClient(object):
    def __init__(self, protocol, server, port, hec_key, logger):
        self._max_retry = 3
        self._retry_delay = 10
        self._timeout = 10
        self._protocol = protocol
        self._url = f"{protocol}://{server}:{port}/services/collector/event"
        self._headers = {'Authorization': hec_key}
        self._method = 'POST'
        self._logger = logger
        self._logger.debug(f'HEC URL: {self._url}')

    def post(self, data):
        post_timer = TimeFunction('SplunkHECPost', self._logger)
        post_timer.start()
        successful = False
        msg = None
        retry = 0
        while not successful and retry < self._max_retry:
            retry += 1
            successful, msg = self._post(data)
            if not successful:
                retry_delay = self._retry_delay * retry
                self._logger.warning(msg)
                self._logger.warning(f'Will retry { retry_delay }s later')
                time.sleep(self._retry_delay * retry)
        if not successful:
            self._logger.error(msg)
        post_timer.stop()
        return successful

    def _post(self, data):
        ctx = None
        if self._protocol == 'https':
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            requestObj = request.Request(url=self._url, data=data.encode(),
                                         headers=self._headers,
                                         method=self._method)
            request.urlopen(requestObj, timeout=self._timeout, context=ctx)
            return True, None
        except request.HTTPError as e:
            msg = (f"Failed to post Splunk Event, code: {e.code}" +
                   f", reason: {e.reason}")
            return False, msg
        except Exception as e:
            msg = f"Failed to post Splunk Event, error: {e}"
            return False, msg

class SplunkEventBuilder(object):
    def __init__(self):
        self._timestamp = time.time()
        self._source = ""
        self._index = ""
        self._source_type = ""
        self._defaults = {}
        self._payload = {}

        try:
            self._hostname = socket.gethostname()
        except:
            self._hostname = ""

    def set_index(self, index):
        self._index = index

    def set_source(self, source):
        self._source = source

    def set_sourcetype(self, source_type):
        self._source_type = source_type

    def set_timestamp(self, unixtime):
        self._timestamp = unixtime

    def build_event(self, payload):
        data = {
            "source": self._source,
            "index": self._index,
            "sourcetype": self._source_type,
            "host": self._hostname,
            "time": str(self._timestamp),
            "event": payload
        }
        return json.dumps(data)