"""Build reproducible fixtures and a CLI option inventory from supplied data."""
import argparse
import os
import ast
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--inputs', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--ffmpeg', default='ffmpeg')
args = parser.parse_args()
ROOT = args.output.resolve()
ROOT.mkdir(parents=True, exist_ok=True)
source = args.source.resolve()
originals = args.inputs.resolve()
fixtures = ROOT / 'fixtures'
for name in ('frames', 'hints', 'linear_exr', 'jpg', 'jpeg'):
    (fixtures / name).mkdir(parents=True, exist_ok=True)

catalog = {}
for file in [source / 'infer.py', *sorted((source / 'scripts').glob('*.py'))]:
    options = []
    for node in ast.walk(ast.parse(file.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument':
            record = {'flags': [ast.literal_eval(a) for a in node.args], 'line': node.lineno}
            for k in node.keywords:
                try:
                    record[k.arg] = ast.literal_eval(k.value)
                except (ValueError, TypeError):
                    record[k.arg] = ast.unparse(k.value)
            options.append(record)
    catalog[str(file.relative_to(source))] = options
(ROOT / 'cli-catalog.json').write_text(json.dumps(catalog, indent=2))

for i, file in enumerate(sorted((originals / 'Video Frames (24)').glob('*.png'))):
    bgr = cv2.imread(str(file), cv2.IMREAD_COLOR)
    small = cv2.resize(bgr, (384, 216), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(fixtures / 'frames' / f'frame_{i:03d}.png'), small)
    b, g, r = small.astype(np.int16).transpose(2, 0, 1)
    matte = np.where((g > r + 20) & (g > b + 20), 0, 255).astype(np.uint8)
    cv2.imwrite(str(fixtures / 'hints' / f'frame_{i:03d}.png'), matte)
    if i < 5:
        cv2.imwrite(str(fixtures / 'jpg' / f'frame_{i:03d}.jpg'), small, [cv2.IMWRITE_JPEG_QUALITY, 95])
        cv2.imwrite(str(fixtures / 'jpeg' / f'frame_{i:03d}.jpeg'), small, [cv2.IMWRITE_JPEG_QUALITY, 95])
        rgb = small[:, :, ::-1].astype(np.float32) / 255
        linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
        import OpenEXR
        # Include above-one values to verify the HDR path with deterministic data.
        OpenEXR.File({}, {'R': linear[:, :, 0] * 2, 'G': linear[:, :, 1] * 2, 'B': linear[:, :, 2] * 2}).write(str(fixtures / 'linear_exr' / f'frame_{i:03d}.exr'))

subprocess.run([args.ffmpeg, '-y', '-v', 'error', '-framerate', '24', '-i', str(fixtures/'frames/frame_%03d.png'), '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv444p', str(fixtures/'sample.mp4')], check=True)
subprocess.run([args.ffmpeg, '-y', '-v', 'error', '-framerate', '24', '-i', str(fixtures/'hints/frame_%03d.png'), '-c:v', 'ffv1', '-pix_fmt', 'gray', str(fixtures/'hints.mkv')], check=True)

def manifest(base):
    return [{'path': str(f.relative_to(base)), 'bytes': f.stat().st_size,
             'sha256': hashlib.file_digest(f.open('rb'), 'sha256').hexdigest()}
            for f in sorted(base.rglob('*')) if f.is_file()]

(ROOT / 'original-input-manifest.json').write_text(json.dumps(manifest(originals), indent=2))
(ROOT / 'fixture-manifest.json').write_text(json.dumps(manifest(fixtures), indent=2))
print(f'Cataloged {sum(map(len, catalog.values()))} options; created fixtures in {fixtures}')
