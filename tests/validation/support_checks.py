"""Check public support commands and interactive CLI planning, without GPU inference."""
import argparse, json, os, shutil, subprocess, sys, hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.source=a.source.resolve();a.fixtures=a.fixtures.resolve();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
records=[]
def run(name,script,args=(),answers=None,expected=0,contains=None):
    cmd=[sys.executable,str(a.source/script),*map(str,args)]
    r=subprocess.run(cmd,input=answers,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=a.source,env=dict(os.environ,PYTHONUTF8='1'),timeout=90)
    (a.output/(name+'.log')).write_text(r.stdout,encoding='utf-8')
    ok=r.returncode==expected and (contains is None or contains in r.stdout)
    records.append(dict(name=name,command=cmd,stdin=answers,returncode=r.returncode,passed=ok,expected=expected,required_text=contains))
for script in ['infer.py','scripts/download_weights.py','scripts/smoke_test_runtime.py','scripts/convert_to_safetensors.py']:
    run(Path(script).stem+'-help',script,['--help'],contains='usage:')
run('runtime-checkpoint','scripts/smoke_test_runtime.py',contains='checkpoint ok:')
run('runtime-package-root','scripts/smoke_test_runtime.py',['--package_root',a.source],contains='checkpoint ok:')
run('interactive-missing','run_interactive.py',[a.output/'missing'],expected=1,contains='Input path does not exist')
run('interactive-single-plan','run_interactive.py',[a.fixtures/'sample.mp4'],answers='1\n1\n1\ny\n'+str(a.output/'single')+'\n1\n1\nn\n\n',contains='--num_frames 1 --start_mode begin')
seq=a.output/'batch'/'shot'/'Input';seq.mkdir(parents=True,exist_ok=True)
shutil.copy2(a.fixtures/'frames/frame_000.png',seq/'frame.png')
run('interactive-sequence-plan','run_interactive.py',[seq.parent],answers='1\n1\n2\n1\ny\n'+str(a.output/'sequence')+'\n1\n1\nn\n\n',contains='--num_frames 1 --start_mode begin')
run('interactive-batch-cancel','run_interactive.py',[seq.parent.parent],answers='1\n2\n1\nn\nn\n',contains='Batch execution canceled.')
# Synthetic legacy fixture exercises the converter; it is not a legacy model validation.
import torch
from safetensors.torch import load_file
legacy=a.output/'synthetic-legacy';legacy.mkdir(exist_ok=True)
state={'probe.weight':torch.arange(6,dtype=torch.float32).reshape(2,3)}
torch.save({'format':'corridorkey_v2_runtime_checkpoint','format_version':1,'metadata':{'public_model_name':'synthetic test','pre_recurrence':True,'training_private':'omit'},'model_config':{'synthetic':True},'state_dict':state},legacy/'corridorkey_v2.pt')
stats={k:torch.arange(3,dtype=torch.float32) for k in ['moge_mean','moge_std','rvm_mean','rvm_std','cradio_mean','cradio_std']}
torch.save(stats,legacy/'foundation_stats.pt')
run('convert-synthetic','scripts/convert_to_safetensors.py',['--weights_dir',legacy,'--output_dir',legacy/'converted'],contains='6 tensors')
assert torch.equal(load_file(legacy/'converted/corridorkey_v2.safetensors')['probe.weight'],state['probe.weight'])
assert all(torch.equal(load_file(legacy/'converted/foundation_stats.safetensors')[k],v) for k,v in stats.items())
(a.output/'results.json').write_text(json.dumps(records,indent=2))
print(json.dumps({'passed':sum(r['passed'] for r in records),'total':len(records),'failed':[r['name'] for r in records if not r['passed']]}))
sys.exit(0 if all(r['passed'] for r in records) else 1)
