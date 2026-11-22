"""File handoff for the Codex/ChatGPT agent. Does not call generation APIs."""
import argparse
import json
from pathlib import Path
import core as c

def main():
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='cmd',required=True)
 sub.add_parser('list')
 sync=sub.add_parser('sync');sync.add_argument('job_id');sync.add_argument('--render',action='store_true')
 args=parser.parse_args()
 # Don't call c.init(): a separately running app may have an active job.
 if args.cmd=='list':
  print(json.dumps([{'id':j['id'],'title':j['title'],'status':j['status']}for j in c.records('jobs')],indent=2));return
 import requests
 base='http://127.0.0.1:8765';headers={'X-Studio-Token':requests.get(base+'/api/session',timeout=5).json()['token']}
 response=requests.post(base+f'/api/jobs/{args.job_id}/sync',headers=headers,timeout=20);response.raise_for_status()
 if args.render:
  response=requests.post(base+f'/api/jobs/{args.job_id}/render',headers=headers,timeout=20);response.raise_for_status()
  import time
  for _ in range(180):
   job=next(j for j in requests.get(base+'/api/state',timeout=10).json()['jobs']if j['id']==args.job_id)
   if job['status']=='complete':print(str(c.local(job['video']['path'])));return
   if job['status']=='error':raise RuntimeError(job['error'])
   time.sleep(1)
  raise TimeoutError('Render still running; check app.')
 else: print(response.text)

if __name__=='__main__':main()
