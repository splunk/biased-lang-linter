import json
import os
import sys
import pytest
from utils import get_batch_info, truncate_line, get_source_type, open_csv, get_colors
from utils import exclude_pink_panther_dirs_files, exclude_other_dirs_files
from utils import write_file, grab_repo_name, get_splunk_hec_info, TimeFunction, BiasedLanguageLogger
from run_json import main, rg_search, build_args_dict, process_word_occurrences
from tools.event2splunk import Event2Splunk

c = get_colors()
mock_repo_path = './tests/mock_repo'


@pytest.fixture(scope="module")
def batch_info():
    return get_batch_info()

@pytest.fixture(scope="module")
def excluded_arr():
    return exclude_other_dirs_files(
        mock_repo_path, c, [], '.test_excluded_dirs', '.test_excluded_files')


def test_get_batch_info(batch_info):
    assert len(batch_info) == 2
    assert 'time' in batch_info
    assert 'uuid' in batch_info


def test_truncate_line():
    line = 'sssanitize","sanitizeFn"],ke={animation:"boolean",template:"string",titlbs-tooltip",Ne=new RegExp("(^|\\s)"+Ae+"\\S+","g"),Oe=["sanitize","whitelist","sanitizeFn"],ke={animation:"boolean",template:"string",title:"(sbs-tooltip",Ne=new RegExp("(^|\\s)"+Ae+"\\S+","g"),Oe=["sanitize","sanitizeFn"],ke={animation:"boolean",template:"string",title:"(s'
    biased_word = 'whitelist'
    max_line_len = 150

    truncated = truncate_line(line, biased_word, max_line_len)
    assert len(truncated) <= max_line_len
    assert biased_word in truncated


def test_get_source_type():
    url = 'https://cd.splunkdev.com/engprod/pink-panther'
    source_type = get_source_type(url)
    assert source_type == 'cd.splunkdev.com'
    source_type = get_source_type(None)
    assert 'local-' in source_type


def test_open_csv():
    data = open_csv('word_list.csv')
    assert len(data) == 4
    for w in data:
        assert len(w) == 2


def test_exclude_pink_panther_dirs_files():
    excluded_arr = exclude_pink_panther_dirs_files([])
    assert len(excluded_arr) == 9
    assert excluded_arr[0] == '__pycache__'
    assert excluded_arr[1] == '.git'
    assert excluded_arr[2] == 'pink-panther'
    assert excluded_arr[3] == 'node_modules'
    assert excluded_arr[4] == 'lib'
    assert excluded_arr[5] == 'check.sh'
    assert excluded_arr[6] == 'fix.sh'
    assert excluded_arr[7] == 'run.py'
    assert excluded_arr[8] == 'word_list.csv'


def test_exclude_other_dirs_files(excluded_arr):
    assert len(excluded_arr) == 2
    assert excluded_arr[0] == 'excluded_dir'
    assert excluded_arr[1] == 'excluded_biased_words_file.txt'


def test_write_file():
    path = mock_repo_path + 'test_file.txt'
    occurrences = {
        "description": "Biased term found: blacklist",
        "location": {
            "path": "nested_dir_1/more_biased_words.txt",
            "lines": {
                "begin": 1
            }
        },
        "fingerprint": "a196f42c3eedd403a3a79661c8eb6469"
    }
    write_file(path,  occurrences)
    assert os.path.exists(path) == True
    os.remove(path)


def test_grab_repo_name():
    path = 'builds/engprod/pink-panther'
    repo_name = grab_repo_name(path)
    assert repo_name == 'engprod/pink-panther'
    alt_path = '/pink-panther'
    alt_repo_name = grab_repo_name(alt_path)
    assert alt_repo_name == '/pink-panther'


def test_rg_search(excluded_arr):
    count = 0
    rg_results = rg_search('whitelist', mock_repo_path, excluded_arr)
    assert len(rg_results) == 11
    for r in rg_results:
        r = json.loads(r)
        if r['type'] == 'match':
            count += 1
    assert count == 4


def test_build_args_dict():
    args = build_args_dict(
        [f'--path={mock_repo_path}', '--url=https://cd.splunkdev.com/engprod/pink-panther', '--mode=check'])
    assert args['path'] == mock_repo_path
    assert args['mode'] == 'check'
    assert len(args) == 11


def test_process_word_occurrences(batch_info, excluded_arr):
    biased_word = 'whitelist'
    rg_results = rg_search(biased_word, mock_repo_path, excluded_arr)
    json_results, word_report, events = process_word_occurrences(
        rg_results, batch_info, biased_word, False, mock_repo_path, True)
    assert json_results['num_matched_lines'] == 4
    assert json_results['num_matched_words'] == 5
    assert json_results['num_matched_files'] == 3
    assert len(json_results['files']) == 3
    assert len(word_report) == 4
    assert 'line_truncated' in events[0]
    assert 'description' in events[0]
    assert 'fingerprint' in events[0]
    assert 'location' in events[0]
    assert 'content' in events[0]
    assert 'line' in events[0]
    assert 'time' in events[0]
    assert 'uuid' in events[0]


def test_event2splunk(mocker):
    logger = BiasedLanguageLogger(
        name='UnitTesting', filename='UnitTesting.log', enable_logs=True)
    hec = get_splunk_hec_info('invalid-token')
    event2splunk = Event2Splunk(hec, logger)
    mocker.patch('tools.event2splunk.Event2Splunk._send_batch')
    event2splunk.post_event(payload={}, source='testing', sourcetype='testing')
    event2splunk._send_batch.assert_called()
