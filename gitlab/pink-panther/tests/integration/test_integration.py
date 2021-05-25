import json
import pytest


@pytest.fixture(scope="module")
def json_data():
    file = 'biased-language-summary.json'
    with open(file, mode='r') as json_file:
        return json.load(json_file)


def test_master(json_data):
    master_dict = json_data['master']
    answers = {'num_matched_lines': 3,
               'num_matched_words': 4,
               'num_matched_files': 3}
    loop_and_assert(master_dict, answers)


def test_slave(json_data):
    slave_dict = json_data['slave']
    answers = {'num_matched_lines': 3,
               'num_matched_words': 4,
               'num_matched_files': 3}
    loop_and_assert(slave_dict, answers)


def test_whitelist(json_data):
    whitelist_dict = json_data['whitelist']
    answers = {'num_matched_lines': 4,
               'num_matched_words': 5,
               'num_matched_files': 3}
    loop_and_assert(whitelist_dict, answers)


def test_blacklist(json_data):
    blacklist_dict = json_data['blacklist']
    answers = {'num_matched_lines': 4,
               'num_matched_words': 5,
               'num_matched_files': 3}
    loop_and_assert(blacklist_dict, answers)


def test_summary(json_data):
    assert json_data['total_lines_matched'] == 14
    assert json_data['total_words_matched'] == 18
    assert json_data['total_files_matched'] == 3


def loop_and_assert(data, answers):
    for key in data:
        if key == 'num_matched_lines':
            assert data[key] == answers[key]
        if key == 'num_matched_words':
            assert data[key] == answers[key]
        if key == 'num_matched_files':
            assert data[key] == answers[key]
