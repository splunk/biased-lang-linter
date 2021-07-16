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

import requests
import sys
import json
import time

args=sys.argv
token=f'Bearer {args[1]}'
headers={'authorization': token}

# Trigger workflow
sys.stdout.write('Triggering GitHub Workflow...\n')
r = requests.post('https://api.github.com/repos/splunk/test-biased-lang/actions/workflows/main.yml/dispatches', headers=headers, data=json.dumps({"ref": "main"}))

def get_total_runs():
  # return requests.get('https://api.github.com/repos/splunk/test-biased-lang/actions/workflows/8382216/runs?status=completed', headers=headers).json()
  return requests.get('https://api.github.com/repos/splunk/test-biased-lang/actions/workflows/main.yml/runs?status=completed', headers=headers).json()

if r.status_code >= 400:
  print(f'Failed to trigger GitHub Workflow. Status Code: {r.status_code}')
  exit(1)

total_runs=get_total_runs()['total_count']

expected_total_runs=total_runs+1

# 1 min timeout
timeout=time.time() + 60
sys.stdout.write('Getting total runs...\n')
while total_runs < expected_total_runs and time.time() < timeout:
  r=get_total_runs()
  total_runs=r['total_count']
  workflow_runs=r['workflow_runs'][0]

if total_runs < expected_total_runs:
  print('Timeout exceeded, couldnt get most recent run')
  exit(1)

if workflow_runs['conclusion'] != 'success':
  print('GitHub Workflow Conclusion: ' + workflow_runs['conclusion'])
  exit(1)

print('GitHub Workflow Successful')
exit(0)
