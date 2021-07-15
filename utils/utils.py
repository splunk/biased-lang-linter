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

from binaryornot.check import is_binary
from copy import copy
import configparser
import csv
from datetime import datetime
import json
import logging
import logging.config
import math
import os
import re
import socket
import time
import uuid
import urllib.parse

binaryornot_logger = logging.getLogger('binaryornot')
binaryornot_logger.setLevel('ERROR')
chardet_logger = logging.getLogger('chardet')
chardet_logger.setLevel('ERROR')

config = configparser.ConfigParser()
config.read('splunk_configs.ini')

def get_hannibal_hec_info(token):
    if not token:
        raise Exception('No Splunk HEC token provided for Hannibal')
    return {
        'hec_host': config['hannibal']['host'],
        'hec_port': config['hannibal']['port'],
        'hec_key': f'Splunk {token}',
        'hec_index': config['hannibal']['index'],
        'hec_protocol': config['hannibal']['protocol'],
    }


def get_pzero_hec_info(token):
    if not token:
        raise Exception('No Splunk HEC token provided for PZero')
    return {
        'hec_host': config['pzero']['host'],
        'hec_port': config['pzero']['port'],
        'hec_key': f'Splunk {token}',
        'hec_index': config['pzero']['index'],
        'hec_protocol': config['pzero']['protocol']
    }


def get_colors():
    return {
        'text': {
            'yellow': '\033[0;33m',
            'green': '\033[0;32m',
            'red': '\033[0;31m',
            'lightmagenta': '\033[0;95m',
            'orange': '\033[38;5;172m',
            'nc': '\033[0m'
        },
        'underline': {
            'cyan': '\033[4;36m',
            'lightmagenta': '\033[4;95m'
        }
    }


def get_colors_sh():
    return {
        'text': {
            'yellow': '\\033[0;33m',
            'green': '\\033[0;32m',
            'red': '\\033[0;31m',
            'lightmagenta': '\\033[0;95m',
            'orange': '\\033[38;5;172m',
            'nc': '\\033[0m'
        },
        'underline': {
            'cyan': '\\033[4;36m',
            'lightmagenta': '\\033[4;95m'
        }
    }


def get_batch_info():
    year = str(datetime.now().year)
    timezone_offset = time.strftime('%z', time.gmtime())
    start_time = str(time.time()) + '_' + year + '_' + timezone_offset
    batch_uuid = str(uuid.uuid4())

    return {
        'time': start_time,
        'uuid': batch_uuid,
    }


def truncate_line(line, biased_word, max_line_len=150):
    line_result = []
    max_line_len -= len('...')*2
    total_line_len = max_line_len - len(biased_word)
    for match in re.finditer(biased_word, line, re.IGNORECASE):
        padding = math.floor(total_line_len/2)

        # Adding padding before and after banned_word so total len = 150
        start = max(match.start() - padding, 0)
        end = min(match.end() + padding, len(line))

        line_result.append(f'...{line[start:end]}...')

        if (len(line_result) == 5):
            line_result.append('Max length of lines reached...')
            break

    return '\n'.join(line_result)


def get_source_type(url=None):
    return urllib.parse.urlparse(url).netloc or 'local-' + socket.gethostname()


def send_codeclimate_batch(codeclimate_filename, report, repo_name, source_type, event2splunk):
    for line in report:
        event2splunk.post_event(
            filename=codeclimate_filename, payload=line, source=repo_name, sourcetype=source_type)
    event2splunk.close(codeclimate_filename)


def open_csv(csv_name):
    with open(csv_name) as fp:
        reader = csv.reader(fp, delimiter=',', quotechar='"')
        return [row for row in reader]


def write_file(file, content):
    with open(file, 'w') as outfile:
        json.dump(content, outfile, indent=2)
        outfile.write('\n')


# Grabs the org + repo name if in CI environment- engprod/biased-lang
# If run locally, will grab the last two parts of the path- splunk/biased-lang
def grab_repo_name(path):
    subpath = path[:path.rindex('/')]
    if not subpath:
        return path
    project_name = subpath[subpath.rindex('/')+1:]
    repository = path[path.rindex('/'):]
    return project_name + repository


