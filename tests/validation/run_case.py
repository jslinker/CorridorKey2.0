"""Execute an unchanged CLI command, recording reproducible timing and hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

p = argparse.ArgumentParser()
p.add_argument('--source', required=True, type=Path)
p.add_argument('--runs', required=True, type=Path)
p.add_argument('--name', required=True)
p.add_argument('--ffmpeg', default='ffmpeg')
p.add_argument('--timeout', type=int, default=7200)
p.add_argument('arguments', nargs=argparse.REMAINDER)
a = p.parse_args()
case = a.runs.resolve() / a.name
case.mkdir(parents=True, exist_ok=False)
arguments = a.arguments[1:] if a.arguments[:1] == ['--'] else a.arguments
command = [sys.executable, '-u', str(a.source.resolve() / 'infer.py'),
           '--output_dir', str(case / 'outputs'), '--temp_dir', str(case / 'temp'),
           '--ffmpeg_bin', a.ffmpeg, *arguments]
record = {'name': a.name, 'command': command, 'cwd': str(a.source.resolve()),
          'platform': platform.platform(), 'python': sys.version, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
(case / 'command.json').write_text(json.dumps(record, indent=2))
start = time.perf_counter()
environment = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
try:
    with (case / 'process.log').open('wb') as log:
        process = subprocess.run(command, cwd=a.source, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=a.timeout)
    record['returncode'] = process.returncode
except subprocess.TimeoutExpired:
    record['returncode'] = None
    record['timeout'] = a.timeout
record['elapsed_seconds'] = time.perf_counter() - start
record['outputs'] = []
record['invalid_media'] = []
for f in sorted((case / 'outputs').rglob('*')):
    if f.is_file():
        with f.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        record['outputs'].append({'path': str(f.relative_to(case)), 'bytes': f.stat().st_size, 'sha256': digest})
        if f.suffix.lower() == '.exr':
            os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
            import cv2
            import numpy as np
            pixels = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
            if pixels is None or not np.isfinite(pixels).all():
                record['invalid_media'].append(str(f.relative_to(case)))
(case / 'result.json').write_text(json.dumps(record, indent=2))
print(json.dumps({k: record[k] for k in ('name', 'returncode', 'elapsed_seconds')}), flush=True)
sys.exit(3 if record['invalid_media'] else (record['returncode'] if record['returncode'] is not None else 124))
