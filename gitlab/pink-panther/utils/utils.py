from binaryornot.check import is_binary
from copy import copy
import csv
from datetime import datetime
import json
import logging
import math
import os
import re
import socket
import sys
import time
import uuid
import urllib.parse


def get_splunk_hec_info(token):
    if not token:
        raise Exception('No Splunk HEC token provided')
    return {
        'hec_host': 'hannibal.sv.splunk.com',
        'hec_port': 8088,
        'hec_key': f'Splunk {token}',
        'hec_index': 'bias_language',
        'hec_protocol': 'https',
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


def exclude_pink_panther_dirs_files(excluded_arr):
    results_arr = copy(excluded_arr)
    excluded_dirs_files = ['.excluded_dirs', '.excluded_files']
    for ex in excluded_dirs_files:
        with open(ex, 'r') as excluded:
            for line in excluded:
                results_arr.append(line.rstrip())
    return results_arr


def exclude_other_dirs_files(path, colors, excluded_arr=[], ex_dirs_path=None, ex_files_path=None):
    results_arr = copy(excluded_arr)
    dirs_target_path = '%s/%s' % (path, ex_dirs_path)
    files_target_path = '%s/%s' % (path, ex_files_path)
    
    for ex_path in [dirs_target_path, files_target_path]:
        if os.path.exists(ex_path):
            with open(ex_path, 'r') as excluded:
                for line in excluded:
                    results_arr.append(line.rstrip())
        else:
            sys.stdout.write('%sWarning: no file or directory "%s" specifying excluded directories found. Ignoring. %s\n' % (
                colors['red'], ex_path, colors['nc']))
    return results_arr


def write_file(file, occurrences):
    with open(file, 'w') as outfile:
        json.dump(occurrences, outfile, indent=2)
        outfile.write('\n')


# Grabs the org + repo name if in CI environment- engprod/pink-panther
# If run locally, will grab the last two parts of the path- splunk/pink-panther
def grab_repo_name(path):
    subpath = path[:path.rindex('/')]
    if not subpath:
        return path
    project_name = subpath[subpath.rindex('/')+1:]
    repository = path[path.rindex('/'):]
    return project_name + repository


def get_line_count(path, excluded):
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
            line_count += get_line_count(file, excluded)
    return line_count


class TimeFunction:
    def __init__(self, fn=None, logger=None):
        self._start_time = None
        self._function_name = fn
        self._logger = logger

    def start(self):
        if self._start_time is not None:
            return print(f'Timer "{self._function_name}"is running. Use .stop() to stop it')
        self._start_time = time.time()

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
    def __init__(self, name='BiasedLanguageLogger', filename=None, enable_logs=False):
        self._name = name
        self._filename = filename
        self._enable_logs = enable_logs
        self._logger = logging.getLogger(self._name)
        logging.basicConfig(filename=self._filename,
                            filemode='w', level=logging.DEBUG)

    def info(self, msg):
        if self._enable_logs:
            self._logger.info(msg)
    
    def warning(self, msg):
        if self._enable_logs:
            self._logger.warn(msg)
    
    def error(self, msg):
        if self._enable_logs:
            self._logger.error(msg)

    def debug(self, msg):
        if self._enable_logs:
            self._logger.debug(msg)
