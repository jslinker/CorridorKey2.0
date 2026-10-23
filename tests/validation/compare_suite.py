import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--left',type=Path,required=True);p.add_argument('--right',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
for l in sorted(a.left.iterdir()):
    r=a.right/l.name
    if not (l/'result.json').exists() or not (r/'result.json').exists():continue
    if any(json.loads((q/'result.json').read_text())['returncode']!=0 for q in [l,r]):continue
    target=a.output/(l.name+'.json')
    if target.exists():continue
    subprocess.run([sys.executable,str(Path(__file__).with_name('compare_runs.py')),str(l/'outputs'),str(r/'outputs'),'--output',str(target)],check=True)
