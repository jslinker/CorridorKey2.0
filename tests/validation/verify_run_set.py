"""Check recorded exits, output hashes, dimensions, counts, and finite EXRs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
import cv2
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--runs', type=Path, required=True)
p.add_argument('--suite', type=Path, default=Path(__file__).with_name('suite.json'))
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()

def options(args):
    values = {}
    for item in args:
        if item.startswith('--'):
            key = item
            values[key] = []
        else:
            values[key].append(item)
    return values

def output_kind(path):
    name = path.name.lower()
    return next((kind for kind in ['alpha', 'checker', 'cutout', 'fg']
                 if name.startswith(kind + '_') or '_' + kind + '_' in name
                 or name.endswith('_' + kind + path.suffix)), None)

rows = []
for case in json.loads(a.suite.read_text()):
    folder = a.runs / case['name']
    result = folder / 'result.json'
    row = {'case': case['name'], 'errors': [], 'media_files': 0}
    rows.append(row)
    if not result.exists():
        row['pending'] = True
        continue
    record = json.loads(result.read_text())
    if record['returncode'] != case['expected_returncode']:
        row['errors'].append('Unexpected exit code')
    for output in record.get('outputs', []):
        path = folder / output['path'].replace('\\', '/')
        if not path.exists():
            row['errors'].append('Missing recorded output: ' + output['path'])
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != output['sha256']:
            row['errors'].append('Changed output hash: ' + output['path'])
    if case['expected_returncode'] != 0:
        continue
    opts = options(case['args'])
    requested = int(opts.get('--num_frames', ['-1'])[0])
    available = 302 if case['name'] == 'native-video-302' else 24
    frames = min(requested, available) if requested > 0 else available
    width, height = (3840, 2160) if case['group'] == 'native' else (384, 216)
    selected = [x.lower() for item in opts.get('--outputs', []) for x in item.split(',')]
    aliases = {'foreground': 'fg', 'raw_fg': 'fg'}
    selected = set(aliases.get(x, x) for x in selected) or {'alpha', 'fg'}
    fmt = opts.get('--output_format', ['video'])[0]
    counts = {kind: 0 for kind in selected}
    for path in sorted((folder / 'outputs').rglob('*')):
        if path.suffix.lower() not in {'.exr', '.mp4', '.mov', '.mkv'}:
            continue
        row['media_files'] += 1
        kind = output_kind(path)
        if kind not in counts:
            row['errors'].append('Unexpected media: ' + path.name)
            continue
        counts[kind] += 1
        if path.suffix.lower() == '.exr':
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if image is None or image.shape[:2] != (height, width) or not np.isfinite(image).all():
                row['errors'].append('Invalid EXR dimensions or values: ' + path.name)
        else:
            probe = json.loads(subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,nb_frames', '-of', 'json', str(path)]))
            stream = probe['streams'][0]
            if (stream['width'], stream['height']) != (width, height):
                row['errors'].append('Invalid video dimensions: ' + path.name)
            if int(stream.get('nb_frames', -1)) != frames:
                row['errors'].append('Video frame count differs or is unavailable: ' + path.name)
    expected = frames if fmt == 'exr' else 1
    if any(count != expected for count in counts.values()):
        row['errors'].append(f'Output count mismatch: expected {expected} per selection; got {counts}')
    row['expected_frames'] = frames
    row['output_counts'] = counts
report = {'runs': str(a.runs), 'cases': rows,
          'failed': [r['case'] for r in rows if r['errors']],
          'pending': [r['case'] for r in rows if r.get('pending')]}
a.output.write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))
