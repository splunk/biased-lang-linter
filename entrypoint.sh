#!/bin/sh
cd /pink-panther

exec ls
exec pwd

python3 run_json.py \
--mode=check \
--path=${GITHUB_WORKSPACE} \
--url=${GITHUB_REPOSITORY} \
--excluded_dirs_path=/pink-panther/excluded_dirs \
--excluded_files_path=/pink-panther/excluded_files \
--err_file=err_biased_lang.log \
--splunk_logs