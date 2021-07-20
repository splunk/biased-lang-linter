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

'''
This version of the script is intended to produce a JSON output and used in a CI environment
like GitHub Actions or GitLab CI.

 Note: This Python script only functions in check mode.
'''

import argparse
import constants
import hashlib
import json
import os
import re
import sys
import requests
from subprocess import getoutput
from copy import copy
from tools.event2splunk import Event2Splunk
from utils import truncate_line, get_source_type, send_codeclimate_batch
from utils import open_csv, write_file, TimeFunction, process_and_return_exclusions
from utils import get_hec_info, get_colors, get_batch_info, grab_repo_name
from utils import BiasedLanguageLogger, get_line_count, is_json

c = get_colors()['text']

# args parameter is only used for unit testing.


def build_args_dict(args=None):
    if not args:
        args = sys.argv[1:]
    # Parse params
    parser = argparse.ArgumentParser()
    parser.add_argument('--path')
    parser.add_argument('--url')
    parser.add_argument('--mode')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--err_file')
    parser.add_argument('--splunk', action='store_true')
    parser.add_argument('--h_endpoint')
    parser.add_argument('--splunk_token')
    parser.add_argument('--pz_endpoint')
    parser.add_argument('--pzero_token')
    parser.add_argument('--github_repo')
    args = parser.parse_args(args)
    # args.path will be passed through GitLab CI and manual runs
    # GITHUB_WORKSPACE is env var set in GitHub Actions
    path = args.path or os.environ.get('GITHUB_WORKSPACE')
    if not path:
        raise Exception('No path specified')
    if path.endswith('/'):
        path = path[:-1]
    if args.mode == 'check':
        mode = 'check'
    elif args.mode == 'fix':
        raise Exception(
            'Fix mode for JSON output is not yet supported. Please use --mode=check or use standard output with fix mode instead.')
    if not mode:
        raise Exception(
            'Invalid mode specified. Please specify --mode=check or --mode=fix.')
    if args.err_file:
        if not os.path.exists(args.err_file):
            sys.stdout.write('%sWarning: no file "%s" for error logs found. Defaulting to "%s". %s\n' % (
                c['red'], args.err_file, constants.ERR_FILE, c['nc']))
            args.err_file = constants.ERR_FILE
        else:
            os.remove(args.err_file)

    return {
        'path': path,
        'url': args.url or os.environ.get('GITHUB_URL'),
        'mode': mode,
        'is_verbose': args.verbose,
        'splunk_flag': args.splunk,
        'err_file': args.err_file,
        'h_endpoint': args.h_endpoint,
        'splunk_token': args.splunk_token,
        'pz_endpoint': args.pz_endpoint,
        'pzero_token': args.pzero_token,
        'github_repo': os.environ.get('GITHUB_REPO')
    }


'''
process_word_occurrences
input: raw results for a biased word from ripgrep and
output: more readable JSON summary
'''


def process_word_occurrences(results, batch_info, biased_word, is_verbose, path, splunk_flag):
    json_result, report, events = {'biased_word': biased_word}, [], []
    files, lines = [], []

    while len(results) > 0:
        json_value = results.pop(0)
        if not is_json(json_value):
            continue
        entry = json.loads(json_value)
        is_truncated = False
        if entry['type'] == 'summary':
            json_result['num_matched_lines'] = entry['data']['stats']['matched_lines']
            json_result['num_matched_words'] = entry['data']['stats']['matches']
        if entry['type'] == 'begin':
            # add to json_result
            files.append(entry['data']['path']['text'])
        if entry['type'] == 'match':
            # add to code quality report
            file_path = (entry['data']['path']['text'])[len(path)+1:]
            line_number = entry['data']['line_number']
            if 'bytes' in entry['data']['lines']:
                line = entry['data']['lines']['bytes']
            else:
                line = entry['data']['lines']['text']
            string = '%s-%s-%s-%s' % (biased_word,
                                      file_path, line_number, line)

            line = line.strip()

            if len(line) > constants.MAX_LINE_LEN:
                line = truncate_line(line, biased_word, constants.MAX_LINE_LEN)
                is_truncated = True

            location = {
                'path': file_path,
                'lines': {
                    'begin': line_number
                }
            }
            occurrence = {
                'description': f'Biased term found: {biased_word}',
                'location': location,
                'fingerprint': hashlib.md5(string.encode('utf-8')).hexdigest()
            }

            if is_verbose:
                # add to json_result
                lines.append({'line': line, 'location': location})
                # add to code quality report
                occurrence['line'] = line
            # code quality report
            report.append(occurrence)
            # code quality events - additional details if Splunking
            if splunk_flag:
                splunk_info = {
                    'line_truncated': is_truncated,
                    'line': line,
                    'content': constants.CODECLIMATE_FILENAME
                }
                splunk_info.update(batch_info)
                splunk_info.update(occurrence)
                events.append(splunk_info)

    json_result['num_matched_files'] = len(files)
    json_result['files'] = files
    if lines:
        json_result['lines'] = lines
    return json_result, report, events


def rg_search(biased_word, path):
    rg_command = f'rg --ignore-case --hidden --json {biased_word} {path}'
    output = getoutput(rg_command)
    return output.splitlines()


