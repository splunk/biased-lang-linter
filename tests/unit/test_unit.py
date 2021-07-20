import json
import os
import sys
import pytest
import constants
from unittest.mock import patch
from utils import process_and_return_exclusions, is_json, add_lines, rgignore_cleanup
from utils import get_batch_info, truncate_line, get_source_type, open_csv, get_colors
from utils import write_file, grab_repo_name, get_hec_info, TimeFunction, BiasedLanguageLogger
from utils import get_line_count
from run_json import main, rg_search, build_args_dict, process_word_occurrences, process_biased_word_line
from tools.event2splunk import Event2Splunk

c = get_colors()
mock_repo_path = './tests/mock_repo'
mock_repo_path_no_exclusions = './tests/mock_repo_no_exclusions'


@pytest.fixture(scope="module")
def batch_info():
    return get_batch_info()


@pytest.fixture(scope="module")
def excluded_arr():
    excluded = []
    filename = f'{mock_repo_path}/{constants.EXCLUDE_FILE}'
    if os.path.exists(filename):
        f = open(filename, 'r')
        rgignore = f.read().split('\n')
        for path in rgignore:
            if path != '':
                excluded.append(path.strip())
        f.close()
    return excluded


def test_get_batch_info(batch_info):
    assert len(batch_info) == 2
    assert 'time' in batch_info
    assert 'uuid' in batch_info


def test_truncate_line():
    line = 'sssanitize","sanitizeFn"],ke={animation:"boolean",template:"string",titlbs-tooltip",Ne=new RegExp("(^|\\s)"+Ae+"\\S+","g"),Oe=["sanitize","whitelist","sanitizeFn"],ke={animation:"boolean",template:"string",title:"(sbs-tooltip",Ne=new RegExp("(^|\\s)"+Ae+"\\S+","g"),Oe=["sanitize","sanitizeFn"],ke={animation:"boolean",template:"string",title:"(s'
    biased_word = 'whitelist'
    max_line_len = constants.MAX_LINE_LEN

    truncated = truncate_line(line, biased_word, max_line_len)
    assert len(truncated) <= max_line_len
    assert biased_word in truncated

    # Test max lines case
    max_line = line.join([line[:len(line)]] * 6)
    max_truncated = truncate_line(max_line, biased_word, max_line_len)
    assert "Max length of lines reached" in max_truncated


def test_get_source_type():
    url = 'https://cd.splunkdev.com/engprod/biased-lang'
    source_type = get_source_type(url)
    assert source_type == 'cd.splunkdev.com'
    source_type = get_source_type(None)
    assert 'local-' in source_type


def test_open_csv():
    data = open_csv('word_list.csv')
    assert len(data) == 4
    for w in data:
        assert len(w) == 1


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
    path = 'builds/engprod/biased-lang'
    repo_name = grab_repo_name(path)
    assert repo_name == 'engprod/biased-lang'
    alt_path = '/biased-lang'
    alt_repo_name = grab_repo_name(alt_path)
    assert alt_repo_name == '/biased-lang'


def test_rg_search():
    count = 0
    rg_results = rg_search('whitelist', mock_repo_path)
    assert len(rg_results) == 11
    for r in rg_results:
        r = json.loads(r)
        if r['type'] == 'match':
            count += 1
    assert count == 4


def test_build_args_dict():
    extra_slash_path = mock_repo_path + '/'
    args = build_args_dict(
        [f'--path={extra_slash_path}', '--url=https://cd.splunkdev.com/engprod/biased-lang', '--mode=check', '--err_file=fake_file'])
    assert args['path'] == mock_repo_path
    assert args['mode'] == 'check'
    assert args['err_file'] == constants.ERR_FILE
    assert len(args) == 11


def test_process_word_occurrences(batch_info):
    biased_word = 'whitelist'
    rg_results = rg_search(biased_word, mock_repo_path)
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


