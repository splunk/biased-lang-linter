# Copyright 2021 Splunk Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

import json
import time
from utils import BiasedLanguageLogger
from .splunkhecclient import (SplunkHECClient,
                              SplunkEventBuilder)


class Event2Splunk(object):
    def __init__(self, splunk_env, logger=None, dryrun=False):
        self._batch_size = 40000
        self._batch_events = []
        self._ingested_events = 0
        self._total_events = 0
        self._dryrun = dryrun
        self._logger = logger
        if self._dryrun:
            return

        # Configure Splunk HEC Client
        self._splunk_env = splunk_env
        self.splunk_client = SplunkHECClient(
            self._splunk_env['hec_protocol'],
            self._splunk_env['hec_host'],
            self._splunk_env['hec_port'],
            self._splunk_env['hec_key'],
            self._logger
        )

        # Configure default Event Builder
        self._builder = SplunkEventBuilder()
        if "hec_index" in self._splunk_env:
            self._builder.set_index(self._splunk_env["hec_index"])
        if "source" in self._splunk_env:
            self._builder.set_source(self._splunk_env["source"])
        if "source_type" in self._splunk_env:
            self._builder.set_sourcetype(self._splunk_env["source_type"])

        # Configure event map
        self._event_map = None
        if "event_map" in self._splunk_env:
            self._event_map = self._splunk_env["event_map"]

    @property
    def ingested_events(self):
        return self._ingested_events

    @property
    def total_events(self):
        return self._total_events

    def post_event(self, payload, timestamp=None, index=None,
                   source=None, sourcetype=None, filename=None):
        if self._dryrun:
            self._logger.debug(json.dumps(payload, sort_keys=True,
                                    indent=4, separators=(',', ': ')))
            return

        if timestamp:
            self._builder.set_timestamp(timestamp)
        else:
            self._builder.set_timestamp(time.time())

        if index:
            self._builder.set_index(index)
        if sourcetype:
            self._builder.set_sourcetype(sourcetype)
        if source:
            self._builder.set_source(source)

        self._total_events += 1
        self._batch_events.append(self._builder.build_event(payload))
        self._send_batch(filename)

    def _send_batch(self, filename, force=False):
        if ((not force and len(self._batch_events) < self._batch_size)
                or (force and len(self._batch_events) == 0)):
            return

        if self.splunk_client.post("".join(self._batch_events)):
            self._ingested_events += len(self._batch_events)
            self._logger.info(f'Sent {self._ingested_events} events to Splunk HEC')

        # Cleanup queued events. Doing this will lose events when sending a post
        # request failed.
        self._batch_events = []

    def close(self, filename=None):
        if self._dryrun:
            return
        self._send_batch(filename, force=True)
