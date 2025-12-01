# Neganuki Decoupled Algorithms Workspace

This sub-project is a standalone Poetry workspace for experimenting with
perspective correction, homography-based alignment, and stitching pipelines
outside of the Raspberry Pi hardware environment.

## Getting Started

```bash
cd decoupled
poetry install  # add --with image-science,visualization if you need extras
poetry shell
```

Place any local test assets under `data/sample/`. A high-resolution TIFF or RAW
frame exported from the scanner works best for prototyping.

Example structure:

```
decoupled/
  data/
    sample/
      capture_raw_0001.tiff
```

## Running Experiments

The main entry point is `decoupled_algorithms.scan`, which loads every image in
`data/sample/`, rotates each frame, aligns them, and writes a stitched TIFF
under `output/`.

```bash
poetry run python -m decoupled_algorithms.scan --method ecc --log-level info
```

### CLI Options

- `--method {ecc,orb,sift}`: choose the alignment backend (default `ecc`).
- `--log-level {critical,error,warning,info,debug}`: control logging verbosity.
- `--ecc-max-iter <int>` / `--ecc-epsilon <float>`: tune ECC convergence when using the ECC backend.

Outputs are saved as `output/neganuki_<method>_<timestamp>.tiff` with a dynamic
canvas sized to fit all aligned frames.

## Suggested Dependencies

The default dependencies cover TIFF/RAW IO and base image processing:

- `numpy`
- `opencv-python`
- `pillow`
- `tifffile`
- `rawpy`
