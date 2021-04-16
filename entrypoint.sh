#!/bin/sh
echo ${GITHUB_WORKSPACE}
python3 /pink-panther/run_json.py --mode=check --path=${GITHUB_WORKSPACE}