# Cross-platform validation

These tools preserve commands, exit codes, elapsed wall time, logs, output hashes,
and exact decoded-pixel comparisons. The audit applies the limits listed below.
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

### Accepted exception for the supplied 24-frame fixture

The user accepted one exception for `all-frames` and its equivalent
`zero-means-all-frames` command on 2026-10-22. On this supplied PNG fixture,
alpha maximum absolute error reaches 0.1640625. At most 23 of 82,944 pixels
per frame exceed 0.02; 120 of 1,990,656 pixels exceed it across the sequence.
The largest errors are near the left image edge. Alpha mean error and all
color limits pass. Higher-precision experiments did not remove the difference.

This is a documented exception for this measured result. It does not change
the general limits or accept future regressions. The numerical audit continues
to report these exceedances so they remain visible.

## Check output structure and preserved hashes

```sh
python tests/validation/verify_run_set.py --runs /path/to/runs \
  --output /path/to/inventory-audit.json
```

This check is specific to the supplied matrix and its 384 × 216 fixtures and
3840 × 2160 original media. It checks recorded file hashes, expected exit codes,
output selections, frame counts, dimensions, and finite EXR values. It reports
missing cases as pending. Windows paths in saved records are supported on Mac.