def process_biased_word_line(line, occurrences, code_quality_report, splunk_events, args, batch_info, terms_found, logger):
    copy_occurrences = copy(occurrences)
    biased_word = line[0]
    json_results, word_report, events = {}, [], []
    terms_found = terms_found or False

    rg_results_timer = TimeFunction(f'rg_search for {biased_word}', logger)
    rg_results_timer.start()
    rg_results = rg_search(biased_word, args['path'])
    rg_results_timer.stop()

    # the data summary entry will always be there, hence the > 1
    if len(rg_results) > 1:
        json_results, word_report, events = process_word_occurrences(
            rg_results, batch_info, biased_word, args['is_verbose'], args['path'], args['splunk_flag'])
        terms_found = True

    # add to code quality output and to Splunkable events list
    for report in word_report:
        code_quality_report.append(report)
    if args['splunk_flag']:
        for report in events:
            splunk_events.append(report)
    # add to stdout json
    copy_occurrences['biased_words'].append(biased_word)
    copy_occurrences[biased_word] = json_results

    return terms_found, copy_occurrences


def main(args, logger):
    main_timer = TimeFunction('main', logger)
    main_timer.start()
    batch_info = get_batch_info()
    if args['splunk_flag'] and not args['github_repo']:
        hec = get_hec_info(args['splunk_token'], args['h_endpoint'])
        pzero_hec = get_hec_info(args['pzero_token'], args['pz_endpoint'])
        event2splunk = Event2Splunk(hec, logger)
        pz_event2splunk = Event2Splunk(pzero_hec, logger)
    repo_name = args['github_repo'] or grab_repo_name(args['path'])
    source_type = get_source_type(args['url'])
    excluded = process_and_return_exclusions(
        args['path'], constants.EXCLUDE_FILE, constants.RGIGNORE_FILE)
    lines = open_csv('word_list.csv')

    if args['mode'] == 'check':
        occurrences = {'biased_words': [],
                       'mode': args['mode'], 'verbose': args['is_verbose']}
        code_quality_report, splunk_events = [], []
        terms_found = False

        # Generate JSON
        for line in lines:
            terms_found, occurrences = process_biased_word_line(
                line, occurrences, code_quality_report, splunk_events, args, batch_info, terms_found, logger)

        occurrences['terms_found'] = terms_found

        # every JSON in the codeclimate array is a line found
        occurrences['total_lines_matched'] = len(code_quality_report)
        # dedupes the files and accounts for all words for total count
        all_files_matched = []
        occurrences['total_words_matched'] = 0
        for word in occurrences['biased_words']:
            if word in occurrences and len(occurrences[word]) > 0:
                occurrences['total_words_matched'] += occurrences[word]['num_matched_words']
                all_files_matched = list(
                    set(all_files_matched) | set(occurrences[word]['files']))
        occurrences['total_files_matched'] = len(all_files_matched)

        # print output to console
        print(json.dumps(occurrences, indent=2))

        write_file(constants.SUMMARY_FILENAME, occurrences)
        write_file(constants.CODECLIMATE_FILENAME, code_quality_report)
        # final error check for check mode
        if terms_found:
            error_message = '%sError: %sBiased Lang Linter%s found biased words. Replacement(s) required. 🚨\nSee JSON output for details on what to replace. 🕵🏽‍♀️ %s\n' % (
                c['red'], c['lightmagenta'], c['red'], c['nc'])
            sys.stderr.write(error_message)
            if args['err_file']:
                with open(args['err_file'], 'w') as errfile:
                    errfile.write(error_message)
            if args['splunk_flag']:
                # Splunk the code quality report
                # If ran in GitHub, call endpoint to Splunk data
                if args['github_repo']:
                    # TODO: Call endpoint to post data to Splunk instance
                    print('Posting data to Splunk')
                else:
                    send_codeclimate_batch(constants.CODECLIMATE_FILENAME, splunk_events,
                                           repo_name, source_type, event2splunk)
                    send_codeclimate_batch(constants.CODECLIMATE_FILENAME, splunk_events,
                                           repo_name, source_type, pz_event2splunk)

        else:
            sys.stdout.write('%sBiased Lang Linter %sfound no biased words! 🎉%s\n' % (
                c['lightmagenta'], c['green'], c['nc']))

        if args['splunk_flag']:
            # Splunk the summarized JSON
            occurrences['content'] = constants.SUMMARY_FILENAME
            occurrences.update(batch_info)
            occurrences['total_lines'] = get_line_count(args['path'], excluded)
            occurrences['run_time'] = main_timer.stop()
            # If ran in GitHub, call endpoint to Splunk data
            if args['github_repo']:
                # TODO: Call endpoint to post data to Splunk instance
                print('Splunking occurrences data from GitHub!')
            else:
                event2splunk.post_event(payload=occurrences,
                                        source=repo_name, sourcetype=source_type)
                event2splunk.close(filename=constants.SUMMARY_FILENAME)
                pz_event2splunk.post_event(
                    payload=occurrences, source=repo_name, sourcetype=source_type)
                pz_event2splunk.close(filename=constants.SUMMARY_FILENAME)
        # For GitHub Actions to provide error annotations
        err_file = args['err_file']
        if os.path.exists(err_file) and args['github_repo']:
            print(f'{err_file} file found, exiting(1)')
            sys.exit(1)


if __name__ == '__main__':
    args = build_args_dict()
    logger = BiasedLanguageLogger(
        name='BiasedLanguageLogger', filename=constants.LOG_FILE)

    main(args, logger)