def copy_file_and_add_exclusions(src_file, dest_file, excluded):
    excluded_copy = copy(excluded)
    with open(src_file, 'r') as bl, open(dest_file, 'w') as rg:
        for line in bl:
            excluded_copy.append(line.strip())
        for path in excluded_copy:
            rg.write('\n' + path)
    return excluded_copy


# This func will copy contents from exclude_file arg into a new
# .rgignore file for ripgrep library to exclude from search.
# The excluded list is pre-populated with known dirs to exclude.
def process_and_return_exclusions(path, exclude_file, rgignore_file):
    excluded = ['.git', 'node_modules', '__pycache__']
    bl_exclude_filepath = f'{path}/{exclude_file}'
    rgignore_filepath = f'{path}/{rgignore_file}'
    if os.path.exists(bl_exclude_filepath):
        excluded = copy_file_and_add_exclusions(
            bl_exclude_filepath, rgignore_filepath, excluded)
    else:
        rg = open(rgignore_filepath, 'w')
        for path in excluded:
            rg.write(path + '\n')
        rg.close()
    return excluded


# Add up the line count, but first it will update the nested dir values
# in the excluded list to the path after the last '/'
# This can be problematic for files of the same name in different dirs
# so the line count here would be a rough estimate
def get_line_count(path, excluded):
    excluded_copy = copy(excluded)
    def last_path(a): return a.rsplit('/', 1)[1]
    for i in range(len(excluded_copy)):
        if '/' in excluded_copy[i]:
            excluded_copy[i] = last_path(excluded_copy[i])
    return add_lines(path, excluded_copy)


def add_lines(path, excluded):
    line_count = 0
    for name in os.listdir(path):
        if name in excluded:
            continue
        file = os.path.join(path, name)
        if os.path.isfile(file) and not is_binary(file):
            with open(file, 'rb') as f:
                source = f.readlines()
                line_count += len(source)
        elif os.path.isdir(file):
            line_count += add_lines(file, excluded)
    return line_count


def rgignore_cleanup(path, rgignore_file):
    rgignore_filepath = f'{path}/{rgignore_file}'
    if os.path.exists(rgignore_filepath):
        os.remove(rgignore_filepath)


def is_json(json_val):
    try:
        json.loads(json_val)
    except ValueError as e:
        print('Error parsing JSON: ', json_val)
        return False
    return True


class TimeFunction:
    def __init__(self, fn=None, logger=None):
        self._start_time = None
        self._function_name = fn
        self._logger = logger

    def start(self):
        if self._start_time is not None:
            return print(f'Timer "{self._function_name}"is running. Use .stop() to stop it')
        self._start_time = time.time()
        return self._start_time

    def stop(self):
        if self._start_time is None:
            return print(f'Timer "{self._function_name}" is not running. Use .start() to start it')
        stop_time_seconds = time.time()
        elapsed_time = stop_time_seconds - self._start_time
        start_datetime = time.strftime(
            '%m/%d/%Y, %H:%M:%S', time.localtime(self._start_time))
        stop_datetime = time.strftime(
            '%m/%d/%Y, %H:%M:%S', time.localtime(stop_time_seconds))
        if self._logger is not None:
            self._logger.info(
                f'"{self._function_name}" start time: {start_datetime}')
            self._logger.info(
                f'"{self._function_name}" stop time: {stop_datetime}')
            self._logger.info(
                f'"{self._function_name}" took {elapsed_time} seconds')
        self._start_time = None
        return round(elapsed_time, 2)


class BiasedLanguageLogger:
    def __init__(self, name='BiasedLanguageLogger', filename=None):
        self._name = name
        self._filename = filename
        self._logger = logging.getLogger(self._name)
        logging.basicConfig(filename=self._filename,
                            filemode='w', level=logging.DEBUG)

    def info(self, msg):
        self._logger.info(msg)

    def warning(self, msg):
        self._logger.warn(msg)

    def error(self, msg):
        self._logger.error(msg)

    def debug(self, msg):
        self._logger.debug(msg)
