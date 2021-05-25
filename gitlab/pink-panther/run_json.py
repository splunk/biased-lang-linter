'''
This version of the script is intended to produce JSON output to be used in CI work like Gitlab's
Code Climate output, in logging like HEC logging, or as input to another source.

Note: This Python script only functions in check mode.
Fix mode doesn't have output of where it replaced terms. Maybe it should,
in which case run_json.py should have fix mode as well and create JSON output?
For now, JSON output is produced only for check mode.
'''

import argparse
import constants
import hashlib
import json
import os
import re
import sys
import requests
from copy import copy
from ripgrepy import Ripgrepy as rg
from tools.event2splunk import Event2Splunk
from utils import truncate_line, get_source_type, send_codeclimate_batch
from utils import exclude_other_dirs_files, write_file, TimeFunction
from utils import open_csv, exclude_pink_panther_dirs_files
from utils import get_splunk_hec_info, get_colors, get_batch_info, grab_repo_name
from utils import BiasedLanguageLogger, get_line_count

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
    parser.add_argument('--excluded_dirs_path')
    parser.add_argument('--excluded_files_path')
    parser.add_argument('--splunk_logs', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--err_file')
    parser.add_argument('--splunk', action='store_true')
    parser.add_argument('--splunk_token')
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
            sys.stdout.write('%sWarning: no file "%s" for error logs found. Defaulting to "err_biased_lang.log". %s\n' % (
                c['red'], args.err_file, c['nc']))
            args.err_file = 'err_biased_lang.log'
        else:
            os.remove(args.err_file)

    return {
        'path': path,
        'url': args.url or os.environ.get('GITHUB_URL'),
        'mode': mode,
        'is_verbose': args.verbose,
        'splunk_flag': args.splunk,
        'log_splunk': args.splunk_logs,
        'ex_dirs_path': args.excluded_dirs_path,
        'ex_files_path': args.excluded_files_path,
        'err_file': args.err_file,
        'splunk_token': args.splunk_token,
        'github_repo': os.environ.get('GITHUB_REPO')
    }


def exclude_files_and_dir(path, ex_dirs_path, ex_files_path):
    # excluded_arr pre-populated with common directories to ignore
    excluded_arr = ['__pycache__', '.git', 'node_modules']
    excluded_arr = exclude_other_dirs_files(path, c, excluded_arr, ex_dirs_path, ex_files_path)
    return excluded_arr


'''
process_word_occurrences
input: raw results for a biased word from ripgrepy and
output: more readable JSON summary
'''


def process_word_occurrences(results, batch_info, biased_word, is_verbose, path, splunk_flag):
    json_result, report, events = {'biased_word': biased_word}, [], []
    files, lines = [], []

    while len(results) > 0:
        entry = json.loads(results.pop(0))
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


def rg_search(biased_word, path, excluded):
    # Prepare ripgrep and ignore excluded files/directories
    rg_options = rg(biased_word, path).ignore_case().hidden()
    for item in excluded:
        rg_options = rg_options.iglob('!%s' % item)

    return rg_options.json().run().as_string.splitlines()


def process_biased_word_line(line, occurrences, code_quality_report, splunk_events, args, excluded, batch_info, terms_found, logger):
    copy_occurrences = copy(occurrences)
    biased_word = line[0]
    json_results, word_report, events = {}, [], []
    terms_found = True if terms_found == True else None

    rg_results_timer = TimeFunction(f'rg_search for {biased_word}', logger)
    rg_results_timer.start()
    rg_results = rg_search(biased_word, args['path'], excluded)
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
        hec = get_splunk_hec_info(args['splunk_token'])
        event2splunk = Event2Splunk(hec, logger)
    repo_name = args['github_repo'] if args['github_repo'] else grab_repo_name(args['path'])
    source_type = get_source_type(args['url'])
    excluded = exclude_files_and_dir(
        args['path'], args['ex_dirs_path'], args['ex_files_path'])
    lines = open_csv('word_list.csv')

    if args['mode'] == 'check':
        occurrences = {'biased_words': [],
                       'mode': args['mode'], 'verbose': args['is_verbose']}
        code_quality_report, splunk_events = [], []
        terms_found = False

        # Generate JSON
        for line in lines:
            terms_found, occurrences = process_biased_word_line(
                line, occurrences, code_quality_report, splunk_events, args, excluded, batch_info, terms_found, logger)

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
            error_message = '%sError: %sPink Panther%s found biased words. Replacement(s) required. 🚨\nSee JSON output for details on what to replace. 🕵🏽‍♀️ %s\n' % (
                c['red'], c['lightmagenta'], c['red'], c['nc'])
            sys.stderr.write(error_message)
            if args['err_file']:
                with open(args['err_file'], 'w') as errfile:
                    errfile.write(error_message)
            if args['splunk_flag']:
                # Splunk the code quality report
                # If ran in GitHub, call endpoint to Splunk data
                if args['github_repo']:
                    # TODO: Call endpoint to trigger lambda function and firehose
                    print('Splunking splunk_events!')
                else:
                    send_codeclimate_batch(constants.CODECLIMATE_FILENAME, splunk_events,
                                           repo_name, source_type, event2splunk)

        else:
            sys.stdout.write('%sPink panther %sfound no biased words! 🎉%s\n' % (
                c['lightmagenta'], c['green'], c['nc']))

        if args['splunk_flag']:
            # Splunk the summarized JSON
            occurrences['content'] = constants.SUMMARY_FILENAME
            occurrences.update(batch_info)
            occurrences['total_lines'] = get_line_count(args['path'], excluded)
            occurrences['run_time'] = main_timer.stop()
            # If ran in GitHub, call endpoint to Splunk data
            if args['github_repo']:
                # TODO: Call endpoint to trigger lambda function and firehose
                # res = requests.post('https://8pnlr6tm71.execute-api.us-east-2.amazonaws.com/v2/', json.dumps(occurrences))
                # jsonResponse = res.json()
                # print('RESPONSE', jsonResponse)
                print('Splunking occurrences data from GitHub!')
            else:
                event2splunk.post_event(payload=occurrences,
                                        source=repo_name, sourcetype=source_type)
                event2splunk.close(filename=constants.SUMMARY_FILENAME)
        # For GitHub Actions to provide error annotations
        err_file=args['err_file']
        if os.path.exists(err_file) and args['github_repo']:
            print(f'{err_file} file found, exiting(1)')
            sys.exit(1)


if __name__ == '__main__':
    args = build_args_dict()
    logger = BiasedLanguageLogger(
        name='BiasedLanguageLogger', filename=constants.LOG_FILE, enable_logs=args['log_splunk'])
    main(args, logger)