def test_process_biased_word_line(batch_info):
    line = ['blacklist', 'blocklist']
    logger = BiasedLanguageLogger(name='test_logger', filename=None)
    code_quality_report, splunk_events = [], []
    terms_found = False
    args = {
        'path': mock_repo_path,
        'is_verbose': False,
        'splunk_flag': False,
        'mode': 'check'
    }
    occurrences = {'biased_words': [],
                   'mode': args['mode'], 'verbose': args['is_verbose']}
    terms_found, occurrences = process_biased_word_line(
        line, occurrences, code_quality_report, splunk_events, args, batch_info, terms_found, logger
    )
    assert terms_found == True
    assert 'blacklist' in occurrences['biased_words']


def test_exclusions():
    biased_word = 'master'
    process_and_return_exclusions(
        mock_repo_path, constants.EXCLUDE_FILE, constants.RGIGNORE_FILE)
    rg_results = rg_search(biased_word, mock_repo_path)
    assert len(rg_results) == 10
    count = 0
    for r in rg_results:
        r = json.loads(r)
        if r['type'] == 'match':
            count += 1
    assert count == 3


def test_exclusions_if_no_exclude_file():
    excluded = process_and_return_exclusions(
        mock_repo_path_no_exclusions, constants.EXCLUDE_FILE, constants.RGIGNORE_FILE)
    rgignore_filepath = f'{mock_repo_path_no_exclusions}/{constants.RGIGNORE_FILE}'
    assert os.path.exists(rgignore_filepath) == 1
    assert excluded == ['.git', 'node_modules', '__pycache__']
    rgignore_cleanup(mock_repo_path_no_exclusions, constants.RGIGNORE_FILE)


def test_get_splunk_hec_info():
    with pytest.raises(Exception) as no_hec:
        get_hec_info(None, None)
    assert "Missing Splunk HEC token" in str(no_hec.value)


def test_event2splunk(mocker):
    logger = BiasedLanguageLogger(
        name='UnitTesting', filename='UnitTesting.log')
    hec = get_hec_info('valid-token', 'https://fakeurl.com:1234')
    event2splunk = Event2Splunk(hec, logger)
    mocker.patch('tools.event2splunk.Event2Splunk._send_batch')
    event2splunk.post_event(payload={}, source='testing', sourcetype='testing')
    event2splunk._send_batch.assert_called()


def test_is_json():
    valid_json = '{"type":"begin","data":{"path":{"text":"./tests/mock_repo/nested_dir_1/more_biased_words.txt"}}}'
    invalid_json = '{["Error": "True"], "{"type":"begin","data":{"path":{"text":"./tests/mock_repo/nested_dir_1/more_biased_words.txt"}}}}'
    assert is_json(valid_json) == True
    assert is_json(invalid_json) == False


def test_add_lines():
    line_count = add_lines(mock_repo_path, [])
    assert line_count == 22


def test_get_line_count_with_exclusions():
    excluded = [
        'mock_repo/nested_dir_1/nested_dir_2/excluded_dir/excluded_biased_words_file.txt']
    line_count = get_line_count(mock_repo_path, excluded)
    assert line_count == 18


def test_timefunction():
    test_time = TimeFunction()
    start_time = test_time.start()
    start_time_duplicate = test_time.start()
    assert type(start_time) == float
    assert start_time_duplicate == None
    stop_time = test_time.stop()
    assert type(stop_time) == float


@patch('tools.event2splunk.Event2Splunk.post_event')
@patch('tools.event2splunk.Event2Splunk.close')
def test_main(mock_post_event, mock_close_event):
    args = {
        'path': mock_repo_path,
        'url': 'https://cd.splunkdev.com/engprod/biased-lang',
        'mode': 'check',
        'is_verbose': False,
        'splunk_flag': True,
        'enable_logs': False,
        'err_file': constants.ERR_FILE,
        'h_endpoint': 'valid-endpoint:1234',
        'splunk_token': 'valid-token',
        'pz_endpoint': 'valid-endpoint:1234',
        'pzero_token': 'valid-token',
        'github_repo': None
    }
    logger = BiasedLanguageLogger(name='test_logger', filename=None)
    main(args, logger)
    assert mock_post_event.called
    assert mock_close_event.called
