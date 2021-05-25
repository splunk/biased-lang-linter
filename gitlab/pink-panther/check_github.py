import requests
import sys
import json
import time

args=sys.argv
token=f'Bearer {args[1]}'
headers={'authorization': token}

# Trigger workflow
sys.stdout.write('Triggering GitHub Workflow...\n')
r = requests.post('https://api.github.com/repos/splunk/test-pink-panther/actions/workflows/main.yml/dispatches', headers=headers, data=json.dumps({"ref": "main"}))

def get_total_runs():
  return requests.get('https://api.github.com/repos/splunk/test-pink-panther/actions/workflows/8382216/runs?status=completed', headers=headers).json()

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
