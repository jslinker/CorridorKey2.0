import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser()
p.add_argument('--source',required=True,type=Path)
p.add_argument('--runs',required=True,type=Path)
p.add_argument('--inputs',required=True,type=Path)
p.add_argument('--fixtures',required=True,type=Path)
p.add_argument('--ffmpeg',default='ffmpeg')
p.add_argument('--groups',nargs='+',default=['smoke'])
p.add_argument('--names',nargs='*')
a=p.parse_args()
root=Path(__file__).resolve().parent
mapping={'${SOURCE}':str(a.source.resolve()),'${FIXTURES}':str(a.fixtures.resolve()),'${INPUTS}':str(a.inputs.resolve())}
cases=json.loads((root/'suite.json').read_text())
for case in cases:
    if a.names:
        if case['name'] not in a.names: continue
    elif case['group'] not in a.groups: continue
    result=a.runs/case['name']/'result.json'
    if result.exists():
        print('EXISTING',case['name'],flush=True)
        continue
    args=case['args']
    for token, value in mapping.items(): args=[v.replace(token,value) for v in args]
    cmd=[sys.executable,str(root/'run_case.py'),'--source',str(a.source.resolve()),'--runs',str(a.runs.resolve()),'--name',case['name'],'--ffmpeg',a.ffmpeg,'--',*args]
    process=subprocess.run(cmd)
    if process.returncode != case['expected_returncode']:
        print('UNEXPECTED RESULT',case['name'],process.returncode,flush=True)
        sys.exit(1)
