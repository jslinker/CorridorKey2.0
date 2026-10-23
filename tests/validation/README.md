# Cross-platform validation

These tools preserve commands, exit codes, elapsed wall time, logs, output hashes,
and exact decoded-pixel comparisons. They do not declare a numerical tolerance.
The same source and model asset hashes must be used for a controlled comparison.

The 82-case matrix covers all nonempty output selections, hint mode combinations,
representative numeric settings, image/video inputs, encoders, expected failures,
and two full-resolution input runs. Continuous numeric parameters have infinitely
many combinations; this is a finite test matrix, not exhaustive numeric coverage.

## Inputs

Supply an `Example Files` directory containing `example-green-screen.mp4` and
`Video Frames (24)/output_01.png` through `output_24.png`. Media is not included
in the repository. Run each command from the repository root with its virtual
environment active. Install `pytest`, `opencv-python`, and `OpenEXR` for validation.
FFmpeg and FFprobe must be available on PATH for media comparisons.

```sh
python tests/validation/prepare_validation.py --source . \
  --inputs '/path/to/Example Files' --output /path/to/validation
python tests/validation/run_suite.py --source . \
  --inputs '/path/to/Example Files' --fixtures /path/to/validation/fixtures \
  --runs /path/to/runs --groups smoke matrix known-failure native
python tests/validation/support_checks.py --source . \
  --fixtures /path/to/validation/fixtures --output /path/to/support-checks
python -m pytest -q tests/test_device.py
```

The prepared hints are deterministic green-threshold test fixtures. They are not
artist mattes or ground truth. The synthetic linear EXRs contain values above one.
Use one generated fixture set on both systems, then verify its SHA256 manifest.
Regeneration with different image libraries or encoders can change file bytes.

`run_suite.py` stops at an unexpected exit status or invalid EXR. It skips any case
with an existing result record; preserve a failed case under a different directory
before rerunning it. `run_case.py` times the complete subprocess, including startup,
model loading, inference, and output writing. Do not treat it as GPU kernel time.

The support checks exercise help, checkpoint loading, interactive command planning
without starting inference, and conversion of a small synthetic legacy checkpoint.
They do not validate a real legacy training checkpoint. Model download is verified
separately by matching the complete asset manifest.

## Compare two run sets

```sh
python tests/validation/compare_suite.py --left /path/to/windows/runs \
  --right /path/to/mac/runs --output /path/to/comparisons
```

Image metrics are in stored EXR units. Video metrics are decoded 16-bit sample
units (divide by 65535 for normalized values). Different codec builds can add
encoding differences. Settings files contain machine-specific paths, so compare
media pixels separately from whole-file bytes. Missing media, shape differences,
invalid values, frame counts, and exact repeatability need separate checks.

Auto memory settings can select different temporal windows on different GPUs.
Use identical explicit Hann window, stride, and memory mode for controlled pixel
comparisons. Default-auto runs test usability and performance on each system.

## Agreed numerical limits

For each raw EXR frame, compare alpha separately from color. Alpha must have
maximum absolute error at most 0.02 and mean absolute error at most 0.0005.
Color must have maximum absolute error at most 0.05 and mean absolute error at
most 0.001. These are stored linear EXR units, not display-brightness percentages.
The user accepted these limits on 2026-10-22. Matching dimensions, frame counts,
finite values, and exact repeatability within each platform remain required.

```sh
python tests/validation/audit_comparisons.py --comparisons /path/to/comparisons \
  --output /path/to/tolerance-audit.json
```

This audit reports encoded video separately. Its limits apply to raw EXR output.
A passed exit status alone is not a parity result.
